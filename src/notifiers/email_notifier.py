"""Email notifier for sending alerts via SMTP."""

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from ..checkers.base_checker import CheckResult
from ..storage.credential_manager import CredentialManager
from .base_notifier import BaseNotifier


class EmailNotifier(BaseNotifier):
    """Send notifications via email."""

    def __init__(
        self,
        config: Dict[str, Any],
        credential_manager: Optional[CredentialManager] = None,
    ):
        """
        Initialize email notifier.

        Args:
            config: Configuration dictionary
            credential_manager: Optional credential manager
        """
        super().__init__(config)
        self.credential_manager = credential_manager or CredentialManager()
        self.email_config = None

        if self.enabled:
            self._setup_email_config()

    def _is_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        return (
            self.config.get("notifications", {}).get("email", {}).get("enabled", False)
        )

    def _setup_email_config(self):
        """Set up email configuration from credentials."""
        self.email_config = self.credential_manager.get_email_credentials()

        # Override with config values if present
        email_settings = self.config.get("notifications", {}).get("email", {})
        self.email_config["smtp_server"] = email_settings.get(
            "smtp_server", self.email_config.get("smtp_server")
        )
        self.email_config["smtp_port"] = email_settings.get(
            "smtp_port", self.email_config.get("smtp_port")
        )
        self.email_config["use_tls"] = email_settings.get("use_tls", True)

        # Get recipient list
        to_addresses = email_settings.get("to_addresses", [])
        if to_addresses and "${EMAIL_TO}" in to_addresses:
            to_addresses = (
                [self.email_config.get("to_address", "")]
                if self.email_config.get("to_address")
                else []
            )
        self.email_config["to_addresses"] = to_addresses

        # Validate configuration
        if not all(
            [
                self.email_config.get("from_address"),
                self.email_config.get("to_addresses"),
                self.email_config.get("password"),
            ]
        ):
            self.logger.warning(
                "Email configuration incomplete, notifications disabled"
            )
            self.enabled = False

    def notify(
        self,
        result: CheckResult,
        previous_result: CheckResult = None,
        site_name: str = None,
    ) -> bool:
        """
        Send email notification for a check result.

        Args:
            result: Current check result
            previous_result: Previous check result
            site_name: Name of the site being checked

        Returns:
            True if email sent successfully
        """
        if not self.enabled or not self.should_notify(result, previous_result):
            return False

        try:
            # Determine email subject and type
            subject, email_type = self._get_email_subject_and_type(
                result, previous_result, site_name
            )

            # Check if we should send this type of alert
            alert_on = (
                self.config.get("notifications", {})
                .get("email", {})
                .get("alert_on", [])
            )
            if alert_on and email_type not in alert_on:
                self.logger.debug(
                    f"Email type '{email_type}' not in alert_on list, skipping"
                )
                return False

            # Create email content
            html_content = self._create_html_email(result, previous_result, site_name)
            text_content = self._create_text_email(result, previous_result, site_name)

            # Send email
            return self._send_email(subject, html_content, text_content)

        except Exception as e:
            self.logger.error(f"Failed to send email notification: {e}")
            return False

    def notify_batch(self, results: List[CheckResult]) -> bool:
        """
        Send email with multiple results.

        Args:
            results: List of check results

        Returns:
            True if email sent successfully
        """
        if not self.enabled or not results:
            return False

        try:
            # Create summary
            failures = [r for r in results if r.is_failure]
            warnings = [r for r in results if r.is_warning]
            successes = [r for r in results if r.is_success]

            subject = (
                f"InfoRuta Monitor: {len(failures)} failures, {len(warnings)} warnings"
            )

            # Create batch email content
            html_content = self._create_batch_html_email(results)
            text_content = self._create_batch_text_email(results)

            return self._send_email(subject, html_content, text_content)

        except Exception as e:
            self.logger.error(f"Failed to send batch email notification: {e}")
            return False

    def _get_email_subject_and_type(
        self,
        result: CheckResult,
        previous_result: CheckResult = None,
        site_name: str = None,
    ) -> tuple:
        """Get email subject and type based on results."""
        site_identifier = site_name or self.config.get("monitoring", {}).get(
            "url", "Site"
        )

        # Detect state changes
        if previous_result:
            if previous_result.is_success and result.is_failure:
                return (f"🔴 ALERT: {site_identifier} is DOWN", "downtime")
            elif previous_result.is_failure and result.is_success:
                return (f"✅ RECOVERY: {site_identifier} is back online", "recovery")

        # Regular status emails
        if result.is_failure:
            if result.check_type == "authentication":
                return (
                    f"🔐 AUTH FAILURE: {site_identifier} login failed",
                    "auth_failure",
                )
            else:
                return (f"🔴 FAILURE: {site_identifier} check failed", "downtime")
        elif result.is_warning:
            return (f"⚠️ WARNING: {site_identifier} slow response", "slow_response")
        else:
            return (f"✅ OK: {site_identifier} is online", "status_update")

    def _create_html_email(
        self,
        result: CheckResult,
        previous_result: CheckResult = None,
        site_name: str = None,
    ) -> str:
        """Create HTML email content."""
        site_identifier = site_name or self.config.get("monitoring", {}).get(
            "url", "Site"
        )

        # Determine status color
        status_color = {
            "success": "#28a745",
            "warning": "#ffc107",
            "failure": "#dc3545",
            "error": "#dc3545",
            "timeout": "#6c757d",
        }.get(result.status.value, "#6c757d")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {status_color}; color: white; padding: 20px; text-align: center; }}
                .content {{ background-color: #f4f4f4; padding: 20px; margin-top: 10px; }}
                .metrics {{ background-color: white; padding: 15px; margin-top: 10px; }}
                .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>InfoRuta Monitor Alert</h2>
                    <h3>{result.check_type.upper()} - {result.status.value.upper()}</h3>
                </div>

                <div class="content">
                    <p><strong>Site:</strong> {site_identifier}</p>
                    <p><strong>Check Time:</strong> {result.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</p>
                    <p><strong>Response Time:</strong> {result.response_time_ms:.0f}ms</p>
        """

        if result.status_code:
            html += f"<p><strong>HTTP Status:</strong> {result.status_code}</p>"

        if result.error_message:
            html += f"""
                <div style="background-color: #f8d7da; color: #721c24; padding: 10px; margin-top: 10px;">
                    <strong>Error:</strong> {result.error_message}
                </div>
            """

        if result.warning_message:
            html += f"""
                <div style="background-color: #fff3cd; color: #856404; padding: 10px; margin-top: 10px;">
                    <strong>Warning:</strong> {result.warning_message}
                </div>
            """

        # Add metrics if available
        if result.metrics:
            html += """
                </div>
                <div class="metrics">
                    <h4>Performance Metrics</h4>
                    <table>
            """
            for key, value in result.metrics.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        html += f"<tr><td>{key}.{sub_key}</td><td>{sub_value}</td></tr>"
                else:
                    html += f"<tr><td>{key}</td><td>{value}</td></tr>"
            html += "</table>"

        html += f"""
                </div>
                <div class="footer">
                    <p>InfoRuta Website Monitor v1.0.0</p>
                    <p>This is an automated monitoring alert</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _create_text_email(
        self,
        result: CheckResult,
        previous_result: CheckResult = None,
        site_name: str = None,
    ) -> str:
        """Create plain text email content."""
        site_identifier = site_name or self.config.get("monitoring", {}).get(
            "url", "Site"
        )

        text = f"""
Multi-Site Monitor Alert
{"=" * 40}

Site: {site_identifier}
Check Type: {result.check_type.upper()}
Status: {result.status.value.upper()}
Time: {result.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
Response Time: {result.response_time_ms:.0f}ms
"""

        if result.status_code:
            text += f"HTTP Status: {result.status_code}\n"

        if result.error_message:
            text += f"\nError: {result.error_message}\n"

        if result.warning_message:
            text += f"\nWarning: {result.warning_message}\n"

        text += f"""
{"=" * 40}
InfoRuta Website Monitor v1.0.0
This is an automated monitoring alert
"""

        return text

    def _create_batch_html_email(self, results: List[CheckResult]) -> str:
        """Create HTML email for batch results."""
        # Group results by status
        failures = [r for r in results if r.is_failure]
        warnings = [r for r in results if r.is_warning]
        successes = [r for r in results if r.is_success]

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 800px; margin: 0 auto; padding: 20px; }
                .summary { background-color: #f8f9fa; padding: 20px; margin-bottom: 20px; }
                .section { margin-bottom: 30px; }
                table { width: 100%; border-collapse: collapse; margin-top: 10px; }
                th { background-color: #343a40; color: white; padding: 10px; text-align: left; }
                td { padding: 8px; border-bottom: 1px solid #ddd; }
                .status-success { color: #28a745; }
                .status-warning { color: #ffc107; }
                .status-failure { color: #dc3545; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>InfoRuta Monitor - Batch Report</h2>

                <div class="summary">
                    <h3>Summary</h3>
                    <p>Total Checks: {}</p>
                    <p class="status-failure">Failures: {}</p>
                    <p class="status-warning">Warnings: {}</p>
                    <p class="status-success">Successes: {}</p>
                </div>
        """.format(len(results), len(failures), len(warnings), len(successes))

        # Add sections for each status type
        for section_name, section_results, status_class in [
            ("Failures", failures, "status-failure"),
            ("Warnings", warnings, "status-warning"),
            ("Successes", successes, "status-success"),
        ]:
            if section_results:
                html += f"""
                <div class="section">
                    <h3 class="{status_class}">{section_name}</h3>
                    <table>
                        <tr>
                            <th>Check Type</th>
                            <th>Time</th>
                            <th>Response Time</th>
                            <th>Details</th>
                        </tr>
                """

                for result in section_results:
                    details = result.error_message or result.warning_message or "OK"
                    html += f"""
                        <tr>
                            <td>{result.check_type}</td>
                            <td>{result.timestamp.strftime("%H:%M:%S")}</td>
                            <td>{result.response_time_ms:.0f}ms</td>
                            <td>{details}</td>
                        </tr>
                    """

                html += "</table></div>"

        html += """
            </div>
        </body>
        </html>
        """

        return html

    def _create_batch_text_email(self, results: List[CheckResult]) -> str:
        """Create text email for batch results."""
        failures = [r for r in results if r.is_failure]
        warnings = [r for r in results if r.is_warning]
        successes = [r for r in results if r.is_success]

        text = f"""
InfoRuta Monitor - Batch Report
{"=" * 40}

Summary:
- Total Checks: {len(results)}
- Failures: {len(failures)}
- Warnings: {len(warnings)}
- Successes: {len(successes)}

{"=" * 40}
"""

        for section_name, section_results in [
            ("FAILURES", failures),
            ("WARNINGS", warnings),
            ("SUCCESSES", successes),
        ]:
            if section_results:
                text += f"\n{section_name}:\n"
                for result in section_results:
                    details = result.error_message or result.warning_message or "OK"
                    text += f"  - {result.check_type}: {details} ({result.response_time_ms:.0f}ms)\n"

        return text

    def _send_email(self, subject: str, html_content: str, text_content: str) -> bool:
        """
        Send email via SMTP.

        Args:
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body

        Returns:
            True if sent successfully
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email_config["from_address"]
            msg["To"] = ", ".join(self.email_config["to_addresses"])

            # Attach parts
            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")
            msg.attach(text_part)
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(
                self.email_config["smtp_server"], self.email_config["smtp_port"]
            ) as server:
                if self.email_config.get("use_tls", True):
                    server.starttls()
                server.login(
                    self.email_config["from_address"], self.email_config["password"]
                )
                server.send_message(msg)

            self.logger.info(f"Email sent successfully: {subject}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False
