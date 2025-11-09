"""Base checker interface and common data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any, List
import httpx
import logging


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
