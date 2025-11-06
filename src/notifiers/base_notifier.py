"""Base notifier interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging

from ..checkers.base_checker import CheckResult


class BaseNotifier(ABC):
    """Abstract base class for all notifiers."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the notifier.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.enabled = self._is_enabled()

    @abstractmethod
    def _is_enabled(self) -> bool:
        """Check if this notifier is enabled."""
        pass

    @abstractmethod
    def notify(self, result: CheckResult, previous_result: CheckResult = None) -> bool:
        """
        Send notification for a check result.

        Args:
            result: Current check result
            previous_result: Previous check result (for state change detection)

        Returns:
            True if notification sent successfully
        """
        pass

    @abstractmethod
    def notify_batch(self, results: List[CheckResult]) -> bool:
        """
        Send notification for multiple check results.

        Args:
            results: List of check results

        Returns:
            True if notification sent successfully
        """
        pass

    def should_notify(
        self, result: CheckResult, previous_result: CheckResult = None
    ) -> bool:
        """
        Determine if a notification should be sent.

        Args:
            result: Current check result
            previous_result: Previous check result

        Returns:
            True if notification should be sent
        """
        if not self.enabled:
            return False

        # Always notify on first check if it's a failure
        if previous_result is None:
            return result.is_failure

        # Notify on state changes
        if previous_result.is_success and result.is_failure:
            return True  # Downtime alert

        if previous_result.is_failure and result.is_success:
            return True  # Recovery alert

        # Notify on new warnings
        if not previous_result.is_warning and result.is_warning:
            return True

        return False

    def format_result(self, result: CheckResult) -> str:
        """
        Format a check result for display.

        Args:
            result: Check result to format

        Returns:
            Formatted string
        """
        status_emoji = {
            "success": "✅",
            "warning": "⚠️",
            "failure": "❌",
            "error": "🔴",
            "timeout": "⏰",
        }.get(result.status.value, "❓")

        lines = [
            f"{status_emoji} {result.check_type.upper()} - {result.status.value.upper()}",
            f"Time: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Response Time: {result.response_time_ms:.0f}ms",
        ]

        if result.status_code:
            lines.append(f"HTTP Status: {result.status_code}")

        if result.error_message:
            lines.append(f"Error: {result.error_message}")

        if result.warning_message:
            lines.append(f"Warning: {result.warning_message}")

        return "\n".join(lines)
