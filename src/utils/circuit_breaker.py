"""Circuit breaker pattern implementation for failure management."""

import time
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Any
from threading import Lock


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking calls due to failures
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are blocked
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        expected_exception: type = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        self._lock = Lock()

        self.logger = logging.getLogger(self.__class__.__name__)

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call a function through the circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            Original exception: If function fails
        """
        with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise CircuitOpenError(
                        f"Circuit breaker is OPEN (failures: {self.failure_count})"
                    )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True

        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.logger.info(
                    "Circuit breaker recovering, returning to CLOSED state"
                )

            self.failure_count = 0
            self.state = CircuitState.CLOSED

    def _on_failure(self):
        """Handle failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    self.logger.warning(
                        f"Circuit breaker opening after {self.failure_count} failures"
                    )
                    self.state = CircuitState.OPEN

    def reset(self):
        """Manually reset the circuit breaker."""
        with self._lock:
            self.failure_count = 0
            self.last_failure_time = None
            self.state = CircuitState.CLOSED
            self.logger.info("Circuit breaker manually reset")

    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        with self._lock:
            return {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "last_failure_time": self.last_failure_time.isoformat()
                if self.last_failure_time
                else None,
                "threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            }

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.state == CircuitState.HALF_OPEN


class CircuitOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    pass
