"""Main monitor orchestrator that coordinates all components."""

import logging
import signal
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

from .checkers import AuthChecker, CheckResult, HealthChecker, UptimeChecker
from .notifiers import ConsoleNotifier, EmailNotifier, TelegramNotifier
from .scheduler import MonitorScheduler
from .storage import CredentialManager, StateManager
from .utils import CircuitBreaker, MetricsCollector, setup_logging


class Monitor:
    """Main monitoring orchestrator."""

    def __init__(
        self,
        config_path: str = "config/config.yaml",
        env_file: Optional[str] = None,
        telegram_debug: bool = False,
    ):
        """
        Initialize the monitor.

        Args:
            config_path: Path to configuration file
            env_file: Path to .env file
            telegram_debug: Override Telegram debug mode setting
        """
        # Load configuration
        self.config = self._load_config(config_path)

        # Override Telegram debug mode if specified
        if telegram_debug:
            if "notifications" not in self.config:
                self.config["notifications"] = {}
            if "telegram" not in self.config["notifications"]:
                self.config["notifications"]["telegram"] = {}
            self.config["notifications"]["telegram"]["debug_mode"] = True

        # Setup logging
        self.logger = setup_logging(self.config)
        self.logger.info("Multi-Site Monitor starting...")

        # Initialize components
        self.credential_manager = CredentialManager(env_file)
        self.state_manager = StateManager()
        self.metrics_collector = MetricsCollector()

        # Get list of sites from config
        self.sites = self.config.get("sites", [])
        if not self.sites:
            self.logger.error("No sites configured in config.yaml")
            sys.exit(1)

        self.logger.info(f"Configured to monitor {len(self.sites)} site(s)")

        # Initialize notifiers (shared across all sites)
        self.notifiers = self._initialize_notifiers()

        # Initialize scheduler
        self.scheduler = MonitorScheduler(self.config, blocking=False)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        self.running = False

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            print(f"Configuration loaded from {config_path}")
            return config
        except Exception as e:
            print(f"Failed to load configuration: {e}")
            sys.exit(1)

    def _initialize_checkers_for_site(
        self, site_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Initialize checkers for a specific site.

        Args:
            site_config: Site-specific configuration

        Returns:
            Dictionary of checkers for this site
        """
        checkers = {}
        enabled_checks = site_config.get("checks_enabled", [])
        site_name = site_config.get("name", "Unknown")

        if "uptime" in enabled_checks:
            # Create merged config with site-specific settings
            merged_config = self.config.copy()
            merged_config["monitoring"] = {"url": site_config.get("url")}
            merged_config["checks"] = {"uptime": site_config.get("uptime", {})}

            checkers["uptime"] = UptimeChecker(merged_config)
            self.logger.debug(f"[{site_name}] Uptime checker initialized")

        if "authentication" in enabled_checks:
            # Create merged config with site-specific settings
            merged_config = self.config.copy()
            merged_config["monitoring"] = {"url": site_config.get("url")}
            merged_config["checks"] = {
                "authentication": site_config.get("authentication", {})
            }

            checkers["authentication"] = AuthChecker(
                merged_config,
                credential_manager=self.credential_manager,
                site_config=site_config,
            )
            self.logger.debug(f"[{site_name}] Authentication checker initialized")

        if "health" in enabled_checks:
            # Health checker needs auth checker for session
            auth_checker = checkers.get("authentication")
            if auth_checker:
                merged_config = self.config.copy()
                merged_config["monitoring"] = {"url": site_config.get("url")}
                merged_config["checks"] = {"health": site_config.get("health", {})}

                checkers["health"] = HealthChecker(
                    merged_config, auth_checker=auth_checker
                )
                self.logger.debug(f"[{site_name}] Health checker initialized")
            else:
                self.logger.warning(
                    f"[{site_name}] Health checker requires authentication checker"
                )

        return checkers

    def _initialize_notifiers(self) -> List[Any]:
        """Initialize all enabled notifiers."""
        notifiers = []

        # Console notifier
        console_notifier = ConsoleNotifier(self.config)
        if console_notifier.enabled:
            notifiers.append(console_notifier)
            self.logger.info("Console notifier initialized")

        # Email notifier
        email_notifier = EmailNotifier(self.config, self.credential_manager)
        if email_notifier.enabled:
            notifiers.append(email_notifier)
            self.logger.info("Email notifier initialized")

        # Telegram notifier
        telegram_notifier = TelegramNotifier(self.config, self.credential_manager)
        if telegram_notifier.enabled:
            notifiers.append(telegram_notifier)
            mode_str = "DEBUG" if telegram_notifier.debug_mode else "REGULAR"
            self.logger.info(f"Telegram notifier initialized ({mode_str} mode)")

        return notifiers

    def perform_checks(self):
        """Perform all enabled checks for all sites."""
        self.logger.info(f"Starting monitoring checks for {len(self.sites)} site(s)...")
        total_results = 0
        all_results_for_batch = []  # Collect all results for batch notification

        # Loop through each site
        for site_config in self.sites:
            site_name = site_config.get("name", "Unknown")
            self.logger.info(f"[{site_name}] Starting checks...")

            # Check per-site circuit breaker
            cb_config = self.config.get("circuit_breaker", {})
            site_state = self.state_manager._get_site_state(site_name)
            circuit_breaker_state = site_state.get("circuit_breaker", {})

            if cb_config.get("enabled", True) and circuit_breaker_state.get(
                "is_open", False
            ):
                self.logger.warning(
                    f"[{site_name}] Circuit breaker is OPEN, skipping checks"
                )
                continue

            # Initialize checkers for this site
            checkers = self._initialize_checkers_for_site(site_config)

            # Perform checks for this site
            results = self._perform_site_checks(
                site_name, site_config, checkers, all_results_for_batch
            )
            total_results += len(results)

        # Send batch notifications if we have results
        if all_results_for_batch:
            self._send_batch_notifications(all_results_for_batch)

        # Log summary
        self.logger.info(
            f"Completed {total_results} check(s) across {len(self.sites)} site(s)"
        )

        # Display metrics summary periodically
        if self.state_manager.state["global"]["total_checks"] % 10 == 0:
            self._log_metrics_summary()

    def _perform_site_checks(
        self,
        site_name: str,
        site_config: Dict[str, Any],
        checkers: Dict[str, Any],
        batch_results: List = None,
    ) -> List[CheckResult]:
        """
        Perform checks for a specific site.

        Args:
            site_name: Name of the site
            site_config: Site configuration
            checkers: Dictionary of checkers for this site
            batch_results: Optional list to collect results for batch notification

        Returns:
            List of check results
        """
        results = []

        # Perform checks in order: uptime -> auth -> health
        check_order = ["uptime", "authentication", "health"]

        for check_type in check_order:
            if check_type in checkers:
                checker = checkers[check_type]

                try:
                    # Skip health check if auth failed
                    if check_type == "health":
                        auth_result = next(
                            (r for r in results if r.check_type == "authentication"),
                            None,
                        )
                        if auth_result and not auth_result.success:
                            self.logger.warning(
                                f"[{site_name}] Skipping health check due to authentication failure"
                            )
                            continue

                    # Perform the check
                    self.logger.debug(f"[{site_name}] Performing {check_type} check...")

                    # Call check with site_name for per-site state
                    if check_type == "authentication":
                        result = checker.check(site_name=site_name)
                    else:
                        result = checker.check()

                    results.append(result)

                    # Record metrics
                    self.metrics_collector.record_check_result(
                        result.success, result.response_time_ms
                    )

                    # Get previous result for comparison
                    previous_result_dict = self.state_manager.get_last_result(
                        check_type, site_name
                    )
                    previous_success = True
                    if previous_result_dict:
                        previous_success = previous_result_dict.get("success", True)

                    # Record in state manager (with site name)
                    self.state_manager.record_result(result, site_name)

                    # Collect for batch notifications if batch_results list provided
                    if batch_results is not None:
                        # Get previous result for notifiers to check state changes
                        previous_result = None
                        if previous_result_dict:
                            from .checkers import CheckStatus

                            status_str = previous_result_dict.get(
                                "status", "SUCCESS"
                            ).upper()
                            previous_result = CheckResult(
                                check_type=previous_result_dict.get("check_type", ""),
                                timestamp=datetime.fromisoformat(
                                    previous_result_dict.get("timestamp", "")
                                ),
                                status=CheckStatus[status_str],
                                success=previous_result_dict.get("success", True),
                            )
                        batch_results.append((result, previous_result, site_name))

                    # Always send to console immediately (non-batch)
                    self._send_console_notification(result, site_name)

                except Exception as e:
                    self.logger.error(
                        f"[{site_name}] Error during {check_type} check: {e}",
                        exc_info=True,
                    )

                    # Update circuit breaker on failure
                    cb_config = self.config.get("circuit_breaker", {})
                    if cb_config.get("enabled", True):
                        site_state = self.state_manager._get_site_state(site_name)
                        failure_threshold = cb_config.get("failure_threshold", 5)
                        if (
                            site_state["circuit_breaker"]["failure_count"]
                            >= failure_threshold
                        ):
                            site_state["circuit_breaker"]["is_open"] = True
                            self.logger.warning(f"[{site_name}] Circuit breaker OPENED")

        return results

    def _send_notifications(
        self, result: CheckResult, previous_success: bool, site_name: str
    ):
        """
        Send notifications for a check result.

        Args:
            result: Check result
            previous_success: Whether previous check was successful
            site_name: Name of the site being checked
        """
        # Determine if this is a state change
        is_state_change = (previous_success and result.is_failure) or (
            not previous_success and result.is_success
        )

        for notifier in self.notifiers:
            try:
                # Always show in console
                if isinstance(notifier, ConsoleNotifier):
                    notifier.notify(result, site_name=site_name)
                # For other notifiers, check if they want this notification
                # (TelegramNotifier in debug mode will return True from should_notify)
                else:
                    # Get previous result for state change detection
                    previous_result_dict = self.state_manager.get_last_result(
                        result.check_type, site_name
                    )
                    previous_result = None
                    if previous_result_dict:
                        # Reconstruct a minimal CheckResult for comparison
                        from .checkers import CheckStatus

                        status_str = previous_result_dict.get(
                            "status", "SUCCESS"
                        ).upper()
                        previous_result = CheckResult(
                            check_type=previous_result_dict.get("check_type", ""),
                            timestamp=datetime.fromisoformat(
                                previous_result_dict.get("timestamp", "")
                            ),
                            status=CheckStatus[status_str],
                            success=previous_result_dict.get("success", True),
                        )

                    # Let the notifier decide if it should notify
                    # (handles debug mode, state changes, etc.)
                    if notifier.should_notify(result, previous_result):
                        notifier.notify(result, previous_result, site_name=site_name)
            except Exception as e:
                self.logger.error(
                    f"[{site_name}] Failed to send notification: {e}", exc_info=True
                )

    def _send_console_notification(self, result: CheckResult, site_name: str):
        """Send notification to console only."""
        for notifier in self.notifiers:
            if isinstance(notifier, ConsoleNotifier):
                try:
                    notifier.notify(result, site_name=site_name)
                except Exception as e:
                    self.logger.error(f"Console notification failed: {e}")
                break

    def _send_batch_notifications(self, batch_results: List):
        """
        Send batch notifications to all enabled notifiers (except console).

        Args:
            batch_results: List of (result, previous_result, site_name) tuples
        """
        for notifier in self.notifiers:
            # Skip console (already notified individually)
            if isinstance(notifier, ConsoleNotifier):
                continue

            try:
                # Filter results that this notifier wants to be notified about
                filtered_results = []
                for result, previous_result, site_name in batch_results:
                    if notifier.should_notify(result, previous_result):
                        filtered_results.append((result, previous_result, site_name))

                # Send batch if we have results to notify
                if filtered_results:
                    # Check if notifier supports batch notifications
                    if hasattr(notifier, "batch_enabled") and notifier.batch_enabled:
                        notifier.notify_batch(filtered_results)
                    else:
                        # Fall back to individual notifications
                        for result, previous_result, site_name in filtered_results:
                            notifier.notify(
                                result, previous_result, site_name=site_name
                            )
            except Exception as e:
                self.logger.error(
                    f"Batch notification failed for {notifier.__class__.__name__}: {e}",
                    exc_info=True,
                )

    def _send_startup_notification(self, interval_minutes: int):
        """Send a startup notification to Telegram (if enabled and not in debug mode)."""
        for notifier in self.notifiers:
            # Only send to Telegram notifier
            if notifier.__class__.__name__ == "TelegramNotifier":
                # Only send startup notification in regular mode (not debug mode)
                if not hasattr(notifier, "debug_mode") or not notifier.debug_mode:
                    try:
                        # Create startup message
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        site_list = "\n".join(
                            [
                                f"  • {site.get('name', 'Unknown')}"
                                for site in self.sites
                            ]
                        )

                        message = (
                            f"🚀 *Monitor Started*\n\n"
                            f"📊 Monitoring {len(self.sites)} sites:\n{site_list}\n\n"
                            f"⏱ Check interval: `{interval_minutes} minutes`\n"
                            f"🕐 Started at: `{timestamp}`\n\n"
                            f"_Regular mode: You'll only receive alerts for failures and recoveries_"
                        )

                        # Send via Telegram API directly
                        notifier._send_telegram_message(message)
                        self.logger.info("Startup notification sent to Telegram")
                    except Exception as e:
                        self.logger.error(f"Failed to send startup notification: {e}")

    def _log_metrics_summary(self):
        """Log metrics summary."""
        metrics_summary = self.metrics_collector.get_all_metrics_summary()
        availability = metrics_summary.get("availability", {})

        self.logger.info(
            f"Metrics Summary - "
            f"Availability: {availability.get('availability_percentage', 0):.2f}%, "
            f"Total Checks: {availability.get('total_checks', 0)}, "
            f"Failed: {availability.get('failed_checks', 0)}"
        )

    def start(self):
        """Start the monitor."""
        self.running = True

        # Validate credentials for all sites
        for site_config in self.sites:
            site_name = site_config.get("name", "Unknown")
            credential_key = site_config.get("credential_key")

            if credential_key:
                creds = self.credential_manager.get_credentials_by_key(credential_key)
                if not creds.get("username") or not creds.get("password"):
                    self.logger.warning(
                        f"[{site_name}] Credentials not configured for '{credential_key}' - authentication checks will fail"
                    )
                else:
                    self.logger.info(
                        f"[{site_name}] Credentials validated for '{credential_key}'"
                    )

        # Schedule monitoring job
        interval_minutes = self.config.get("monitoring", {}).get("interval_minutes", 15)
        self.scheduler.add_interval_job(
            "monitor_checks", self.perform_checks, minutes=interval_minutes
        )

        # Schedule daily report if enabled
        daily_config = self.config.get("reporting", {}).get("daily_digest", {})
        if daily_config.get("enabled", False):
            hour = daily_config.get("send_at_hour", 9)
            self.scheduler.add_cron_job(
                "daily_report", self._send_daily_report, hour=hour, minute=0
            )

        # Start scheduler
        self.scheduler.start()

        # Perform initial check
        self.logger.info("Performing initial check...")
        self.perform_checks()

        # Send startup notification
        self._send_startup_notification(interval_minutes)

        self.logger.info(f"Monitor started - checking every {interval_minutes} minutes")
        self.logger.info("Press Ctrl+C to stop")

        # Keep running
        try:
            while self.running:
                import time

                time.sleep(1)
        except KeyboardInterrupt:
            self._handle_shutdown()

    def stop(self):
        """Stop the monitor."""
        self.logger.info("Stopping monitor...")
        self.running = False

        # Shutdown scheduler
        if self.scheduler:
            self.scheduler.shutdown()

        # Clean up checkers (if they exist as instance variables)
        # Note: In multi-site architecture, checkers are created per-check-cycle
        # and automatically cleaned up when they go out of scope
        if hasattr(self, 'checkers') and self.checkers:
            for checker in self.checkers.values():
                try:
                    checker.cleanup()
                except Exception as e:
                    self.logger.error(f"Error cleaning up checker: {e}")

        # Save final state
        self.state_manager.save_state()

        # Log final metrics
        self._log_metrics_summary()

        self.logger.info("Monitor stopped")

    def _send_shutdown_notification(self):
        """Send a shutdown notification to Telegram (if enabled)."""
        for notifier in self.notifiers:
            # Only send to Telegram notifier
            if notifier.__class__.__name__ == "TelegramNotifier":
                try:
                    # Get final stats
                    metrics_summary = self.metrics_collector.get_all_metrics_summary()
                    availability = metrics_summary.get("availability", {})
                    total_checks = availability.get("total_checks", 0)
                    availability_pct = availability.get("availability_percentage", 0)

                    # Create shutdown message
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    message = (
                        f"🛑 *Monitor Stopped*\n\n"
                        f"📊 Monitoring {len(self.sites)} sites\n"
                        f"⏹ Total checks performed: `{total_checks}`\n"
                        f"📈 Overall availability: `{availability_pct:.2f}%`\n\n"
                        f"🕐 Stopped at: `{timestamp}`"
                    )

                    # Send via Telegram API directly
                    notifier._send_telegram_message(message)
                    self.logger.info("Shutdown notification sent to Telegram")
                except Exception as e:
                    self.logger.error(f"Failed to send shutdown notification: {e}")

    def _handle_shutdown(self, signum=None, frame=None):
        """Handle shutdown signal."""
        self.logger.info("Shutdown signal received")

        # Send shutdown notification before stopping
        self._send_shutdown_notification()

        self.stop()
        sys.exit(0)

    def _send_daily_report(self):
        """Send daily status report."""
        self.logger.info("Generating daily report...")

        # Get metrics summary
        metrics_summary = self.metrics_collector.get_all_metrics_summary()
        state_summary = self.state_manager.get_summary()

        # Create report content
        report = f"""
Daily InfoRuta Monitor Report
{"=" * 40}
Date: {datetime.now().strftime("%Y-%m-%d")}

Availability: {metrics_summary["availability"]["availability_percentage"]:.2f}%
Total Checks: {metrics_summary["availability"]["total_checks"]}
Failed Checks: {metrics_summary["availability"]["failed_checks"]}
Success Rate: {metrics_summary["availability"]["success_rate"]:.2f}%

Current Status:
"""

        for check_type, status in state_summary["current_status"].items():
            report += f"  {check_type}: {status['status']}\n"

        # Send via email if configured
        for notifier in self.notifiers:
            if isinstance(notifier, EmailNotifier):
                try:
                    # Create a pseudo check result for the report
                    from .checkers import CheckResult, CheckStatus

                    report_result = CheckResult(
                        check_type="daily_report",
                        timestamp=datetime.now(),
                        status=CheckStatus.SUCCESS,
                        success=True,
                        response_time_ms=0,
                        details={"report": report},
                    )
                    notifier.notify(report_result)
                    self.logger.info("Daily report sent via email")
                except Exception as e:
                    self.logger.error(f"Failed to send daily report: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status."""
        return {
            "running": self.running,
            "sites": [site.get("name", "Unknown") for site in self.sites],
            "notifiers": [n.__class__.__name__ for n in self.notifiers],
            "metrics": self.metrics_collector.get_all_metrics_summary(),
            "state": self.state_manager.get_summary(),
        }
