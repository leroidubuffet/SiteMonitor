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
            results = self._perform_site_checks(site_name, site_config, checkers)
            total_results += len(results)

        # Log summary
        self.logger.info(
            f"Completed {total_results} check(s) across {len(self.sites)} site(s)"
        )

        # Display metrics summary periodically
        if self.state_manager.state["global"]["total_checks"] % 10 == 0:
            self._log_metrics_summary()

    def _perform_site_checks(
        self, site_name: str, site_config: Dict[str, Any], checkers: Dict[str, Any]
    ) -> List[CheckResult]:
        """
        Perform checks for a specific site.

        Args:
            site_name: Name of the site
            site_config: Site configuration
            checkers: Dictionary of checkers for this site

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

                    # Send notifications (with site context)
                    self._send_notifications(result, previous_success, site_name)

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
                # Only send email/other notifications on state changes
                elif is_state_change or (
                    result.is_failure
                    and self.state_manager.get_consecutive_failures(
                        result.check_type, site_name
                    )
                    == 1
                ):
                    notifier.notify(result, site_name=site_name)
            except Exception as e:
                self.logger.error(f"[{site_name}] Failed to send notification: {e}")

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

        # Clean up checkers
        for checker in self.checkers.values():
            checker.cleanup()

        # Save final state
        self.state_manager.save_state()

        # Log final metrics
        self._log_metrics_summary()

        self.logger.info("Monitor stopped")

    def _handle_shutdown(self, signum=None, frame=None):
        """Handle shutdown signal."""
        self.logger.info("Shutdown signal received")
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
            "checkers": list(self.checkers.keys()),
            "notifiers": [n.__class__.__name__ for n in self.notifiers],
            "metrics": self.metrics_collector.get_all_metrics_summary(),
            "state": self.state_manager.get_summary(),
            "circuit_breaker": self.circuit_breaker.get_state()
            if self.circuit_breaker
            else None,
        }
