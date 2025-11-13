"""
Tests for Telegram Bot Handler with bidirectional commands.

Tests bot authorization, commands, and integration with monitor.
"""

import asyncio
import os
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock
from datetime import datetime

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.bot.telegram_bot_handler import TelegramBotHandler
from src.storage.state_manager import StateManager
from src.utils.metrics import MetricsCollector


@pytest.fixture
def mock_monitor():
    """Create a mock Monitor instance."""
    monitor = Mock()
    monitor.running = True
    monitor.sites = [
        {"name": "Test Site 1", "url": "https://test1.com"},
        {"name": "Test Site 2", "url": "https://test2.com"},
    ]
    monitor.perform_checks = Mock()
    return monitor


@pytest.fixture
def mock_state_manager():
    """Create a mock StateManager instance."""
    state_manager = Mock(spec=StateManager)
    state_manager.state = {
        "global": {
            "last_check_time": datetime.now().isoformat(),
            "total_checks": 100
        },
        "sites": {
            "Test Site 1": {
                "last_check_time": datetime.now().isoformat(),
                "last_results": {
                    "uptime": {"success": True, "status": "SUCCESS"}
                },
                "statistics": {
                    "total_checks": 50,
                    "total_failures": 2,
                    "consecutive_failures": {}
                }
            },
            "Test Site 2": {
                "last_check_time": datetime.now().isoformat(),
                "last_results": {
                    "uptime": {"success": False, "status": "FAILURE"}
                },
                "statistics": {
                    "total_checks": 50,
                    "total_failures": 5,
                    "consecutive_failures": {"uptime": 1}
                }
            }
        }
    }
    state_manager.get_summary = Mock(return_value=state_manager.state["sites"])
    state_manager.get_statistics = Mock(return_value={"total_checks": 50, "total_failures": 2})
    state_manager.get_history = Mock(return_value=[
        {"timestamp": datetime.now().isoformat(), "status": "SUCCESS", "success": True},
        {"timestamp": datetime.now().isoformat(), "status": "FAILURE", "success": False},
    ])
    return state_manager


@pytest.fixture
def mock_metrics_collector():
    """Create a mock MetricsCollector instance."""
    collector = Mock(spec=MetricsCollector)
    collector.get_all_metrics_summary = Mock(return_value={
        "availability": {
            "availability_percentage": 95.5,
            "total_checks": 100,
            "failed_checks": 5,
            "success_rate": 95.0
        }
    })
    return collector


@pytest.fixture
def bot_handler(mock_monitor, mock_state_manager, mock_metrics_collector):
    """Create a TelegramBotHandler instance with mocks."""
    authorized_users = [123456789, 987654321]

    with patch('src.bot.telegram_bot_handler.Application') as mock_app_class:
        mock_app = Mock()
        mock_app.add_handler = Mock()
        mock_app_builder = Mock()
        mock_app_builder.token.return_value = mock_app_builder
        mock_app_builder.build.return_value = mock_app
        mock_app_class.builder.return_value = mock_app_builder

        handler = TelegramBotHandler(
            bot_token="test_token",
            authorized_users=authorized_users,
            monitor=mock_monitor,
            state_manager=mock_state_manager,
            metrics_collector=mock_metrics_collector
        )

        return handler


class TestTelegramBotAuthorization:
    """Test bot authorization functionality."""

    def test_authorized_user(self, bot_handler):
        """Test that authorized users are recognized."""
        assert bot_handler._is_authorized(123456789) is True
        assert bot_handler._is_authorized(987654321) is True

    def test_unauthorized_user(self, bot_handler):
        """Test that unauthorized users are rejected."""
        assert bot_handler._is_authorized(111111111) is False
        assert bot_handler._is_authorized(999999999) is False

    def test_empty_authorized_users(self, mock_monitor, mock_state_manager, mock_metrics_collector):
        """Test that handler requires authorized users."""
        with patch('src.bot.telegram_bot_handler.Application'):
            handler = TelegramBotHandler(
                bot_token="test_token",
                authorized_users=[],
                monitor=mock_monitor,
                state_manager=mock_state_manager,
                metrics_collector=mock_metrics_collector
            )
            # Should not authorize any user
            assert handler._is_authorized(123456789) is False


class TestBotCommands:
    """Test individual bot commands."""

    @pytest.mark.asyncio
    async def test_cmd_start_authorized(self, bot_handler):
        """Test /start command for authorized user."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()

        await bot_handler.cmd_start(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "Site Monitor Bot" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_start_unauthorized(self, bot_handler):
        """Test /start command for unauthorized user (should be silent)."""
        update = Mock()
        update.effective_user.id = 999999999  # Unauthorized
        update.message.reply_text = AsyncMock()
        context = Mock()

        await bot_handler.cmd_start(update, context)

        # Should not send any response
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_cmd_help(self, bot_handler):
        """Test /help command."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()

        await bot_handler.cmd_help(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "/status" in args[0][0]
        assert "/sites" in args[0][0]
        assert "/check" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_status(self, bot_handler):
        """Test /status command."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()

        await bot_handler.cmd_status(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "Monitor Status" in args[0][0]
        assert "Sites monitored: 2" in args[0][0]
        assert "Test Site 1" in args[0][0]
        assert "Test Site 2" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_sites(self, bot_handler):
        """Test /sites command."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()

        await bot_handler.cmd_sites(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "Monitored Sites" in args[0][0]
        assert "Test Site 1" in args[0][0]
        assert "Test Site 2" in args[0][0]
        assert "https://test1.com" in args[0][0]
        assert "https://test2.com" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_check(self, bot_handler):
        """Test /check command triggers monitoring."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=None)

            await bot_handler.cmd_check(update, context)

            # Should send "triggering" message
            assert update.message.reply_text.call_count == 2
            calls = update.message.reply_text.call_args_list
            assert "Triggering immediate check" in calls[0][0][0]
            assert "completed successfully" in calls[1][0][0]

    @pytest.mark.asyncio
    async def test_cmd_stats(self, bot_handler):
        """Test /stats command."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()

        await bot_handler.cmd_stats(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "Statistics" in args[0][0]
        assert "95.5" in args[0][0]  # Availability percentage
        assert "Per-Site Failure Counts" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_site_valid(self, bot_handler):
        """Test /site command with valid site name."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()
        context.args = ["Test", "Site", "1"]

        await bot_handler.cmd_site(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "Test Site 1" in args[0][0]
        assert "Statistics" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_site_no_args(self, bot_handler):
        """Test /site command without arguments."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()
        context.args = []

        await bot_handler.cmd_site(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "Usage:" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_site_invalid(self, bot_handler, mock_state_manager):
        """Test /site command with invalid site name."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()
        context.args = ["NonExistent"]

        # Mock empty summary for non-existent site
        mock_state_manager.get_summary.return_value = {}

        await bot_handler.cmd_site(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "not found" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_history_valid(self, bot_handler):
        """Test /history command with valid site name."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()
        context.args = ["Test", "Site", "1"]

        await bot_handler.cmd_history(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "History for Test Site 1" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_history_no_args(self, bot_handler):
        """Test /history command without arguments."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()
        context.args = []

        await bot_handler.cmd_history(update, context)

        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "Usage:" in args[0][0]

    @pytest.mark.asyncio
    async def test_handle_unauthorized(self, bot_handler):
        """Test that unauthorized messages are silently ignored."""
        update = Mock()
        update.effective_user.id = 999999999  # Unauthorized
        update.message.text = "Some message"
        update.message.reply_text = AsyncMock()
        context = Mock()

        await bot_handler.handle_unauthorized(update, context)

        # Should not send any response
        update.message.reply_text.assert_not_called()


class TestBotLifecycle:
    """Test bot start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_bot_initialization(self, bot_handler):
        """Test that bot initializes properly."""
        assert bot_handler.bot_token == "test_token"
        assert 123456789 in bot_handler.authorized_users
        assert 987654321 in bot_handler.authorized_users
        assert bot_handler.running is False

    @pytest.mark.asyncio
    async def test_bot_start(self, bot_handler):
        """Test bot start method."""
        with patch.object(bot_handler.application, 'initialize', new_callable=AsyncMock):
            with patch.object(bot_handler.application, 'start', new_callable=AsyncMock):
                with patch.object(bot_handler.application, 'updater') as mock_updater:
                    mock_updater.start_polling = AsyncMock()

                    await bot_handler.start()

                    assert bot_handler.running is True
                    bot_handler.application.initialize.assert_called_once()
                    bot_handler.application.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_stop(self, bot_handler):
        """Test bot stop method."""
        bot_handler.running = True

        with patch.object(bot_handler.application, 'updater') as mock_updater:
            mock_updater.running = True
            mock_updater.stop = AsyncMock()

            with patch.object(bot_handler.application, 'stop', new_callable=AsyncMock):
                with patch.object(bot_handler.application, 'shutdown', new_callable=AsyncMock):
                    await bot_handler.stop()

                    assert bot_handler.running is False
                    mock_updater.stop.assert_called_once()
                    bot_handler.application.stop.assert_called_once()
                    bot_handler.application.shutdown.assert_called_once()


class TestErrorHandling:
    """Test error handling in bot commands."""

    @pytest.mark.asyncio
    async def test_cmd_status_exception(self, bot_handler, mock_monitor):
        """Test /status command handles exceptions gracefully."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()

        # Make monitor.sites raise an exception when accessed
        type(mock_monitor).sites = PropertyMock(side_effect=Exception("Test error"))

        await bot_handler.cmd_status(update, context)

        # Should send error message
        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args
        assert "Error" in args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_check_exception(self, bot_handler):
        """Test /check command handles exceptions gracefully."""
        update = Mock()
        update.effective_user.id = 123456789
        update.message.reply_text = AsyncMock()
        context = Mock()

        with patch('asyncio.get_event_loop') as mock_loop:
            # Make executor raise an exception
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=Exception("Check failed")
            )

            await bot_handler.cmd_check(update, context)

            # Should send error message
            assert update.message.reply_text.call_count >= 2
            last_call = update.message.reply_text.call_args_list[-1]
            assert "Error" in last_call[0][0]


def test_bot_import():
    """Test that bot module can be imported."""
    from src.bot import TelegramBotHandler
    assert TelegramBotHandler is not None


def test_bot_initialization_requirements():
    """Test that bot requires all necessary parameters."""
    with pytest.raises(TypeError):
        # Should fail without required parameters
        TelegramBotHandler()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
