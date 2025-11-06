"""Main monitor orchestrator that coordinates all components."""

import logging
import signal
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime
import yaml

from .checkers import UptimeChecker, AuthChecker, HealthChecker, CheckResult
from .notifiers import ConsoleNotifier, EmailNotifier
from .storage import CredentialManager, StateManager
from .utils import setup_logging, MetricsCollector, CircuitBreaker
from .scheduler import MonitorScheduler


class Monitor:
    """Main monitoring orchestrator."""

    def __init__(
        self, config_path: str = "config/config.yaml", env_file: Optional[str] = None
    ):
        """
        Initialize the monitor.

        Args:
            config_path: Path to configuration file
            env_file: Path to .env file
        """
        # Load configuration
        self.config = self._load_config(config_path)

        # Setup logging
        self.logger = setup_logging(self.config)
        self.logger.info("InfoRuta Monitor starting...")

        # Initialize components
        self.credential_manager = CredentialManager(env_file)
        self.state_manager = StateManager()
        self.metrics_collector = MetricsCollector()

        # Initialize circuit breaker if enabled
        cb_config = self.config.get("circuit_breaker", {})
        if cb_config.get("enabled", True):
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=cb_config.get("failure_threshold", 5),
                recovery_timeout=cb_config.get("recovery_timeout_minutes", 30) * 60,
            )
        else:
            self.circuit_breaker = None

        # Initialize checkers
        self.checkers = self._initialize_checkers()

        # Initialize notifiers
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

    def _initialize_checkers(self) -> Dict[str, Any]:
        """Initialize all enabled checkers."""
        checkers = {}
        enabled_checks = self.config.get("checks", {}).get("enabled", [])

        if "uptime" in enabled_checks:
            checkers["uptime"] = UptimeChecker(self.config)
            self.logger.info("Uptime checker initialized")

        if "authentication" in enabled_checks:
            checkers["authentication"] = AuthChecker(
                self.config, credential_manager=self.credential_manager
            )
            self.logger.info("Authentication checker initialized")

        if "health" in enabled_checks:
            # Health checker needs auth checker for session
            auth_checker = checkers.get("authentication")
            if auth_checker:
                checkers["health"] = HealthChecker(
                    self.config, auth_checker=auth_checker
                )
                self.logger.info("Health checker initialized")
            else:
                self.logger.warning("Health checker requires authentication checker")

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

        return notifiers

    def perform_checks(self):
        """Perform all enabled checks."""
        self.logger.info("Starting monitoring checks...")
        results = []

        # Check if circuit breaker is open
        if self.circuit_breaker and self.circuit_breaker.is_open:
            self.logger.warning("Circuit breaker is OPEN, skipping checks")
            return

        # Perform checks in order: uptime -> auth -> health
        check_order = ["uptime", "authentication", "health"]

        for check_type in check_order:
            if check_type in self.checkers:
                checker = self.checkers[check_type]

                try:
                    # Skip health check if auth failed
                    if check_type == "health":
                        auth_result = next(
                            (r for r in results if r.check_type == "authentication"),
                            None,
                        )
                        if auth_result and not auth_result.success:
                            self.logger.warning(
                                "Skipping health check due to authentication failure"
                            )
                            continue

                    # Perform the check
                    self.logger.info(f"Performing {check_type} check...")

                    if self.circuit_breaker:
                        result = self.circuit_breaker.call(checker.check)
                    else:
                        result = checker.check()

                    results.append(result)

                    # Record metrics
                    self.metrics_collector.record_check_result(
                        result.success, result.response_time_ms
                    )

                    # Get previous result for comparison
                    previous_result_dict = self.state_manager.get_last_result(
                        check_type
                    )
                    previous_result = None
                    if previous_result_dict:
                        # Convert dict back to CheckResult for comparison
                        # This is simplified - in production you'd deserialize properly
                        previous_success = previous_result_dict.get("success", True)
                    else:
                        previous_success = True

                    # Record in state manager
                    self.state_manager.record_result(result)

                    # Send notifications
                    self._send_notifications(result, previous_success)

                except Exception as e:
                    self.logger.error(
                        f"Error during {check_type} check: {e}", exc_info=True
                    )

                    # Update circuit breaker on failure
                    if self.circuit_breaker:
                        self.circuit_breaker._on_failure()

        # Log summary
        self.logger.info(f"Completed {len(results)} checks")

        # Display metrics summary periodically
        if self.state_manager.state["statistics"]["total_checks"] % 10 == 0:
            self._log_metrics_summary()

    def _send_notifications(self, result: CheckResult, previous_success: bool):
        """Send notifications for a check result."""
        # Determine if this is a state change
        is_state_change = (previous_success and result.is_failure) or (
            not previous_success and result.is_success
        )

        for notifier in self.notifiers:
            try:
                # Always show in console
                if isinstance(notifier, ConsoleNotifier):
                    notifier.notify(result)
                # Only send email/other notifications on state changes
                elif is_state_change or (
                    result.is_failure
                    and self.state_manager.get_consecutive_failures(result.check_type)
                    == 1
                ):
                    notifier.notify(result)
            except Exception as e:
                self.logger.error(f"Failed to send notification: {e}")

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

        # Validate credentials
        cred_status = self.credential_manager.validate_credentials()
        self.logger.info(f"Credential status: {cred_status}")

        if not cred_status.get("inforuta_configured"):
            self.logger.warning(
                "InfoRuta credentials not configured - authentication checks will fail"
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
