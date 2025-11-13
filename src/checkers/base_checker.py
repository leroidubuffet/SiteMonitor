"""Base checker interface and common data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any, List
import socket
import ipaddress
from urllib.parse import urlparse, urljoin
import httpx
import logging


class SSRFProtectionError(Exception):
    """Exception raised when SSRF protection blocks a request."""
    pass


class CheckStatus(Enum):
    """Status of a health check."""

    SUCCESS = "success"
    WARNING = "warning"
    FAILURE = "failure"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class CheckResult:
    """Result of a health check."""

    check_type: str
    timestamp: datetime
    status: CheckStatus
    success: bool
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    error_message: Optional[str] = None
    warning_message: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if the result indicates success."""
        return self.status == CheckStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        """Check if the result indicates failure."""
        return self.status in [
            CheckStatus.FAILURE,
            CheckStatus.ERROR,
            CheckStatus.TIMEOUT,
        ]

    @property
    def is_warning(self) -> bool:
        """Check if the result indicates a warning."""
        return self.status == CheckStatus.WARNING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "check_type": self.check_type,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "success": self.success,
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "error_message": self.error_message,
            "warning_message": self.warning_message,
            "metrics": self.metrics,
            "details": self.details,
        }


class BaseChecker(ABC):
    """Abstract base class for all health checkers."""

    # Security limits
    MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10MB max response size
    MAX_HTML_PARSE_SIZE = 5 * 1024 * 1024  # 5MB max for HTML parsing

    def __init__(self, config: Dict[str, Any], client: Optional[httpx.Client] = None):
        """
        Initialize the checker.

        Args:
            config: Configuration dictionary
            client: Optional HTTPX client to reuse
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._client = client
        self.last_result: Optional[CheckResult] = None
        self.consecutive_failures = 0
        self.consecutive_successes = 0

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTPX client."""
        if self._client is None:
            timeout = httpx.Timeout(
                timeout=self.config.get("monitoring", {}).get("timeout_seconds", 30),
                connect=10.0,
                read=20.0,
                write=10.0,
                pool=5.0,
            )
            self._client = httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                http2=True,
                headers={
                    "User-Agent": self.config.get("monitoring", {}).get(
                        "user_agent", "InfoRuta-Monitor/1.0"
                    )
                },
            )
        return self._client

    def _validate_url(self, url: str, validate_dns: bool = True) -> bool:
        """
        Comprehensive URL validation to prevent SSRF attacks.

        Protects against:
        - Private IP addresses (10.x, 172.16-31.x, 192.168.x)
        - Localhost/loopback addresses
        - Link-local addresses (169.254.x.x)
        - Cloud metadata endpoints
        - IPv6 private ranges
        - DNS rebinding attacks (if validate_dns=True)
        - Malicious URL schemes

        Args:
            url: URL to validate
            validate_dns: If True, resolve DNS and validate the IP address

        Returns:
            True if URL is safe

        Raises:
            SSRFProtectionError: If URL is potentially unsafe
        """
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise SSRFProtectionError(f"Failed to parse URL: {e}")

        # 1. Validate URL scheme - only allow HTTP/HTTPS
        if parsed.scheme not in ["http", "https"]:
            raise SSRFProtectionError(
                f"Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed."
            )

        # 2. Ensure hostname is present
        if not parsed.hostname:
            raise SSRFProtectionError("URL must have a valid hostname")

        hostname = parsed.hostname.lower()

        # 3. Block localhost and loopback addresses (multiple representations)
        localhost_patterns = [
            "localhost", "127.0.0.1", "::1", "0.0.0.0",
            "0000:0000:0000:0000:0000:0000:0000:0001",
            "[::1]", "[0:0:0:0:0:0:0:1]"
        ]
        if hostname in localhost_patterns or hostname.startswith("127."):
            raise SSRFProtectionError(f"Localhost addresses are not allowed: {hostname}")

        # 4. Block cloud metadata endpoints
        metadata_endpoints = [
            "169.254.169.254",  # AWS, Azure, GCP, Oracle Cloud
            "metadata.google.internal",  # GCP alternative
            "metadata", "instance-data",  # Generic metadata hostnames
            "fd00:ec2::254",  # AWS IPv6 metadata
        ]
        if hostname in metadata_endpoints or hostname.startswith("169.254."):
            raise SSRFProtectionError(
                f"Cloud metadata endpoints are not allowed: {hostname}"
            )

        # 5. Check if hostname is an IP address and validate it
        try:
            ip = ipaddress.ip_address(hostname.strip("[]"))  # Strip brackets for IPv6

            # Block private IP addresses
            if ip.is_private:
                raise SSRFProtectionError(
                    f"Private IP addresses are not allowed: {ip}"
                )

            # Block loopback addresses
            if ip.is_loopback:
                raise SSRFProtectionError(
                    f"Loopback addresses are not allowed: {ip}"
                )

            # Block link-local addresses
            if ip.is_link_local:
                raise SSRFProtectionError(
                    f"Link-local addresses are not allowed: {ip}"
                )

            # Block multicast addresses
            if ip.is_multicast:
                raise SSRFProtectionError(
                    f"Multicast addresses are not allowed: {ip}"
                )

            # Block reserved addresses
            if ip.is_reserved:
                raise SSRFProtectionError(
                    f"Reserved IP addresses are not allowed: {ip}"
                )

            # Additional IPv6-specific checks
            if isinstance(ip, ipaddress.IPv6Address):
                # Block Unique Local Addresses (fc00::/7) - IPv6 equivalent of private IPs
                if ip.packed[0] & 0xfe == 0xfc:
                    raise SSRFProtectionError(
                        f"IPv6 Unique Local Addresses are not allowed: {ip}"
                    )

                # Block IPv6-mapped IPv4 addresses that are private
                if ip.ipv4_mapped:
                    ipv4 = ip.ipv4_mapped
                    if ipv4.is_private or ipv4.is_loopback or ipv4.is_link_local:
                        raise SSRFProtectionError(
                            f"IPv6-mapped private IPv4 addresses are not allowed: {ip}"
                        )

        except ValueError:
            # Not an IP address - it's a hostname
            # Additional hostname-based checks

            # Block common private IP patterns in hostname strings
            private_ip_prefixes = [
                "10.", "172.16.", "172.17.", "172.18.", "172.19.",
                "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                "172.30.", "172.31.", "192.168."
            ]
            if any(hostname.startswith(prefix) for prefix in private_ip_prefixes):
                raise SSRFProtectionError(
                    f"Private IP ranges are not allowed: {hostname}"
                )

            # DNS resolution validation to prevent DNS rebinding attacks
            if validate_dns:
                try:
                    resolved_ip = self._resolve_and_validate_dns(hostname)
                    self.logger.debug(f"DNS validation passed: {hostname} -> {resolved_ip}")
                except SSRFProtectionError:
                    raise
                except Exception as e:
                    raise SSRFProtectionError(
                        f"Failed to resolve hostname '{hostname}': {e}"
                    )

        return True

    def _resolve_and_validate_dns(self, hostname: str) -> str:
        """
        Resolve hostname to IP and validate it's not private/internal.

        Prevents DNS rebinding attacks where a hostname resolves to a private IP.

        Args:
            hostname: Hostname to resolve

        Returns:
            Resolved IP address (as string)

        Raises:
            SSRFProtectionError: If hostname resolves to private/internal IP
        """
        try:
            # Resolve hostname to IP address
            resolved_ip_str = socket.gethostbyname(hostname)

            # Validate the resolved IP address
            resolved_ip = ipaddress.ip_address(resolved_ip_str)

            # Check if resolved IP is private/internal
            if resolved_ip.is_private:
                raise SSRFProtectionError(
                    f"Hostname '{hostname}' resolves to private IP: {resolved_ip}"
                )

            if resolved_ip.is_loopback:
                raise SSRFProtectionError(
                    f"Hostname '{hostname}' resolves to loopback address: {resolved_ip}"
                )

            if resolved_ip.is_link_local:
                raise SSRFProtectionError(
                    f"Hostname '{hostname}' resolves to link-local address: {resolved_ip}"
                )

            if resolved_ip.is_reserved or resolved_ip.is_multicast:
                raise SSRFProtectionError(
                    f"Hostname '{hostname}' resolves to reserved/multicast IP: {resolved_ip}"
                )

            return resolved_ip_str

        except socket.gaierror as e:
            raise SSRFProtectionError(
                f"Failed to resolve hostname '{hostname}': {e}"
            )

    def _validate_redirect_url(self, redirect_url: str, base_url: str) -> bool:
        """
        Validate a redirect URL to prevent SSRF via redirects.

        Handles both absolute and relative redirect URLs.

        Args:
            redirect_url: URL from a redirect response (may be relative)
            base_url: Base URL to resolve relative redirects against

        Returns:
            True if redirect URL is safe

        Raises:
            SSRFProtectionError: If redirect URL is unsafe
        """
        # Handle relative redirects by converting to absolute URL
        if not redirect_url:
            self.logger.warning("Empty redirect URL, skipping validation")
            return True

        # Check if redirect_url is relative (no scheme)
        parsed = urlparse(redirect_url)
        if not parsed.scheme:
            # Relative URL - resolve against base URL
            absolute_redirect_url = urljoin(base_url, redirect_url)
            self.logger.debug(
                f"Resolved relative redirect: {redirect_url} -> {absolute_redirect_url}"
            )
            redirect_url = absolute_redirect_url

        self.logger.debug(f"Validating redirect URL: {redirect_url}")
        return self._validate_url(redirect_url, validate_dns=True)

    def _make_request(
        self,
        method: str,
        url: str,
        validate_dns: bool = True,
        **kwargs
    ) -> httpx.Response:
        """
        Make an HTTP request with SSRF protection.

        This method should be used instead of calling self.client.get/post directly.

        Args:
            method: HTTP method ('get', 'post', 'put', 'delete', etc.)
            url: URL to request
            validate_dns: If True, resolve and validate DNS
            **kwargs: Additional arguments to pass to httpx request

        Returns:
            httpx.Response object

        Raises:
            SSRFProtectionError: If URL validation fails
            httpx.HTTPError: For HTTP-related errors
        """
        # Validate URL before making request
        try:
            self._validate_url(url, validate_dns=validate_dns)
        except SSRFProtectionError as e:
            self.logger.error(f"SSRF protection blocked request to {url}: {e}")
            raise

        # Make the request
        try:
            response = getattr(self.client, method.lower())(url, **kwargs)

            # Check for redirects and validate them
            if response.history:
                # Track the base URL for resolving relative redirects
                current_url = url

                for hist_response in response.history:
                    if hist_response.is_redirect:
                        redirect_url = hist_response.headers.get('location')
                        if redirect_url:
                            try:
                                # Validate redirect (handles both absolute and relative URLs)
                                self._validate_redirect_url(redirect_url, current_url)

                                # Update current_url for next redirect in chain
                                parsed = urlparse(redirect_url)
                                if parsed.scheme:
                                    # Absolute URL
                                    current_url = redirect_url
                                else:
                                    # Relative URL - resolve it
                                    current_url = urljoin(current_url, redirect_url)

                            except SSRFProtectionError as e:
                                self.logger.error(
                                    f"SSRF protection blocked redirect from {current_url} to {redirect_url}: {e}"
                                )
                                raise

            return response

        except SSRFProtectionError:
            raise
        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error for {url}: {e}")
            raise

    @abstractmethod
    def check(self) -> CheckResult:
        """
        Perform the health check.

        Returns:
            CheckResult object with the check results
        """
        pass

    @abstractmethod
    def get_check_type(self) -> str:
        """
        Get the type identifier for this checker.

        Returns:
            String identifier for the check type
        """
        pass

    def update_consecutive_counts(self, result: CheckResult) -> None:
        """Update consecutive success/failure counts."""
        if result.is_success:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
        elif result.is_failure:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
        self.last_result = result

    def should_alert(self, result: CheckResult) -> bool:
        """
        Determine if an alert should be sent for this result.

        Args:
            result: The check result

        Returns:
            True if an alert should be sent
        """
        # Alert on state changes
        if self.last_result is None:
            return result.is_failure

        # Alert when transitioning from success to failure
        if self.last_result.is_success and result.is_failure:
            return True

        # Alert when recovering from failure to success
        if self.last_result.is_failure and result.is_success:
            return True

        # Alert on warnings after multiple occurrences
        if result.is_warning and self.consecutive_failures >= 3:
            return True

        return False

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._client:
            self._client.close()
            self._client = None

    def _check_response_size(self, response: httpx.Response, max_size: int = None) -> bool:
        """
        Check if response size is within acceptable limits.

        Args:
            response: HTTPX response object
            max_size: Maximum allowed size in bytes (default: MAX_RESPONSE_SIZE)

        Returns:
            True if size is acceptable, False otherwise
        """
        max_size = max_size or self.MAX_RESPONSE_SIZE

        # Check Content-Length header if present
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > max_size:
                    self.logger.warning(
                        f"Response size ({size} bytes) exceeds limit ({max_size} bytes)"
                    )
                    return False
            except ValueError:
                pass  # Invalid Content-Length, continue

        # Check actual content size
        content_size = len(response.content)
        if content_size > max_size:
            self.logger.warning(
                f"Response content ({content_size} bytes) exceeds limit ({max_size} bytes)"
            )
            return False

        return True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()

    def measure_performance_metrics(self, response: httpx.Response) -> Dict[str, float]:
        """
        Extract performance metrics from HTTP response.

        Args:
            response: HTTPX response object

        Returns:
            Dictionary of performance metrics in milliseconds
        """
        metrics = {}

        # Get timing information from response
        if hasattr(response, "elapsed"):
            metrics["total_time_ms"] = response.elapsed.total_seconds() * 1000

        # If available, get detailed timing metrics
        if hasattr(response, "_request") and hasattr(response._request, "extensions"):
            extensions = response._request.extensions

            if "http2" in extensions:
                metrics["protocol"] = "HTTP/2"
            else:
                metrics["protocol"] = "HTTP/1.1"

        return metrics
