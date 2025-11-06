"""Secure credential management using keyring and environment variables."""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path

try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logging.warning("keyring not available, using environment variables only")

from dotenv import load_dotenv


class CredentialManager:
    """Manage credentials securely using keyring or environment variables."""

    SERVICE_NAME = "inforuta-monitor"

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize credential manager.

        Args:
            env_file: Path to .env file (optional)
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.use_keyring = (
            KEYRING_AVAILABLE and os.getenv("ENVIRONMENT") == "production"
        )

        # Load environment variables from .env file
        if env_file and Path(env_file).exists() and Path(env_file).is_file():
            load_dotenv(env_file)
            self.logger.info(f"Loaded environment from {env_file}")
        else:
            # Try to find .env in common locations
            possible_paths = [
                Path.cwd() / ".env",
                Path.cwd() / "config" / ".env",
                Path(__file__).parent.parent.parent / "config" / ".env",
            ]

            for path in possible_paths:
                if path.exists() and path.is_file():
                    load_dotenv(path)
                    self.logger.info(f"Loaded environment from {path}")
                    break

    def get_credential(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a credential value.

        Args:
            key: Credential key (e.g., 'INFORUTA_USERNAME')
            default: Default value if not found

        Returns:
            Credential value or default
        """
        # Try keyring first if available and in production
        if self.use_keyring:
            try:
                value = keyring.get_password(self.SERVICE_NAME, key)
                if value:
                    self.logger.debug(f"Retrieved {key} from keyring")
                    return value
            except Exception as e:
                self.logger.warning(f"Failed to get {key} from keyring: {e}")

        # Fall back to environment variable
        value = os.getenv(key, default)
        if value and value != default:
            self.logger.debug(f"Retrieved {key} from environment")

        return value

    def set_credential(self, key: str, value: str) -> bool:
        """
        Set a credential value.

        Args:
            key: Credential key
            value: Credential value

        Returns:
            True if successful
        """
        if self.use_keyring:
            try:
                keyring.set_password(self.SERVICE_NAME, key, value)
                self.logger.info(f"Stored {key} in keyring")
                return True
            except Exception as e:
                self.logger.error(f"Failed to store {key} in keyring: {e}")
                return False
        else:
            # For development, just log that we would store it
            self.logger.info(
                f"Would store {key} (keyring not available or not in production)"
            )
            return True

    def delete_credential(self, key: str) -> bool:
        """
        Delete a credential.

        Args:
            key: Credential key

        Returns:
            True if successful
        """
        if self.use_keyring:
            try:
                keyring.delete_password(self.SERVICE_NAME, key)
                self.logger.info(f"Deleted {key} from keyring")
                return True
            except Exception as e:
                self.logger.warning(f"Failed to delete {key} from keyring: {e}")
                return False
        return True

    def get_inforuta_credentials(self) -> Dict[str, Optional[str]]:
        """
        Get InfoRuta login credentials.

        Returns:
            Dictionary with username and password
        """
        return {
            "username": self.get_credential("INFORUTA_USERNAME"),
            "password": self.get_credential("INFORUTA_PASSWORD"),
        }

    def get_email_credentials(self) -> Dict[str, Optional[str]]:
        """
        Get email configuration.

        Returns:
            Dictionary with email settings
        """
        return {
            "from_address": self.get_credential("EMAIL_FROM"),
            "to_address": self.get_credential("EMAIL_TO"),
            "password": self.get_credential("EMAIL_PASSWORD"),
            "smtp_server": self.get_credential("SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(self.get_credential("SMTP_PORT", "587")),
        }

    def get_slack_webhook(self) -> Optional[str]:
        """
        Get Slack webhook URL.

        Returns:
            Webhook URL or None
        """
        return self.get_credential("SLACK_WEBHOOK")

    def validate_credentials(self) -> Dict[str, bool]:
        """
        Validate that required credentials are present.

        Returns:
            Dictionary showing which credentials are configured
        """
        results = {}

        # Check InfoRuta credentials
        inforuta_creds = self.get_inforuta_credentials()
        results["inforuta_configured"] = bool(
            inforuta_creds.get("username") and inforuta_creds.get("password")
        )

        # Check email credentials
        email_creds = self.get_email_credentials()
        results["email_configured"] = bool(
            email_creds.get("from_address")
            and email_creds.get("to_address")
            and email_creds.get("password")
        )

        # Check Slack
        results["slack_configured"] = bool(self.get_slack_webhook())

        return results

    def mask_credential(self, value: str, visible_chars: int = 3) -> str:
        """
        Mask a credential value for logging.

        Args:
            value: Credential value to mask
            visible_chars: Number of characters to show at start

        Returns:
            Masked value
        """
        if not value or len(value) <= visible_chars:
            return "*" * len(value) if value else ""

        return value[:visible_chars] + "*" * (len(value) - visible_chars)
