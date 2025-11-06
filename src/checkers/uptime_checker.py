"""Uptime checker for basic website availability monitoring."""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx
import ssl
import socket
from urllib.parse import urlparse

from .base_checker import BaseChecker, CheckResult, CheckStatus


class UptimeChecker(BaseChecker):
    """Check if website is up and responding."""

    def get_check_type(self) -> str:
        """Return the check type identifier."""
        return "uptime"

    def check(self) -> CheckResult:
        """
        Perform uptime check on configured endpoints.

        Returns:
            CheckResult with uptime status
        """
        start_time = time.time()
        timestamp = datetime.now()

        try:
            # Get configuration
            url = self.config.get("monitoring", {}).get(
                "url", "https://inforuta-rce.es/"
            )
            endpoints = (
                self.config.get("checks", {}).get("uptime", {}).get("endpoints", ["/"])
            )
            expected_status = (
                self.config.get("checks", {})
                .get("uptime", {})
                .get("expected_status", [200, 301, 302])
            )
            check_ssl = (
                self.config.get("checks", {}).get("uptime", {}).get("check_ssl", True)
            )

            # Check each endpoint
            all_success = True
            error_messages = []
            warning_messages = []
            metrics = {}
            details = {}
            status_code = None

            for endpoint in endpoints:
                full_url = url.rstrip("/") + "/" + endpoint.lstrip("/")
                self.logger.info(f"Checking endpoint: {full_url}")

                try:
                    # Perform HTTP request
                    response = self.client.get(full_url)
                    status_code = response.status_code

                    # Extract performance metrics
                    endpoint_metrics = self.measure_performance_metrics(response)
                    metrics[f"endpoint_{endpoint}"] = endpoint_metrics

                    # Check status code
                    if status_code not in expected_status:
                        all_success = False
                        error_messages.append(
                            f"Unexpected status code {status_code} for {endpoint}"
                        )

                    # Check SSL certificate if enabled
                    if check_ssl and full_url.startswith("https"):
                        ssl_check = self._check_ssl_certificate(full_url)
                        if not ssl_check["valid"]:
                            warning_messages.append(ssl_check["message"])
                        details["ssl"] = ssl_check

                    # Check response time
                    response_time = endpoint_metrics.get("total_time_ms", 0)
                    warning_threshold = self.config.get("performance", {}).get(
                        "warning_threshold_ms", 3000
                    )
                    critical_threshold = self.config.get("performance", {}).get(
                        "critical_threshold_ms", 10000
                    )

                    if response_time > critical_threshold:
                        warning_messages.append(
                            f"Critical: Response time {response_time:.0f}ms exceeds {critical_threshold}ms"
                        )
                    elif response_time > warning_threshold:
                        warning_messages.append(
                            f"Slow response: {response_time:.0f}ms exceeds {warning_threshold}ms"
                        )

                except httpx.TimeoutException as e:
                    all_success = False
                    error_messages.append(f"Timeout for {endpoint}: {str(e)}")
                    self.logger.error(f"Timeout checking {full_url}: {e}")

                except httpx.ConnectError as e:
                    all_success = False
                    error_messages.append(f"Connection error for {endpoint}: {str(e)}")
                    self.logger.error(f"Connection error checking {full_url}: {e}")

                except httpx.HTTPError as e:
                    all_success = False
                    error_messages.append(f"HTTP error for {endpoint}: {str(e)}")
                    self.logger.error(f"HTTP error checking {full_url}: {e}")

            # Calculate total response time
            response_time_ms = (time.time() - start_time) * 1000

            # Determine overall status
            if not all_success:
                status = CheckStatus.FAILURE
            elif warning_messages:
                status = CheckStatus.WARNING
            else:
                status = CheckStatus.SUCCESS

            # Create result
            result = CheckResult(
                check_type=self.get_check_type(),
                timestamp=timestamp,
                status=status,
                success=all_success,
                status_code=status_code,
                response_time_ms=response_time_ms,
                error_message="; ".join(error_messages) if error_messages else None,
                warning_message="; ".join(warning_messages)
                if warning_messages
                else None,
                metrics=metrics,
                details=details,
            )

            # Update consecutive counts
            self.update_consecutive_counts(result)

            # Log result
            if result.is_success:
                self.logger.info(f"Uptime check successful in {response_time_ms:.0f}ms")
            elif result.is_warning:
                self.logger.warning(
                    f"Uptime check completed with warnings: {result.warning_message}"
                )
            else:
                self.logger.error(f"Uptime check failed: {result.error_message}")

            return result

        except Exception as e:
            # Handle unexpected errors
            self.logger.error(
                f"Unexpected error during uptime check: {e}", exc_info=True
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

    def _check_ssl_certificate(self, url: str) -> Dict[str, Any]:
        """
        Check SSL certificate validity and expiration.

        Args:
            url: URL to check SSL certificate for

        Returns:
            Dictionary with SSL check results
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            port = parsed.port or 443

            # Create SSL context
            context = ssl.create_default_context()

            # Connect and get certificate
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()

                    # Check expiration
                    not_after = datetime.strptime(
                        cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
                    )
                    days_until_expiry = (not_after - datetime.now()).days

                    if days_until_expiry < 0:
                        return {
                            "valid": False,
                            "message": f"SSL certificate expired {abs(days_until_expiry)} days ago",
                            "expiry_date": not_after.isoformat(),
                            "days_until_expiry": days_until_expiry,
                        }
                    elif days_until_expiry < 30:
                        return {
                            "valid": True,
                            "message": f"SSL certificate expires in {days_until_expiry} days",
                            "expiry_date": not_after.isoformat(),
                            "days_until_expiry": days_until_expiry,
                            "warning": True,
                        }
                    else:
                        return {
                            "valid": True,
                            "message": f"SSL certificate valid for {days_until_expiry} days",
                            "expiry_date": not_after.isoformat(),
                            "days_until_expiry": days_until_expiry,
                        }

        except Exception as e:
            self.logger.warning(f"Could not check SSL certificate: {e}")
            return {
                "valid": False,
                "message": f"Could not verify SSL certificate: {str(e)}",
                "error": True,
            }
