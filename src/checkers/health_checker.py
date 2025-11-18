"""Health checker for deep application health verification."""

import time
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from .auth_checker import AuthChecker
from .base_checker import BaseChecker, CheckResult, CheckStatus, SSRFProtectionError


class HealthChecker(BaseChecker):
    """Check application health by accessing protected endpoints."""

    def __init__(
        self,
        config: Dict[str, Any],
        client: Optional[httpx.Client] = None,
        auth_checker: Optional[AuthChecker] = None,
    ):
        """
        Initialize health checker.

        Args:
            config: Configuration dictionary
            client: Optional HTTPX client
            auth_checker: Optional auth checker for session reuse
        """
        super().__init__(config, client)
        self.auth_checker = auth_checker

    def get_check_type(self) -> str:
        """Return the check type identifier."""
        return "health"

    def check(self) -> CheckResult:
        """
        Perform health check on protected endpoints.

        Returns:
            CheckResult with health status
        """
        start_time = time.time()
        timestamp = datetime.now()

        # Check if health check is enabled
        if not self.config.get("checks", {}).get("health", {}).get("enabled", False):
            return CheckResult(
                check_type=self.get_check_type(),
                timestamp=timestamp,
                status=CheckStatus.SUCCESS,
                success=True,
                response_time_ms=0,
                details={"message": "Health check disabled"},
            )

        try:
            # Ensure we have a valid session
            if not self.auth_checker or not self.auth_checker.session_cookies:
                self.logger.warning(
                    "No authenticated session available for health check"
                )
                return CheckResult(
                    check_type=self.get_check_type(),
                    timestamp=timestamp,
                    status=CheckStatus.ERROR,
                    success=False,
                    response_time_ms=(time.time() - start_time) * 1000,
                    error_message="No authenticated session available",
                )

            # Get configuration
            base_url = self.config.get("monitoring", {}).get(
                "url", "https://inforuta-rce.es/"
            )
            protected_endpoint = (
                self.config.get("checks", {})
                .get("health", {})
                .get("protected_endpoint", "/ajax/alertasUsuario.aspx")
            )
            expected_content = (
                self.config.get("checks", {})
                .get("health", {})
                .get("expected_content", [])
            )

            # Construct URL
            health_url = base_url.rstrip("/") + "/" + protected_endpoint.lstrip("/")

            self.logger.info(f"Checking protected endpoint: {health_url}")

            # Make request with session cookies using SSRF-protected method
            response = self._make_request(
                "get", health_url, cookies=self.auth_checker.session_cookies
            )

            response_time_ms = (time.time() - start_time) * 1000

            # Check response status
            if response.status_code == 401 or response.status_code == 403:
                self.logger.error("Session expired or unauthorized")
                result = CheckResult(
                    check_type=self.get_check_type(),
                    timestamp=timestamp,
                    status=CheckStatus.FAILURE,
                    success=False,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    error_message="Session expired or unauthorized",
                )
            elif response.status_code != 200:
                self.logger.error(f"Unexpected status code: {response.status_code}")
                result = CheckResult(
                    check_type=self.get_check_type(),
                    timestamp=timestamp,
                    status=CheckStatus.FAILURE,
                    success=False,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    error_message=f"Unexpected status code: {response.status_code}",
                )
            else:
                # Check for expected content
                content_found = []
                content_missing = []
                response_text = response.text.lower()

                for expected in expected_content:
                    if expected.lower() in response_text:
                        content_found.append(expected)
                    else:
                        content_missing.append(expected)

                # Check response time
                warning_threshold = self.config.get("performance", {}).get(
                    "warning_threshold_ms", 5000
                )
                critical_threshold = self.config.get("performance", {}).get(
                    "critical_threshold_ms", 10000
                )

                warning_message = None
                if response_time_ms > critical_threshold:
                    warning_message = f"Critical: Response time {response_time_ms:.0f}ms exceeds {critical_threshold}ms"
                elif response_time_ms > warning_threshold:
                    warning_message = f"Slow response: {response_time_ms:.0f}ms exceeds {warning_threshold}ms"

                # Determine status
                if content_missing and expected_content:
                    status = CheckStatus.WARNING
                    warning_message = (
                        f"Missing expected content: {', '.join(content_missing)}"
                    )
                elif warning_message:
                    status = CheckStatus.WARNING
                else:
                    status = CheckStatus.SUCCESS

                self.logger.info(f"Health check completed in {response_time_ms:.0f}ms")

                result = CheckResult(
                    check_type=self.get_check_type(),
                    timestamp=timestamp,
                    status=status,
                    success=True,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    warning_message=warning_message,
                    details={
                        "content_found": content_found,
                        "content_missing": content_missing,
                        "response_length": len(response.text),
                    },
                )

            self.update_consecutive_counts(result)
            return result

        except SSRFProtectionError as e:
            self.logger.error(f"SSRF protection blocked health check: {e}")
            result = CheckResult(
                check_type=self.get_check_type(),
                timestamp=timestamp,
                status=CheckStatus.ERROR,
                success=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=f"SSRF protection blocked request: {str(e)}",
            )

            self.update_consecutive_counts(result)
            return result

        except httpx.TimeoutException as e:
            self.logger.error(f"Health check timeout: {e}")
            result = CheckResult(
                check_type=self.get_check_type(),
                timestamp=timestamp,
                status=CheckStatus.TIMEOUT,
                success=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=f"Timeout: {str(e)}",
            )

            self.update_consecutive_counts(result)
            return result

        except Exception as e:
            self.logger.error(
                f"Unexpected error during health check: {e}", exc_info=True
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
