"""
Telegram Bot Handler for bidirectional communication with the monitoring system.

Provides commands to check status, trigger checks, and view statistics via Telegram.
"""

import asyncio
import logging
import os
from functools import wraps
from typing import Any, Dict, List, Optional
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ..storage import StateManager
from ..utils import MetricsCollector


def require_message(func):
    """Decorator to ensure update has a message and user before processing."""
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return  # Skip non-message updates
        return await func(self, update, context)
    return wrapper


class TelegramBotHandler:
    """Handles incoming Telegram bot commands and provides system interaction."""

    def __init__(
        self,
        bot_token: str,
        authorized_users: List[int],
        monitor: Any,
        state_manager: StateManager,
        metrics_collector: MetricsCollector,
    ):
        """
        Initialize the Telegram bot handler.

        Args:
            bot_token: Telegram bot token
            authorized_users: List of authorized Telegram user IDs
            monitor: Monitor instance for triggering checks
            state_manager: StateManager instance for accessing state
            metrics_collector: MetricsCollector instance for metrics
        """
        self.bot_token = bot_token
        self.authorized_users = set(authorized_users)
        self.monitor = monitor
        self.state_manager = state_manager
        self.metrics_collector = metrics_collector
        self.logger = logging.getLogger(self.__class__.__name__)

        # Build application
        self.application = Application.builder().token(bot_token).build()

        # Register command handlers
        self._register_handlers()

        self.running = False

    def _register_handlers(self):
        """Register all command handlers."""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("sites", self.cmd_sites))
        self.application.add_handler(CommandHandler("check", self.cmd_check))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("site", self.cmd_site))
        self.application.add_handler(CommandHandler("history", self.cmd_history))

        # Handle unauthorized messages silently
        self.application.add_handler(
            MessageHandler(filters.ALL, self.handle_unauthorized)
        )

    def _is_authorized(self, user_id: int) -> bool:
        """
        Check if user is authorized to use the bot.

        Args:
            user_id: Telegram user ID

        Returns:
            True if authorized, False otherwise
        """
        authorized = user_id in self.authorized_users
        if not authorized:
            self.logger.warning(f"Unauthorized access attempt from user ID: {user_id}")
        return authorized

    def _format_datetime(self, dt_value, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        Safely format a datetime value that could be string, datetime, or None.

        Args:
            dt_value: Can be datetime object, ISO format string, or None
            format_str: strftime format string

        Returns:
            Formatted datetime string or "Never" if None/invalid
        """
        if dt_value is None:
            return "Never"

        try:
            # If it's already a datetime object
            if isinstance(dt_value, datetime):
                return dt_value.strftime(format_str)
            # If it's a string, parse it first
            elif isinstance(dt_value, str):
                return datetime.fromisoformat(dt_value).strftime(format_str)
            else:
                self.logger.warning(f"Unexpected datetime type: {type(dt_value)} value: {dt_value}")
                return "Invalid"
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.warning(f"Failed to format datetime {dt_value} (type: {type(dt_value)}): {e}")
            return "Invalid"

    @require_message
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._is_authorized(update.effective_user.id):
            return  # Silent ignore

        await update.message.reply_text(
            "🤖 *Site Monitor Bot*\n\n"
            "I can help you monitor your websites. Use /help to see available commands.",
            parse_mode="Markdown"
        )

    @require_message
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not self._is_authorized(update.effective_user.id):
            return  # Silent ignore

        help_text = (
            "📚 *Available Commands:*\n\n"
            "*Basic Commands:*\n"
            "/status - Check monitor status\n"
            "/sites - List all monitored sites\n"
            "/check - Trigger immediate check\n"
            "/help - Show this help message\n\n"
            "*Detailed Commands:*\n"
            "/stats - View statistics and metrics\n"
            "/site <name> - Get details for specific site\n"
            "/history <site> - View recent check history\n\n"
            "*Note:* Site names are case-sensitive."
        )

        await update.message.reply_text(help_text, parse_mode="Markdown")

    @require_message
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show monitor status."""
        if not self._is_authorized(update.effective_user.id):
            return  # Silent ignore

        try:
            # Get monitor status
            running = self.monitor.running
            sites = [site.get("name") for site in self.monitor.sites]

            # Get last check time
            last_check_time = self.state_manager.state.get("global", {}).get("last_check_time")
            last_check_str = self._format_datetime(last_check_time)

            # Get total checks
            total_checks = self.state_manager.state.get("global", {}).get("total_checks", 0)

            status_icon = "🟢" if running else "🔴"
            status_text = "Running" if running else "Stopped"

            response = (
                f"{status_icon} *Monitor Status: {status_text}*\n\n"
                f"📊 Sites monitored: {len(sites)}\n"
                f"🕐 Last check: {last_check_str}\n"
                f"📈 Total checks: {total_checks}\n\n"
                f"*Monitored sites:*\n"
                + "\n".join(f"  • {site}" for site in sites)
            )

            await update.message.reply_text(response, parse_mode="Markdown")

        except Exception as e:
            self.logger.error(f"Error in /status command: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Error retrieving status. Check logs for details."
            )

    @require_message
    async def cmd_sites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sites command - list all monitored sites with status."""
        if not self._is_authorized(update.effective_user.id):
            return  # Silent ignore

        try:
            sites_data = []

            for site_config in self.monitor.sites:
                site_name = site_config.get("name", "Unknown")

                # Get last results for this site
                site_state = self.state_manager.state.get("sites", {}).get(site_name, {})
                last_results = site_state.get("last_results", {})

                # Determine overall status
                status_icon = "✅"
                for check_type, result in last_results.items():
                    if not result.get("success", True):
                        status_icon = "❌"
                        break

                # Get last check time
                last_check_time = site_state.get("last_check_time")
                last_check = self._format_datetime(last_check_time, "%H:%M:%S")

                sites_data.append({
                    "name": site_name,
                    "status_icon": status_icon,
                    "last_check": last_check,
                    "url": site_config.get("url", "")
                })

            response = "🌐 *Monitored Sites:*\n\n"
            for site in sites_data:
                response += (
                    f"{site['status_icon']} *{site['name']}*\n"
                    f"  🔗 {site['url']}\n"
                    f"  🕐 Last check: {site['last_check']}\n\n"
                )

            await update.message.reply_text(response, parse_mode="Markdown")

        except Exception as e:
            self.logger.error(f"Error in /sites command: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Error retrieving sites. Check logs for details."
            )

    @require_message
    async def cmd_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /check command - trigger immediate check."""
        if not self._is_authorized(update.effective_user.id):
            return  # Silent ignore

        try:
            await update.message.reply_text("🔄 Triggering immediate check...")

            # Run check in executor to avoid blocking the bot
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.monitor.perform_checks)

            await update.message.reply_text("✅ Check completed successfully!")

        except Exception as e:
            self.logger.error(f"Error in /check command: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error triggering check: {str(e)}"
            )

    @require_message
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - show statistics."""
        if not self._is_authorized(update.effective_user.id):
            return  # Silent ignore

        try:
            # Get global metrics
            metrics = self.metrics_collector.get_all_metrics_summary()
            availability = metrics.get("availability", {})

            response = "📊 *Statistics:*\n\n"
            response += "*Global Metrics:*\n"
            response += f"  Availability: {availability.get('availability_percentage', 0):.2f}%\n"
            response += f"  Total checks: {availability.get('total_checks', 0)}\n"
            response += f"  Failed checks: {availability.get('failed_checks', 0)}\n"
            response += f"  Success rate: {availability.get('success_rate', 0):.2f}%\n\n"

            # Per-site statistics
            response += "*Per-Site Failure Counts:*\n"
            for site_config in self.monitor.sites:
                site_name = site_config.get("name")
                stats = self.state_manager.get_statistics(site_name)
                total_failures = stats.get("total_failures", 0)
                total_checks = stats.get("total_checks", 0)

                if total_checks > 0:
                    failure_rate = (total_failures / total_checks) * 100
                    response += f"  • {site_name}: {total_failures} failures ({failure_rate:.1f}%)\n"

            await update.message.reply_text(response, parse_mode="Markdown")

        except Exception as e:
            self.logger.error(f"Error in /stats command: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Error retrieving statistics. Check logs for details."
            )

    @require_message
    async def cmd_site(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /site command - show details for specific site."""
        if not self._is_authorized(update.effective_user.id):
            return  # Silent ignore

        # Get site name from args
        if not context.args:
            await update.message.reply_text(
                "⚠️ Usage: /site <site_name>\n\n"
                "Example: /site AEMET"
            )
            return

        site_name = " ".join(context.args)

        try:
            # Get site summary
            summary = self.state_manager.get_summary(site_name)

            if not summary:
                await update.message.reply_text(
                    f"❌ Site '{site_name}' not found.\n\n"
                    "Use /sites to see all monitored sites."
                )
                return

            site_state = summary.get(site_name, {})
            last_results = site_state.get("last_results", {})
            statistics = site_state.get("statistics", {})

            response = f"🌐 *Site: {site_name}*\n\n"

            # Last check time
            last_check_time = site_state.get("last_check_time")
            last_check_str = self._format_datetime(last_check_time)
            if last_check_str != "Never":
                response += f"🕐 Last check: {last_check_str}\n\n"

            # Check results
            response += "*Latest Check Results:*\n"
            for check_type, result in last_results.items():
                status_icon = "✅" if result.get("success") else "❌"
                status = result.get("status", "UNKNOWN")
                response += f"  {status_icon} {check_type.upper()}: {status}\n"

            # Statistics
            response += "\n*Statistics:*\n"
            response += f"  Total checks: {statistics.get('total_checks', 0)}\n"
            response += f"  Total failures: {statistics.get('total_failures', 0)}\n"

            # Consecutive failures
            consecutive = statistics.get("consecutive_failures", {})
            if consecutive:
                response += "\n*Consecutive Failures:*\n"
                for check_type, count in consecutive.items():
                    if count > 0:
                        response += f"  • {check_type}: {count}\n"

            await update.message.reply_text(response, parse_mode="Markdown")

        except Exception as e:
            self.logger.error(f"Error in /site command: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error retrieving site details: {str(e)}"
            )

    @require_message
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command - show recent check history."""
        if not self._is_authorized(update.effective_user.id):
            return  # Silent ignore

        # Get site name from args
        if not context.args:
            await update.message.reply_text(
                "⚠️ Usage: /history <site_name>\n\n"
                "Example: /history AEMET"
            )
            return

        site_name = " ".join(context.args)

        try:
            # Get history for each check type
            response = f"📜 *History for {site_name}:*\n\n"

            for check_type in ["uptime", "authentication", "health"]:
                history = self.state_manager.get_history(check_type, count=5, site_name=site_name)

                if history:
                    response += f"*{check_type.upper()}:*\n"
                    for entry in history:
                        timestamp = self._format_datetime(entry.get("timestamp"), "%H:%M:%S")
                        status = entry.get("status", "UNKNOWN")
                        success = entry.get("success", False)
                        icon = "✅" if success else "❌"
                        response += f"  {icon} {timestamp} - {status}\n"
                    response += "\n"

            if len(response.split("\n")) <= 3:
                await update.message.reply_text(
                    f"ℹ️ No history found for site '{site_name}'."
                )
            else:
                await update.message.reply_text(response, parse_mode="Markdown")

        except Exception as e:
            self.logger.error(f"Error in /history command: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error retrieving history: {str(e)}"
            )

    async def handle_unauthorized(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages from unauthorized users (silent ignore with logging)."""
        user_id = update.effective_user.id if update.effective_user else "Unknown"

        if user_id != "Unknown" and user_id not in self.authorized_users:
            self.logger.warning(
                f"Unauthorized message from user {user_id}: {update.message.text if update.message else 'N/A'}"
            )
        # Silently ignore - don't send any response

    async def start(self):
        """Start the bot (async)."""
        self.logger.info("Starting Telegram bot...")
        self.running = True

        # Initialize and start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        self.logger.info("Telegram bot started successfully")

    async def stop(self):
        """Stop the bot (async)."""
        self.logger.info("Stopping Telegram bot...")
        self.running = False

        if self.application.updater.running:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

        self.logger.info("Telegram bot stopped")

    def run(self):
        """Run the bot in blocking mode (synchronous entry point)."""
        asyncio.run(self._run_async())

    async def _run_async(self):
        """Run the bot asynchronously."""
        await self.start()

        try:
            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Bot interrupted by user")
        finally:
            await self.stop()
