"""Authentication checker for InfoRuta login verification."""

import time
import re
from datetime import datetime
from typing import Dict, Any, Optional
import httpx

from .base_checker import BaseChecker, CheckResult, CheckStatus
from ..storage.credential_manager import CredentialManager


class AuthChecker(BaseChecker):
    """Check authentication by attempting to log into InfoRuta."""

    def __init__(
        self,
        config: Dict[str, Any],
        client: Optional[httpx.Client] = None,
        credential_manager: Optional[CredentialManager] = None,
    ):
        """
        Initialize authentication checker.

        Args:
            config: Configuration dictionary
            client: Optional HTTPX client
            credential_manager: Optional credential manager
        """
        super().__init__(config, client)
        self.credential_manager = credential_manager or CredentialManager()
        self.session_cookies = None
        self.session_data = {}

    def get_check_type(self) -> str:
        """Return the check type identifier."""
        return "authentication"

    def check(self) -> CheckResult:
        """
        Perform authentication check by attempting login.

        Returns:
            CheckResult with authentication status
        """
        start_time = time.time()
        timestamp = datetime.now()

        # Check if authentication is enabled
        if (
            not self.config.get("checks", {})
            .get("authentication", {})
            .get("enabled", True)
        ):
            return CheckResult(
                check_type=self.get_check_type(),
                timestamp=timestamp,
                status=CheckStatus.SUCCESS,
                success=True,
                response_time_ms=0,
                details={"message": "Authentication check disabled"},
            )

        try:
            # Get credentials
            credentials = self.credential_manager.get_inforuta_credentials()

            if not credentials.get("username") or not credentials.get("password"):
                self.logger.warning("InfoRuta credentials not configured")
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
                credentials["username"], credentials["password"]
            )

            response_time_ms = (time.time() - start_time) * 1000

            if login_result["success"]:
                self.logger.info(
                    f"Authentication successful in {response_time_ms:.0f}ms"
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

    def _perform_login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Perform the actual login to InfoRuta.

        Args:
            username: Login username
            password: Login password

        Returns:
            Dictionary with login results
        """
        try:
            base_url = self.config.get("monitoring", {}).get(
                "url", "https://inforuta-rce.es/"
            )
            login_endpoint = (
                self.config.get("checks", {})
                .get("authentication", {})
                .get("login_endpoint", "/login.aspx")
            )

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

            # Add login credentials to form data
            # Field names based on actual InfoRuta form
            form_data.update(
                {
                    "ctl00$MainContent$txtUsuario": username,
                    "ctl00$MainContent$txtClave": password,
                    "ctl00$MainContent$btnEntrar": "Entrar",
                }
            )

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

            # Check for successful login indicators
            success_indicators = (
                self.config.get("checks", {})
                .get("authentication", {})
                .get("success_indicators", ["Usuario", "session", "dashboard"])
            )

            response_text = login_response.text.lower()
            indicators_found = []

            for indicator in success_indicators:
                if indicator.lower() in response_text:
                    indicators_found.append(indicator)

            # Check for common login failure indicators
            failure_indicators = ["error", "invalid", "incorrect", "fail"]
            failures_found = [ind for ind in failure_indicators if ind in response_text]

            # Store session cookies for future use
            if login_response.cookies:
                self.session_cookies = login_response.cookies
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

    def get_session(self) -> Optional[httpx.Cookies]:
        """
        Get the current session cookies if available.

        Returns:
            Session cookies or None
        """
        return self.session_cookies
