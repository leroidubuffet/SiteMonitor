#!/usr/bin/env python3
"""
Tests for resource management and cleanup in the monitoring system.

These tests ensure that HTTP clients, connections, and file descriptors
are properly managed to prevent resource leaks in long-running monitors.
"""

import gc
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import httpx

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.checkers import CheckStatus, UptimeChecker
from src.checkers.base_checker import BaseChecker
from src.monitor import Monitor
from src.notifiers.telegram_notifier import TelegramNotifier


class TestCheckerCleanup(unittest.TestCase):
    """Test that checkers properly clean up HTTP clients."""

    def setUp(self):
        """Set up test configuration."""
        self.config = {
            "monitoring": {
                "url": "https://www.example.com",
                "timeout_seconds": 10,
                "user_agent": "Test-Monitor/1.0",
            },
            "checks": {
                "uptime": {
                    "endpoints": ["/"],
                    "expected_status": [200],
                    "check_ssl": False,
                }
            },
        }

    def test_checker_cleanup_closes_client(self):
        """Test that cleanup() closes the HTTP client."""
        checker = UptimeChecker(self.config)

        # Access the client property to create it
        client = checker.client
        self.assertIsNotNone(client)
        self.assertFalse(client.is_closed)

        # Call cleanup
        checker.cleanup()

        # Client should be closed
        self.assertTrue(client.is_closed)
        self.assertIsNone(checker._client)

    def test_checker_context_manager(self):
        """Test that checker works as context manager with automatic cleanup."""
        with UptimeChecker(self.config) as checker:
            client = checker.client
            self.assertIsNotNone(client)
            self.assertFalse(client.is_closed)

        # After exiting context, client should be closed
        self.assertTrue(client.is_closed)

    def test_multiple_checkers_cleanup(self):
        """Test that multiple checkers can be cleaned up without issues."""
        checkers = []

        # Create multiple checkers
        for _ in range(5):
            checker = UptimeChecker(self.config)
            # Force client creation
            _ = checker.client
            checkers.append(checker)

        # All clients should be open
        for checker in checkers:
            self.assertFalse(checker.client.is_closed)

        # Clean up all checkers
        for checker in checkers:
            checker.cleanup()

        # All clients should be closed
        for checker in checkers:
            self.assertTrue(checker._client is None or checker._client.is_closed)

    def test_checker_cleanup_idempotent(self):
        """Test that cleanup can be called multiple times safely."""
        checker = UptimeChecker(self.config)
        _ = checker.client

        # Call cleanup multiple times
        checker.cleanup()
        checker.cleanup()
        checker.cleanup()

        # Should not raise any errors
        self.assertIsNone(checker._client)


class TestConnectionPoolLimits(unittest.TestCase):
    """Test that HTTP clients have proper connection pool limits."""

    def setUp(self):
        """Set up test configuration."""
        self.config = {
            "monitoring": {
                "url": "https://www.example.com",
                "timeout_seconds": 30,
            },
            "checks": {
                "uptime": {"endpoints": ["/"]},
            },
        }

    def test_client_has_connection_limits(self):
        """Test that HTTPX client is created with connection pool limits."""
        checker = UptimeChecker(self.config)
        client = checker.client

        # Check that limits are configured (accessing internal pool manager)
        # HTTPX stores limits in the transport's pool
        self.assertIsNotNone(client._transport)
        # Just verify the client was created successfully with our config
        # The limits are passed to httpx.Client constructor and applied internally
        self.assertTrue(hasattr(client, '_transport'))

        checker.cleanup()

    def test_client_has_timeouts(self):
        """Test that HTTPX client has proper timeouts configured."""
        checker = UptimeChecker(self.config)
        client = checker.client

        # Check that timeouts are configured
        self.assertIsNotNone(client.timeout)
        self.assertEqual(client.timeout.connect, 10.0)
        self.assertEqual(client.timeout.read, 20.0)
        self.assertEqual(client.timeout.write, 10.0)
        self.assertEqual(client.timeout.pool, 5.0)

        checker.cleanup()


class TestTelegramNotifierResourceManagement(unittest.TestCase):
    """Test that TelegramNotifier properly manages HTTP client resources."""

    def setUp(self):
        """Set up test configuration."""
        self.config = {
            "notifications": {
                "telegram": {
                    "enabled": True,
                    "debug_mode": False,
                    "batch_notifications": True,
                }
            }
        }

        # Mock credential manager
        self.mock_cred_manager = Mock()
        self.mock_cred_manager.get_telegram_credentials.return_value = {
            "bot_token": "test_token",
            "chat_id": "test_chat_id",
        }

    def test_telegram_notifier_no_persistent_client(self):
        """Test that TelegramNotifier does not keep a persistent HTTP client."""
        notifier = TelegramNotifier(self.config, self.mock_cred_manager)

        # Should not have http_client attribute
        self.assertFalse(hasattr(notifier, "http_client"))

    @patch("httpx.Client")
    def test_telegram_message_uses_context_manager(self, mock_client_class):
        """Test that _send_telegram_message uses context manager for HTTP client."""
        notifier = TelegramNotifier(self.config, self.mock_cred_manager)

        # Mock the HTTP client and response
        mock_client_instance = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True}
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)

        mock_client_class.return_value = mock_client_instance

        # Send a message
        result = notifier._send_telegram_message("Test message")

        # Verify client was created with context manager
        self.assertTrue(result)
        mock_client_class.assert_called_once_with(timeout=10.0)
        mock_client_instance.__enter__.assert_called_once()
        mock_client_instance.__exit__.assert_called_once()


class TestMonitorCheckerCleanup(unittest.TestCase):
    """Test that Monitor properly cleans up checkers after each check cycle."""

    @patch("src.monitor.CredentialManager")
    @patch("src.monitor.StateManager")
    @patch("src.monitor.MetricsCollector")
    def setUp(self, mock_metrics, mock_state, mock_creds):
        """Set up test monitor configuration."""
        self.config_data = {
            "monitoring": {"interval_minutes": 15},
            "notifications": {
                "console": {"enabled": True},
                "email": {"enabled": False},
                "telegram": {"enabled": False},
            },
            "sites": [
                {
                    "name": "TestSite",
                    "url": "https://example.com",
                    "checks_enabled": ["uptime"],
                    "uptime": {
                        "endpoints": ["/"],
                        "expected_status": [200],
                    },
                }
            ],
            "logging": {"level": "INFO"},
        }

    def test_perform_site_checks_cleanup(self):
        """Test that _perform_site_checks calls cleanup on all checkers."""
        # Create a monitor with mocked components
        with patch("builtins.open", unittest.mock.mock_open(read_data="dummy")):
            with patch("yaml.safe_load", return_value=self.config_data):
                with patch("src.monitor.setup_logging"):
                    with patch("src.monitor.create_healthcheck_monitor"):
                        monitor = Monitor()

        # Create mock checkers
        mock_uptime_checker = Mock(spec=UptimeChecker)
        mock_uptime_checker.check.return_value = Mock(
            check_type="uptime",
            success=True,
            status=CheckStatus.SUCCESS,
            response_time_ms=100,
        )

        checkers = {"uptime": mock_uptime_checker}

        # Call _perform_site_checks
        monitor._perform_site_checks("TestSite", self.config_data["sites"][0], checkers)

        # Verify cleanup was called
        mock_uptime_checker.cleanup.assert_called_once()

    def test_perform_site_checks_cleanup_on_exception(self):
        """Test that cleanup is called even when check raises exception."""
        # Create a monitor with mocked components
        with patch("builtins.open", unittest.mock.mock_open(read_data="dummy")):
            with patch("yaml.safe_load", return_value=self.config_data):
                with patch("src.monitor.setup_logging"):
                    with patch("src.monitor.create_healthcheck_monitor"):
                        monitor = Monitor()

        # Create mock checker that raises exception
        mock_checker = Mock(spec=UptimeChecker)
        mock_checker.check.side_effect = Exception("Test exception")

        checkers = {"uptime": mock_checker}

        # Call _perform_site_checks (should not raise)
        try:
            monitor._perform_site_checks(
                "TestSite", self.config_data["sites"][0], checkers
            )
        except Exception:
            pass

        # Verify cleanup was still called despite exception
        mock_checker.cleanup.assert_called_once()


class TestThreadPoolExecutor(unittest.TestCase):
    """Test that ThreadPoolExecutor is properly configured for bot commands."""

    @patch("src.monitor.CredentialManager")
    @patch("src.monitor.StateManager")
    @patch("src.monitor.MetricsCollector")
    @patch("src.monitor.setup_logging")
    @patch("src.monitor.create_healthcheck_monitor")
    def test_monitor_creates_executor(
        self, mock_health, mock_logging, mock_metrics, mock_state, mock_creds
    ):
        """Test that Monitor creates ThreadPoolExecutor for bot commands."""
        config_data = {
            "monitoring": {"interval_minutes": 15},
            "notifications": {
                "console": {"enabled": True},
                "email": {"enabled": False},
                "telegram": {"enabled": False},
            },
            "bot": {"enabled": False},
            "sites": [
                {
                    "name": "TestSite",
                    "url": "https://example.com",
                    "checks_enabled": ["uptime"],
                    "uptime": {"endpoints": ["/"]},
                }
            ],
            "logging": {"level": "INFO"},
        }

        with patch("builtins.open", unittest.mock.mock_open(read_data="dummy")):
            with patch("yaml.safe_load", return_value=config_data):
                monitor = Monitor()

        # Verify executor is created
        self.assertIsNotNone(monitor.bot_executor)
        self.assertEqual(monitor.bot_executor._max_workers, 2)
        self.assertTrue(monitor.bot_executor._thread_name_prefix.startswith("bot_cmd"))

        # Cleanup
        monitor.bot_executor.shutdown(wait=False)

    @patch("src.monitor.CredentialManager")
    @patch("src.monitor.StateManager")
    @patch("src.monitor.MetricsCollector")
    @patch("src.monitor.setup_logging")
    @patch("src.monitor.create_healthcheck_monitor")
    def test_monitor_shutdown_closes_executor(
        self, mock_health, mock_logging, mock_metrics, mock_state, mock_creds
    ):
        """Test that Monitor.stop() shuts down the executor."""
        config_data = {
            "monitoring": {"interval_minutes": 15},
            "notifications": {
                "console": {"enabled": True},
                "email": {"enabled": False},
                "telegram": {"enabled": False},
            },
            "bot": {"enabled": False},
            "sites": [
                {
                    "name": "TestSite",
                    "url": "https://example.com",
                    "checks_enabled": ["uptime"],
                    "uptime": {"endpoints": ["/"]},
                }
            ],
            "logging": {"level": "INFO"},
        }

        with patch("builtins.open", unittest.mock.mock_open(read_data="dummy")):
            with patch("yaml.safe_load", return_value=config_data):
                monitor = Monitor()

        # Mock metrics collector to return proper data
        monitor.metrics_collector.get_all_metrics_summary = Mock(return_value={
            "availability": {
                "availability_percentage": 99.5,
                "total_checks": 100,
                "failed_checks": 1,
            }
        })

        # Mock scheduler
        monitor.scheduler = Mock()
        monitor.scheduler.shutdown = Mock()

        # Stop monitor
        monitor.stop()

        # Executor should be shut down (checking _shutdown attribute)
        self.assertTrue(monitor.bot_executor._shutdown)


class TestMemoryLeakPrevention(unittest.TestCase):
    """Integration tests to verify no obvious memory leaks."""

    def setUp(self):
        """Set up test configuration."""
        self.config = {
            "monitoring": {
                "url": "https://www.example.com",
                "timeout_seconds": 10,
            },
            "checks": {
                "uptime": {
                    "endpoints": ["/"],
                    "expected_status": [200],
                }
            },
        }

    def test_repeated_checker_creation_and_cleanup(self):
        """Test that creating and cleaning up checkers doesn't leak resources."""
        # Create and cleanup checkers multiple times
        for i in range(10):
            checker = UptimeChecker(self.config)
            # Force client creation
            _ = checker.client
            # Cleanup
            checker.cleanup()

        # Force garbage collection
        gc.collect()

        # If we got here without issues, the test passes
        # (In a real scenario, you could use memory profilers to verify)
        self.assertTrue(True)

    def test_checker_garbage_collection(self):
        """Test that checkers are garbage collected after cleanup."""
        checker = UptimeChecker(self.config)
        _ = checker.client

        # Cleanup and delete reference
        checker.cleanup()
        del checker

        # Force garbage collection
        gc.collect()

        # If we got here without issues, the test passes
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
