"""Logging configuration and utilities."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import coloredlogs


def setup_logging(
    config: Optional[Dict[str, Any]] = None, console: bool = True, file: bool = True
) -> logging.Logger:
    """
    Set up logging configuration.

    Args:
        config: Logging configuration dictionary
        console: Enable console logging
        file: Enable file logging

    Returns:
        Configured root logger
    """
    if config is None:
        config = {}

    # Get configuration values
    log_config = config.get("logging", {})
    level = log_config.get("level", "INFO")
    log_format = log_config.get(
        "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    date_format = log_config.get("date_format", "%Y-%m-%d %H:%M:%S")

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))

    # Clear any existing handlers
    root_logger.handlers = []

    # Console handler with colored output
    if console:
        if sys.stdout.isatty():
            # Use colored logs if in terminal
            coloredlogs.install(
                level=level,
                fmt=log_format,
                datefmt=date_format,
                field_styles={
                    "asctime": {"color": "green"},
                    "hostname": {"color": "magenta"},
                    "levelname": {"color": "white", "bold": True},
                    "name": {"color": "blue"},
                    "programname": {"color": "cyan"},
                },
                level_styles={
                    "debug": {"color": "green"},
                    "info": {"color": "white"},
                    "warning": {"color": "yellow"},
                    "error": {"color": "red"},
                    "critical": {"color": "red", "bold": True},
                },
            )
        else:
            # Plain console handler for non-terminal output
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, level))
            console_formatter = logging.Formatter(log_format, datefmt=date_format)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

    # File handlers
    if file:
        # Create logs directory if it doesn't exist
        log_dir = Path(log_config.get("file_path", "./logs/monitor.log")).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # Main log file with time-based rotation
        file_path = log_config.get("file_path", "./logs/monitor.log")
        rotation_when = log_config.get("rotation_when", "midnight")  # When to rotate
        rotation_interval = log_config.get("rotation_interval", 1)   # Every N periods
        backup_count = log_config.get("backup_count", 7)             # Keep 7 days
        main_log_level = log_config.get("main_log_level", level)     # Default to root level

        file_handler = logging.handlers.TimedRotatingFileHandler(
            file_path,
            when=rotation_when,
            interval=rotation_interval,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, main_log_level))
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Error log file (warnings and errors)
        error_file_path = log_config.get("error_file_path", "./logs/monitor.error.log")
        error_log_level = log_config.get("error_log_level", "ERROR")  # Default to ERROR

        error_handler = logging.handlers.TimedRotatingFileHandler(
            error_file_path,
            when=rotation_when,
            interval=rotation_interval,
            backupCount=backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(getattr(logging, error_log_level))
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)

    # Log initial message
    root_logger.info("Logging configured successfully")
    root_logger.info(f"Log level: {level}")

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for adding context to log messages."""

    def process(self, msg, kwargs):
        """Add context to log messages."""
        # Add any context from extra dict
        if self.extra:
            context_items = [f"{k}={v}" for k, v in self.extra.items()]
            msg = f"[{', '.join(context_items)}] {msg}"
        return msg, kwargs


def get_context_logger(name: str, **context) -> LoggerAdapter:
    """
    Get a logger with additional context.

    Args:
        name: Logger name
        **context: Context variables to add to all log messages

    Returns:
        Logger adapter with context
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, context)
