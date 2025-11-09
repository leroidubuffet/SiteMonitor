"""Security utilities for sanitizing user input and external data."""

import html
import re


def sanitize_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS in HTML emails.

    Args:
        text: Potentially unsafe text

    Returns:
        HTML-safe text
    """
    if not text:
        return ""

    return html.escape(str(text))


def sanitize_email_header(text: str) -> str:
    """
    Sanitize text for use in email headers to prevent header injection.

    Removes newlines, carriage returns, and other control characters.

    Args:
        text: Potentially unsafe header value

    Returns:
        Safe header value
    """
    if not text:
        return ""

    # Remove newlines, carriage returns, and null bytes
    text = str(text).replace('\r', '').replace('\n', '').replace('\0', '')

    # Remove other control characters (ASCII 0-31 except space)
    text = ''.join(char for char in text if ord(char) >= 32 or char == ' ')

    return text.strip()


def sanitize_log_message(text: str, max_length: int = 500) -> str:
    """
    Sanitize text for logging to prevent log injection attacks.

    Args:
        text: Potentially unsafe log message
        max_length: Maximum length of log message

    Returns:
        Safe log message
    """
    if not text:
        return ""

    # Remove newlines to prevent log injection
    text = str(text).replace('\r', '').replace('\n', ' ')

    # Truncate to prevent log flooding
    if len(text) > max_length:
        text = text[:max_length] + "... [truncated]"

    return text


def sanitize_url_for_display(url: str) -> str:
    """
    Sanitize URL for safe display in logs/emails.

    Removes credentials if present in URL.

    Args:
        url: URL that might contain credentials

    Returns:
        Safe URL for display
    """
    if not url:
        return ""

    # Remove user:pass@ from URLs
    url = re.sub(r'://[^:]+:[^@]+@', '://***:***@', str(url))

    return url
