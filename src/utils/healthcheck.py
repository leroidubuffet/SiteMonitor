"""
Healthcheck.io integration for monitoring the monitor.

Sends heartbeat pings to Healthchecks.io to detect when the monitor
stops running or hangs. This provides external validation that the
monitor is working correctly.

Usage:
    1. Sign up at https://healthchecks.io (free tier: 20 checks)
    2. Create a check and get the ping URL
    3. Add HEALTHCHECK_PING_URL to your .env file
    4. Enable in config.yaml

The monitor will:
    - Send a heartbeat ping after each successful check cycle
    - If no ping received within timeout → you get alerted

This operates as a "dead man's switch" - continuous heartbeats indicate
the monitor is alive. If heartbeats stop, you get alerted.
"""

import logging
from typing import Optional

import httpx


class HealthcheckMonitor:
    """
    Healthcheck.io integration for external monitoring.

    This sends heartbeat pings to Healthchecks.io to ensure the monitor
    is running and performing checks. If pings stop, you get notified.
    """

    def __init__(self, ping_url: Optional[str] = None, enabled: bool = True):
        """
        Initialize healthcheck monitor.

        Args:
            ping_url: Full ping URL from Healthchecks.io (e.g., https://hc-ping.com/your-uuid)
            enabled: Whether healthcheck pings are enabled

        Raises:
            ValueError: If ping_url is not provided.
        """
        if not ping_url:
            raise ValueError("HEALTHCHECK_PING_URL is not configured!")

        self.ping_url = ping_url
        self.enabled = enabled
        self.logger = logging.getLogger(self.__class__.__name__)

    def ping_start(self) -> bool:
        """
        Send a 'start' signal to indicate monitor is starting.

        This is useful to distinguish between a fresh start and a restart
        after a crash.

        Returns:
            True if ping sent successfully
        """
        if not self.enabled:
            return False

        return self._send_ping("/start", "Monitor starting")

    def ping_success(self, message: str = None) -> bool:
        """
        Send a heartbeat ping after successful check cycle.

        This is the main "dead man's switch" signal. Call this after each
        complete check cycle to indicate the monitor is alive and working.
        If this stops being called, healthchecks.io will alert you.

        Args:
            message: Optional message to include (e.g., "Checked 5 sites")

        Returns:
            True if ping sent successfully
        """
        if not self.enabled:
            return False

        return self._send_ping("", message or "Check cycle completed")

    def ping_fail(self, message: str = None) -> bool:
        """
        Send a 'fail' signal when checks fail.

        Use this when the monitor is running but checks are failing
        (e.g., all sites down, authentication failures).

        Args:
            message: Optional failure message

        Returns:
            True if ping sent successfully
        """
        if not self.enabled:
            return False

        return self._send_ping("/fail", message or "Check cycle failed")

    def ping_exit(self, exit_status: int = 0, message: str = None) -> bool:
        """
        Send an exit status signal when the monitor is shutting down.

        This reports the script's exit status (0-255 integer). Healthchecks.io
        interprets 0 as success and all other values as failure. Use this for
        graceful shutdowns to avoid false alerts.

        Args:
            exit_status: Exit code (0 = success, 1-255 = failure)
            message: Optional shutdown message

        Returns:
            True if ping sent successfully
        """
        if not self.enabled:
            return False

        if not 0 <= exit_status <= 255:
            self.logger.warning(
                f"Invalid exit status {exit_status}, must be 0-255. Using 1 (failure)."
            )
            exit_status = 1

        return self._send_ping(f"/{exit_status}", message or "Monitor shutting down")

    def _send_ping(self, suffix: str = "", message: str = None) -> bool:
        """
        Send ping to Healthchecks.io.

        Args:
            suffix: URL suffix ("/start", "/success", "/fail", "/<exit_status>")
            message: Optional message to include in ping body

        Returns:
            True if ping sent successfully
        """
        if not self.ping_url:
            return False

        url = f"{self.ping_url.rstrip('/')}{suffix}"

        try:
            # Send ping with optional message body
            # Timeout is short (5s) since this is just a heartbeat
            response = httpx.post(
                url,
                data=message.encode("utf-8") if message else None,
                timeout=5.0,
            )
            response.raise_for_status()

            self.logger.debug(f"Healthcheck ping sent: {suffix or 'success'}")
            return True

        except httpx.HTTPStatusError as e:
            self.logger.warning(
                f"Healthcheck ping failed: HTTP {e.response.status_code}"
            )
            return False
        except httpx.RequestError as e:
            self.logger.warning(f"Healthcheck ping failed: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending healthcheck ping: {str(e)}")
            return False


def create_healthcheck_monitor(
    ping_url: Optional[str] = None, enabled: bool = True
) -> HealthcheckMonitor:
    """
    Factory function to create a HealthcheckMonitor instance.

    Args:
        ping_url: Ping URL from Healthchecks.io
        enabled: Whether to enable healthcheck pings

    Returns:
        HealthcheckMonitor instance

    Raises:
        ValueError: If ping_url is not provided.
    """
    if not ping_url:
        raise ValueError("HEALTHCHECK_PING_URL is not configured!")
    return HealthcheckMonitor(ping_url=ping_url, enabled=enabled)
