"""
Telegram Bot Notifier for Multi-Site Monitor

Sends check results via Telegram Bot API with support for:
- Regular mode: Notify only on state changes (downtime, recovery, auth failures)
- Debug mode: Notify on EVERY check (all sites, every 15 minutes)
- Rich Markdown formatting with emojis
- Batch notifications
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from ..checkers import CheckResult, CheckStatus
from .base_notifier import BaseNotifier


class TelegramNotifier(BaseNotifier):
    """
    Telegram bot notifier with debug mode support.

    Configuration (config.yaml):
        notifications:
            telegram:
                enabled: true
                debug_mode: false  # true = notify on all checks, false = state changes only
                batch_notifications: true
                alert_on:
                    - downtime
                    - recovery
                    - auth_failure

    Environment Variables (.env):
        TELEGRAM_BOT_TOKEN: Bot token from @BotFather
        TELEGRAM_CHAT_ID: Chat/channel ID to send messages to
    """

    TELEGRAM_API_BASE = "https://api.telegram.org/bot"

    def __init__(self, config: Dict[str, Any], credential_manager=None):
        """Initialize Telegram notifier."""
        # Set config attributes BEFORE calling super().__init__()
        # because _is_enabled() is called during parent initialization
        self.telegram_config = config.get("notifications", {}).get("telegram", {})

        from ..storage.credential_manager import CredentialManager

        self.credential_manager = credential_manager or CredentialManager()

        # Now call parent init which will call _is_enabled()
        super().__init__(config)
        self.debug_mode = self.telegram_config.get("debug_mode", False)
        self.batch_enabled = self.telegram_config.get("batch_notifications", True)
        self.alert_types = set(
            self.telegram_config.get(
                "alert_on", ["downtime", "recovery", "auth_failure"]
            )
        )

        # Get credentials
        telegram_creds = self.credential_manager.get_telegram_credentials()
        self.bot_token = telegram_creds.get("bot_token")
        self.chat_id = telegram_creds.get("chat_id")

        # HTTP client for API calls
        self.http_client = httpx.Client(timeout=10.0)

        # Validation
        if self.enabled and (not self.bot_token or not self.chat_id):
            self.logger.error("Telegram enabled but missing BOT_TOKEN or CHAT_ID")
            self._enabled_cache = False

        if self.enabled:
            mode_str = "DEBUG" if self.debug_mode else "REGULAR"
            self.logger.info(f"Telegram notifier initialized in {mode_str} mode")

    def _is_enabled(self) -> bool:
        """Check if Telegram notifications are enabled."""
        return self.telegram_config.get("enabled", False)

    def should_notify(
        self, result: CheckResult, previous_result: Optional[CheckResult] = None
    ) -> bool:
        """
        Determine if notification should be sent.

        Debug mode: Always notify (every check)
        Regular mode: Only notify on state changes or alert types
        """
        # Debug mode: notify on ALL checks
        if self.debug_mode:
            return True

        # Regular mode: use parent class logic (state changes only)
        return super().should_notify(result, previous_result)

    def notify(
        self,
        result: CheckResult,
        previous_result: Optional[CheckResult] = None,
        site_name: str = "Unknown",
    ) -> bool:
        """
        Send a single check result notification via Telegram.

        Args:
            result: Current check result
            previous_result: Previous check result (for state change detection)
            site_name: Name of the site being checked

        Returns:
            bool: True if notification sent successfully
        """
        if not self.enabled:
            return False

        # Check if we should notify based on mode and state changes
        if not self.should_notify(result, previous_result):
            return False

        # Format and send message
        message = self._format_message(result, previous_result, site_name)
        return self._send_telegram_message(message)

    def notify_batch(self, results: List[tuple]) -> bool:
        """
        Send batch notification for multiple check results.

        Args:
            results: List of (CheckResult, previous_result, site_name) tuples

        Returns:
            bool: True if notification sent successfully
        """
        if not self.enabled or not self.batch_enabled:
            return False

        if not results:
            return False

        # Filter results that should be notified
        filtered_results = [
            (result, prev, site)
            for result, prev, site in results
            if self.should_notify(result, prev)
        ]

        if not filtered_results:
            return False

        # Format batch message
        message = self._format_batch_message(filtered_results)
        return self._send_telegram_message(message)

    def _format_message(
        self,
        result: CheckResult,
        previous_result: Optional[CheckResult],
        site_name: str,
    ) -> str:
        """
        Format a single check result as a Telegram message with Markdown.

        Args:
            result: Check result to format
            previous_result: Previous result for state change detection
            site_name: Name of the site

        Returns:
            str: Formatted Telegram message with Markdown
        """
        # Emoji mapping
        emoji = self._get_status_emoji(result.status)

        # Detect state change
        state_change = ""
        if previous_result and previous_result.status != result.status:
            if result.status == CheckStatus.SUCCESS:
                state_change = " 🔄 RECOVERED"
            elif result.status in [CheckStatus.FAILURE, CheckStatus.ERROR]:
                state_change = " 🚨 NEW FAILURE"

        # Check type
        check_type = result.check_type.upper()

        # Status text
        status_text = result.status.name

        # Build message
        lines = [
            f"{emoji} *\\[{self._escape_markdown(site_name)}\\]* {check_type} {status_text}{state_change}",
            "",
        ]

        # Add response time and details
        if result.response_time_ms:
            lines.append(f"⏱ Response: `{result.response_time_ms}ms`")

        # Add HTTP status for uptime checks
        if result.check_type == "uptime" and result.status_code:
            lines.append(f"📊 HTTP: `{result.status_code}`")

        # Add warning message if present
        if result.warning_message:
            lines.append(f"💬 {self._escape_markdown(result.warning_message)}")

        # Add error details for failures
        if result.status in [
            CheckStatus.FAILURE,
            CheckStatus.ERROR,
            CheckStatus.TIMEOUT,
        ]:
            if result.error_message:
                lines.append(
                    f"❗️ Error: `{self._escape_markdown(result.error_message)}`"
                )

        # Timestamp
        timestamp = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"🕐 Time: `{timestamp}`")

        # Debug mode indicator
        if self.debug_mode:
            lines.append("")
            lines.append("_\\[Debug Mode\\]_")

        return "\n".join(lines)

    def _format_batch_message(self, results: List[tuple]) -> str:
        """
        Format multiple check results as a batch message.

        Args:
            results: List of (CheckResult, previous_result, site_name) tuples

        Returns:
            str: Formatted batch message
        """
        lines = ["📋 *Batch Status Update*", ""]

        # Count by status
        status_counts = {}
        for result, _, _ in results:
            status_counts[result.status] = status_counts.get(result.status, 0) + 1

        # Summary
        summary_parts = []
        if CheckStatus.SUCCESS in status_counts:
            summary_parts.append(f"✅ {status_counts[CheckStatus.SUCCESS]} OK")
        if CheckStatus.WARNING in status_counts:
            summary_parts.append(f"⚠️ {status_counts[CheckStatus.WARNING]} WARN")
        if CheckStatus.FAILURE in status_counts:
            summary_parts.append(f"❌ {status_counts[CheckStatus.FAILURE]} FAIL")
        if CheckStatus.ERROR in status_counts:
            summary_parts.append(f"❌ {status_counts[CheckStatus.ERROR]} ERR")
        if CheckStatus.TIMEOUT in status_counts:
            summary_parts.append(f"⏰ {status_counts[CheckStatus.TIMEOUT]} TIMEOUT")

        lines.append(" \\| ".join(summary_parts))
        lines.append("")

        # Individual results (condensed)
        for result, prev, site_name in results:
            emoji = self._get_status_emoji(result.status)
            check_type = result.check_type.upper()[:4]  # Shortened
            response = (
                f"{result.response_time_ms}ms" if result.response_time_ms else "N/A"
            )

            line = f"{emoji} `{self._escape_markdown(site_name)[:15]:15s}` {check_type} `{response}`"
            lines.append(line)

        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append("")
        lines.append(f"🕐 `{timestamp}`")

        return "\n".join(lines)

    def _get_status_emoji(self, status: CheckStatus) -> str:
        """Get emoji for check status."""
        emoji_map = {
            CheckStatus.SUCCESS: "✅",
            CheckStatus.WARNING: "⚠️",
            CheckStatus.FAILURE: "❌",
            CheckStatus.ERROR: "❌",
            CheckStatus.TIMEOUT: "⏰",
        }
        return emoji_map.get(status, "❓")

    def _escape_markdown(self, text: str) -> str:
        """
        Escape special characters for Telegram MarkdownV2.

        Special chars that need escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !
        """
        if not text:
            return ""

        special_chars = [
            "_",
            "*",
            "[",
            "]",
            "(",
            ")",
            "~",
            "`",
            ">",
            "#",
            "+",
            "-",
            "=",
            "|",
            "{",
            "}",
            ".",
            "!",
        ]

        escaped = str(text)
        for char in special_chars:
            escaped = escaped.replace(char, f"\\{char}")

        return escaped

    def _send_telegram_message(self, message: str) -> bool:
        """
        Send message via Telegram Bot API.

        Args:
            message: Formatted message to send

        Returns:
            bool: True if sent successfully
        """
        if not self.bot_token or not self.chat_id:
            self.logger.error("Cannot send Telegram message: missing credentials")
            return False

        url = f"{self.TELEGRAM_API_BASE}{self.bot_token}/sendMessage"

        payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "MarkdownV2"}

        try:
            response = self.http_client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                self.logger.debug("Telegram message sent successfully")
                return True
            else:
                self.logger.error(f"Telegram API error: {result.get('description')}")
                return False

        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"Telegram HTTP error: {e.response.status_code} - {e.response.text}"
            )
            return False
        except httpx.RequestError as e:
            self.logger.error(f"Telegram request error: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram message: {str(e)}")
            return False

    def __del__(self):
        """Cleanup HTTP client on destruction."""
        if hasattr(self, "http_client"):
            self.http_client.close()
