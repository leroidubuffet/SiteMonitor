"""Authentication checker for InfoRuta login verification."""

import re
import time
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from ..storage.credential_manager import CredentialManager
from .base_checker import BaseChecker, CheckResult, CheckStatus


class AuthChecker(BaseChecker):
    """Check authentication by attempting to log into InfoRuta."""

    def __init__(
        self,
        config: Dict[str, Any],
        client: Optional[httpx.Client] = None,
        credential_manager: Optional[CredentialManager] = None,
        site_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize authentication checker.

        Args:
            config: Configuration dictionary
            client: Optional HTTPX client
            credential_manager: Optional credential manager
            site_config: Site-specific configuration
        """
        super().__init__(config, client)
        self.credential_manager = credential_manager or CredentialManager()
        self.site_config = site_config or {}
        self.session_cookies = {}  # Now stores per-site cookies
        self.session_data = {}

    def get_check_type(self) -> str:
        """Return the check type identifier."""
        return "authentication"

    def check(self, site_name: Optional[str] = None) -> CheckResult:
        """
        Perform authentication check by attempting login.

        Args:
            site_name: Name of the site being checked (for per-site state)

        Returns:
            CheckResult with authentication status
        """
        start_time = time.time()
        timestamp = datetime.now()

        # Get site-specific or global authentication config
        auth_config = self.site_config.get("authentication", {})
        if not auth_config:
            auth_config = self.config.get("checks", {}).get("authentication", {})

        # Check if authentication is enabled
        if not auth_config.get("enabled", True):
            return CheckResult(
                check_type=self.get_check_type(),
                timestamp=timestamp,
                status=CheckStatus.SUCCESS,
                success=True,
                response_time_ms=0,
                details={"message": "Authentication check disabled"},
            )

        try:
            # Get site-specific credentials
            credential_key = self.site_config.get("credential_key", "inforuta")
            credentials = self.credential_manager.get_credentials_by_key(credential_key)

            if not credentials.get("username") or not credentials.get("password"):
                self.logger.warning(f"{credential_key} credentials not configured")
                return CheckResult(
                    check_type=self.get_check_type(),
                    timestamp=timestamp,
                    status=CheckStatus.ERROR,
                    success=False,
                    response_time_ms=(time.time() - start_time) * 1000,
                    error_message="Credentials not configured",
                )

            # Mask credentials for logging
            masked_username = self.credential_manager.mask_credential(
                credentials["username"], visible_chars=3
            )
            self.logger.info(f"Attempting login with username: {masked_username}")

            # Perform login
            login_result = self._perform_login(
                credentials["username"], credentials["password"], site_name
            )

            response_time_ms = (time.time() - start_time) * 1000

            if login_result["success"]:
                site_label = f"[{site_name}] " if site_name else ""
                self.logger.info(
                    f"{site_label}Authentication successful in {response_time_ms:.0f}ms"
                )

                result = CheckResult(
                    check_type=self.get_check_type(),
                    timestamp=timestamp,
                    status=CheckStatus.SUCCESS,
                    success=True,
                    response_time_ms=response_time_ms,
                    details={
                        "session_created": True,
                        "session_data": login_result.get("session_data", {}),
                        "indicators_found": login_result.get("indicators_found", []),
                    },
                )
            else:
                self.logger.error(f"Authentication failed: {login_result['error']}")

                result = CheckResult(
                    check_type=self.get_check_type(),
                    timestamp=timestamp,
                    status=CheckStatus.FAILURE,
                    success=False,
                    response_time_ms=response_time_ms,
                    error_message=login_result["error"],
                    details=login_result,
                )

            self.update_consecutive_counts(result)
            return result

        except Exception as e:
            self.logger.error(
                f"Unexpected error during authentication check: {e}", exc_info=True
            )

            result = CheckResult(
                check_type=self.get_check_type(),
                timestamp=timestamp,
                status=CheckStatus.ERROR,
                success=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=f"Unexpected error: {str(e)}",
            )

            self.update_consecutive_counts(result)
            return result

    def _perform_login(
        self, username: str, password: str, site_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform the actual login to a site.

        Args:
            username: Login username
            password: Login password
            site_name: Name of the site (for per-site session storage)

        Returns:
            Dictionary with login results
        """
        try:
            # Get site-specific URL and config
            base_url = self.site_config.get("url", "")
            if not base_url:
                base_url = self.config.get("monitoring", {}).get("url", "")

            # Get authentication config
            auth_config = self.site_config.get("authentication", {})
            if not auth_config:
                auth_config = self.config.get("checks", {}).get("authentication", {})

            login_endpoint = auth_config.get("login_endpoint", "/")

            # Construct login URL
            login_url = base_url.rstrip("/") + "/" + login_endpoint.lstrip("/")

            # First, get the login page to extract any necessary tokens/viewstate
            self.logger.debug(f"Fetching login page: {login_url}")
            login_page_response = self.client.get(login_url)

            if login_page_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to load login page: HTTP {login_page_response.status_code}",
                }

            # Extract ASP.NET ViewState and other form fields if present
            form_data = self._extract_form_data(login_page_response.text)

            # Auto-detect username/password fields and add credentials
            detected_fields = self._auto_detect_login_fields(login_page_response.text)

            if detected_fields.get("username_field") and detected_fields.get(
                "password_field"
            ):
                # Use auto-detected fields
                form_data[detected_fields["username_field"]] = username
                form_data[detected_fields["password_field"]] = password

                # Add submit button if found
                if detected_fields.get("submit_field"):
                    form_data[detected_fields["submit_field"]] = detected_fields.get(
                        "submit_value", ""
                    )

                self.logger.debug(
                    f"Auto-detected login fields: username={detected_fields['username_field']}, password={detected_fields['password_field']}"
                )
            else:
                # Fallback to InfoRuta defaults
                form_data.update(
                    {
                        "ctl00$MainContent$txtUsuario": username,
                        "ctl00$MainContent$txtClave": password,
                        "ctl00$MainContent$btnEntrar": "Entrar",
                    }
                )
                self.logger.debug("Using InfoRuta default field names")

            # Perform login POST
            self.logger.debug("Submitting login credentials")
            login_response = self.client.post(
                login_url,
                data=form_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": login_url,
                    "Origin": base_url.rstrip("/"),
                },
            )

            # Check for successful login indicators (site-specific or global)
            success_indicators = auth_config.get(
                "success_indicators", ["Usuario", "session", "dashboard"]
            )

            response_text = login_response.text.lower()
            indicators_found = []

            for indicator in success_indicators:
                if indicator.lower() in response_text:
                    indicators_found.append(indicator)

            # Check for common login failure indicators
            failure_indicators = ["error", "invalid", "incorrect", "fail"]
            failures_found = [ind for ind in failure_indicators if ind in response_text]

            # Store session cookies for future use (per-site)
            if login_response.cookies:
                if site_name:
                    self.session_cookies[site_name] = login_response.cookies
                    self.logger.debug(
                        f"[{site_name}] Stored {len(login_response.cookies)} session cookies"
                    )
                else:
                    self.session_cookies["default"] = login_response.cookies
                    self.logger.debug(
                        f"Stored {len(login_response.cookies)} session cookies"
                    )

            # Determine success
            if indicators_found and not failures_found:
                return {
                    "success": True,
                    "indicators_found": indicators_found,
                    "session_data": {
                        "cookies_count": len(login_response.cookies)
                        if login_response.cookies
                        else 0,
                        "final_url": str(login_response.url),
                        "status_code": login_response.status_code,
                    },
                }
            elif failures_found:
                return {
                    "success": False,
                    "error": f"Login failed - found error indicators: {', '.join(failures_found)}",
                    "failures_found": failures_found,
                }
            else:
                # Ambiguous result - no clear success or failure indicators
                return {
                    "success": False,
                    "error": "Login result unclear - no success indicators found",
                    "details": {
                        "status_code": login_response.status_code,
                        "final_url": str(login_response.url),
                        "response_length": len(response_text),
                    },
                }

        except httpx.TimeoutException as e:
            return {"success": False, "error": f"Login timeout: {str(e)}"}
        except httpx.ConnectError as e:
            return {
                "success": False,
                "error": f"Connection error during login: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during login: {str(e)}",
            }

    def _extract_form_data(self, html: str) -> Dict[str, str]:
        """
        Extract ASP.NET form data from HTML.

        Args:
            html: HTML content

        Returns:
            Dictionary of form fields
        """
        form_data = {}

        # Extract ViewState
        viewstate_match = re.search(
            r'<input[^>]*name="__VIEWSTATE"[^>]*value="([^"]*)"', html
        )
        if viewstate_match:
            form_data["__VIEWSTATE"] = viewstate_match.group(1)

        # Extract ViewStateGenerator
        viewstate_gen_match = re.search(
            r'<input[^>]*name="__VIEWSTATEGENERATOR"[^>]*value="([^"]*)"', html
        )
        if viewstate_gen_match:
            form_data["__VIEWSTATEGENERATOR"] = viewstate_gen_match.group(1)

        # Extract EventValidation
        event_val_match = re.search(
            r'<input[^>]*name="__EVENTVALIDATION"[^>]*value="([^"]*)"', html
        )
        if event_val_match:
            form_data["__EVENTVALIDATION"] = event_val_match.group(1)

        self.logger.debug(f"Extracted {len(form_data)} form fields")
        return form_data

    def _auto_detect_login_fields(self, html: str) -> Dict[str, str]:
        """
        Auto-detect username, password, and submit button fields from HTML.
        Uses logic from debug_login.py to find form fields.

        Args:
            html: HTML content of login page

        Returns:
            Dictionary with detected field names
        """
        detected = {}

        # Find all input fields in the form
        inputs = re.findall(r"<input[^>]*>", html, re.IGNORECASE)
        form_fields = {}

        for inp in inputs:
            name_match = re.search(r'name=["\']([^"\']+)["\']', inp)
            value_match = re.search(r'value=["\']([^"\']*)["\']', inp)
            type_match = re.search(r'type=["\']([^"\']+)["\']', inp)

            if name_match:
                name = name_match.group(1)
                value = value_match.group(1) if value_match else ""
                field_type = type_match.group(1) if type_match else "text"
                form_fields[name] = {"value": value, "type": field_type}

        # Look for username field
        username_fields = [
            k
            for k in form_fields.keys()
            if "user" in k.lower() or "usuario" in k.lower() or "login" in k.lower()
        ]
        if username_fields:
            detected["username_field"] = username_fields[0]

        # Look for password field
        password_fields = [
            k
            for k in form_fields.keys()
            if "pass" in k.lower() or "pwd" in k.lower() or "clave" in k.lower()
        ]
        if password_fields:
            detected["password_field"] = password_fields[0]

        # Look for submit button
        button_fields = [
            k
            for k in form_fields.keys()
            if form_fields[k]["type"].lower() in ["submit", "button"]
            and ("btn" in k.lower() or "submit" in k.lower() or "entrar" in k.lower())
        ]
        if button_fields:
            detected["submit_field"] = button_fields[0]
            detected["submit_value"] = form_fields[button_fields[0]]["value"]

        return detected

    def get_session(self, site_name: Optional[str] = None) -> Optional[httpx.Cookies]:
        """
        Get the current session cookies if available.

        Args:
            site_name: Name of the site (for per-site sessions)

        Returns:
            Session cookies or None
        """
        if site_name:
            return self.session_cookies.get(site_name)
        return self.session_cookies.get("default")
