"""Configuration validation utilities to prevent SSRF and misconfigurations."""

import logging
from typing import Any, Dict, List
from urllib.parse import urlparse
import ipaddress
import socket

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""
    pass


class ConfigValidator:
    """Validator for monitor configuration to prevent security issues."""

    @staticmethod
    def validate_url(url: str, field_name: str = "url") -> None:
        """
        Validate a URL for security issues.

        Args:
            url: URL to validate
            field_name: Name of the field (for error messages)

        Raises:
            ConfigValidationError: If URL is invalid or unsafe
        """
        if not url or not isinstance(url, str):
            raise ConfigValidationError(f"{field_name} must be a non-empty string")

        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ConfigValidationError(f"{field_name}: Failed to parse URL: {e}")

        # Check scheme
        if parsed.scheme not in ["http", "https"]:
            raise ConfigValidationError(
                f"{field_name}: Invalid URL scheme '{parsed.scheme}'. "
                f"Only http and https are allowed."
            )

        # Check hostname
        if not parsed.hostname:
            raise ConfigValidationError(f"{field_name}: URL must have a hostname")

        hostname = parsed.hostname.lower()

        # Block localhost
        if hostname in ["localhost", "127.0.0.1", "::1", "0.0.0.0"] or hostname.startswith("127."):
            raise ConfigValidationError(
                f"{field_name}: Localhost addresses are not allowed: {hostname}"
            )

        # Block cloud metadata
        if hostname in ["169.254.169.254", "metadata.google.internal", "metadata", "instance-data"]:
            raise ConfigValidationError(
                f"{field_name}: Cloud metadata endpoints are not allowed: {hostname}"
            )

        if hostname.startswith("169.254."):
            raise ConfigValidationError(
                f"{field_name}: Cloud metadata IP range (169.254.x.x) is not allowed"
            )

        # Check if it's an IP address
        try:
            ip = ipaddress.ip_address(hostname.strip("[]"))
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ConfigValidationError(
                    f"{field_name}: Private/internal IP addresses are not allowed: {ip}"
                )
        except ValueError:
            # It's a hostname, check for private IP prefixes
            private_prefixes = [
                "10.", "172.16.", "172.17.", "172.18.", "172.19.",
                "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                "172.30.", "172.31.", "192.168."
            ]
            if any(hostname.startswith(prefix) for prefix in private_prefixes):
                raise ConfigValidationError(
                    f"{field_name}: Private IP ranges are not allowed: {hostname}"
                )

        logger.debug(f"URL validation passed for {field_name}: {url}")

    @staticmethod
    def validate_site_config(site: Dict[str, Any], site_index: int) -> None:
        """
        Validate a single site configuration.

        Args:
            site: Site configuration dictionary
            site_index: Index of site in config (for error messages)

        Raises:
            ConfigValidationError: If site configuration is invalid
        """
        site_id = f"sites[{site_index}]"

        # Validate site name
        if "name" not in site or not site["name"]:
            raise ConfigValidationError(f"{site_id}: 'name' is required")

        site_name = site["name"]
        site_id = f"site '{site_name}'"

        # Validate URL
        if "url" not in site or not site["url"]:
            raise ConfigValidationError(f"{site_id}: 'url' is required")

        ConfigValidator.validate_url(site["url"], f"{site_id}.url")

        # Validate checks_enabled
        if "checks_enabled" in site:
            checks = site["checks_enabled"]
            if not isinstance(checks, list):
                raise ConfigValidationError(
                    f"{site_id}: 'checks_enabled' must be a list"
                )

            valid_checks = ["uptime", "authentication", "health"]
            for check in checks:
                if check not in valid_checks:
                    raise ConfigValidationError(
                        f"{site_id}: Invalid check type '{check}'. "
                        f"Valid types: {', '.join(valid_checks)}"
                    )

        # Validate authentication config if present
        if "authentication" in site:
            auth_config = site["authentication"]
            if not isinstance(auth_config, dict):
                raise ConfigValidationError(
                    f"{site_id}: 'authentication' must be a dictionary"
                )

            # Validate login endpoint if present
            if "login_endpoint" in auth_config:
                endpoint = auth_config["login_endpoint"]
                if not isinstance(endpoint, str):
                    raise ConfigValidationError(
                        f"{site_id}.authentication.login_endpoint must be a string"
                    )

        logger.debug(f"Site configuration validated: {site_name}")

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """
        Validate full monitor configuration.

        Args:
            config: Full configuration dictionary

        Returns:
            List of warning messages (non-fatal issues)

        Raises:
            ConfigValidationError: If configuration is invalid
        """
        warnings = []

        # Validate sites array
        if "sites" not in config:
            raise ConfigValidationError("Configuration must have 'sites' array")

        sites = config["sites"]
        if not isinstance(sites, list):
            raise ConfigValidationError("'sites' must be a list")

        if len(sites) == 0:
            raise ConfigValidationError("At least one site must be configured")

        # Check for duplicate site names
        site_names = []
        for i, site in enumerate(sites):
            if not isinstance(site, dict):
                raise ConfigValidationError(f"sites[{i}]: Each site must be a dictionary")

            # Validate each site
            ConfigValidator.validate_site_config(site, i)

            # Check for duplicates
            name = site.get("name", "")
            if name in site_names:
                raise ConfigValidationError(
                    f"Duplicate site name: '{name}'. Site names must be unique."
                )
            site_names.append(name)

        # Validate monitoring configuration
        if "monitoring" in config:
            monitoring = config["monitoring"]
            if "timeout_seconds" in monitoring:
                timeout = monitoring["timeout_seconds"]
                if not isinstance(timeout, (int, float)) or timeout <= 0:
                    raise ConfigValidationError(
                        "monitoring.timeout_seconds must be a positive number"
                    )
                if timeout > 300:
                    warnings.append(
                        f"monitoring.timeout_seconds is very high ({timeout}s). "
                        "Consider reducing it to avoid slow checks."
                    )

        # Validate circuit breaker configuration
        if "circuit_breaker" in config:
            cb = config["circuit_breaker"]
            if "failure_threshold" in cb:
                threshold = cb["failure_threshold"]
                if not isinstance(threshold, int) or threshold < 1:
                    raise ConfigValidationError(
                        "circuit_breaker.failure_threshold must be a positive integer"
                    )

        logger.info(f"Configuration validated successfully: {len(sites)} site(s)")
        return warnings
