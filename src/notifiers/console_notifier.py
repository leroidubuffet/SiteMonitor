"""Console notifier for terminal output."""

import sys
from datetime import datetime
from typing import Any, Dict, List

from colorama import Back, Fore, Style, init

from ..checkers.base_checker import CheckResult, CheckStatus
from .base_notifier import BaseNotifier

# Initialize colorama for cross-platform colored output
init(autoreset=True)


class ConsoleNotifier(BaseNotifier):
    """Display notifications in the console."""

    def _is_enabled(self) -> bool:
        """Check if console notifications are enabled."""
        return (
            self.config.get("notifications", {}).get("console", {}).get("enabled", True)
        )

    def notify(
        self,
        result: CheckResult,
        previous_result: CheckResult = None,
        site_name: str = None,
    ) -> bool:
        """
        Display notification in console.

        Args:
            result: Current check result
            previous_result: Previous check result
            site_name: Name of the site being checked

        Returns:
            True if displayed successfully
        """
        if not self.enabled:
            return False

        try:
            # Get configuration
            show_timestamps = (
                self.config.get("notifications", {})
                .get("console", {})
                .get("show_timestamps", True)
            )
            colored_output = (
                self.config.get("notifications", {})
                .get("console", {})
                .get("colored_output", True)
            )

            # Build notification message
            message = self._format_console_message(
                result, previous_result, colored_output, site_name
            )

            # Add timestamp if enabled
            if show_timestamps:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if colored_output:
                    message = f"{Fore.CYAN}[{timestamp}]{Style.RESET_ALL} {message}"
                else:
                    message = f"[{timestamp}] {message}"

            # Print to console
            print(message)
            sys.stdout.flush()

            return True

        except Exception as e:
            self.logger.error(f"Failed to display console notification: {e}")
            return False

    def notify_batch(self, results: List[CheckResult]) -> bool:
        """
        Display multiple results in console.

        Args:
            results: List of check results

        Returns:
            True if displayed successfully
        """
        if not self.enabled or not results:
            return False

        try:
            print("\n" + "=" * 60)
            print("BATCH CHECK RESULTS")
            print("=" * 60)

            for result in results:
                self.notify(result)

            print("=" * 60 + "\n")
            sys.stdout.flush()

            return True

        except Exception as e:
            self.logger.error(f"Failed to display batch console notification: {e}")
            return False

    def _format_console_message(
        self,
        result: CheckResult,
        previous_result: CheckResult = None,
        colored: bool = True,
        site_name: str = None,
    ) -> str:
        """
        Format a message for console display.

        Args:
            result: Check result
            previous_result: Previous result
            colored: Use colored output
            site_name: Name of the site

        Returns:
            Formatted message string
        """
        # Determine message type
        is_state_change = False
        state_change_type = None

        if previous_result:
            if previous_result.is_success and result.is_failure:
                is_state_change = True
                state_change_type = "DOWNTIME"
            elif previous_result.is_failure and result.is_success:
                is_state_change = True
                state_change_type = "RECOVERY"

        # Build message components
        check_type = result.check_type.upper()
        status = result.status.value.upper()
        response_time = f"{result.response_time_ms:.0f}ms"

        # Format site name
        if site_name:
            if colored:
                site_label = f"{Fore.MAGENTA}[{site_name}]{Style.RESET_ALL}"
            else:
                site_label = f"[{site_name}]"
        else:
            site_label = ""

        # Apply colors if enabled
        if colored:
            # Status colors
            status_colors = {
                CheckStatus.SUCCESS: Fore.GREEN,
                CheckStatus.WARNING: Fore.YELLOW,
                CheckStatus.FAILURE: Fore.RED,
                CheckStatus.ERROR: Fore.RED + Style.BRIGHT,
                CheckStatus.TIMEOUT: Fore.MAGENTA,
            }

            status_color = status_colors.get(result.status, Fore.WHITE)

            # Format message parts with colors
            check_type_formatted = f"{Fore.CYAN}{check_type}{Style.RESET_ALL}"
            status_formatted = f"{status_color}{status}{Style.RESET_ALL}"

            # Response time coloring based on thresholds
            warning_threshold = self.config.get("performance", {}).get(
                "warning_threshold_ms", 3000
            )
            critical_threshold = self.config.get("performance", {}).get(
                "critical_threshold_ms", 10000
            )

            if result.response_time_ms > critical_threshold:
                response_time_formatted = f"{Fore.RED}{response_time}{Style.RESET_ALL}"
            elif result.response_time_ms > warning_threshold:
                response_time_formatted = (
                    f"{Fore.YELLOW}{response_time}{Style.RESET_ALL}"
                )
            else:
                response_time_formatted = (
                    f"{Fore.GREEN}{response_time}{Style.RESET_ALL}"
                )

            # State change highlighting
            if is_state_change:
                if state_change_type == "DOWNTIME":
                    state_msg = (
                        f"{Back.RED}{Fore.WHITE} ⚠ SITE DOWN ⚠ {Style.RESET_ALL}"
                    )
                elif state_change_type == "RECOVERY":
                    state_msg = (
                        f"{Back.GREEN}{Fore.WHITE} ✓ SITE RECOVERED ✓ {Style.RESET_ALL}"
                    )
                else:
                    state_msg = ""
            else:
                state_msg = ""

            # Status icon
            status_icon = {
                CheckStatus.SUCCESS: "✓",
                CheckStatus.WARNING: "⚠",
                CheckStatus.FAILURE: "✗",
                CheckStatus.ERROR: "✗",
                CheckStatus.TIMEOUT: "⏰",
            }.get(result.status, "?")

        else:
            # Plain text formatting
            check_type_formatted = check_type
            status_formatted = status
            response_time_formatted = response_time
            state_msg = f" [{state_change_type}]" if is_state_change else ""

            status_icon = {
                CheckStatus.SUCCESS: "[OK]",
                CheckStatus.WARNING: "[WARN]",
                CheckStatus.FAILURE: "[FAIL]",
                CheckStatus.ERROR: "[ERROR]",
                CheckStatus.TIMEOUT: "[TIMEOUT]",
            }.get(result.status, "[?]")

        # Build main message
        message_parts = []

        # Add site label first if present
        if site_label:
            message_parts.append(site_label)

        # Add state message if present
        if state_msg:
            message_parts.append(state_msg)

        # Add main status
        message_parts.append(
            f"{status_icon} {check_type_formatted}: {status_formatted}"
        )
        message_parts.append(f"({response_time_formatted})")

        if result.status_code:
            message_parts.append(f"HTTP {result.status_code}")

        message = " ".join(message_parts)

        # Add error/warning details on separate lines
        if result.error_message:
            if colored:
                error_line = (
                    f"  {Fore.RED}Error: {result.error_message}{Style.RESET_ALL}"
                )
            else:
                error_line = f"  Error: {result.error_message}"
            message += "\n" + error_line

        if result.warning_message:
            if colored:
                warning_line = (
                    f"  {Fore.YELLOW}Warning: {result.warning_message}{Style.RESET_ALL}"
                )
            else:
                warning_line = f"  Warning: {result.warning_message}"
            message += "\n" + warning_line

        return message
