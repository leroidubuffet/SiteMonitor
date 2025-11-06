"""Metrics collection and tracking."""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import deque, defaultdict
import statistics
import logging


class MetricsCollector:
    """Collect and analyze performance metrics."""

    def __init__(self, window_size: int = 100):
        """
        Initialize metrics collector.

        Args:
            window_size: Number of data points to keep in memory
        """
        self.window_size = window_size
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.logger = logging.getLogger(self.__class__.__name__)

        # Track uptime/downtime
        self.uptime_start: Optional[datetime] = None
        self.downtime_start: Optional[datetime] = None
        self.total_uptime = timedelta()
        self.total_downtime = timedelta()
        self.check_count = 0
        self.failure_count = 0

    def record_metric(
        self, name: str, value: float, timestamp: Optional[datetime] = None
    ):
        """
        Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        self.metrics[name].append({"value": value, "timestamp": timestamp})

        self.logger.debug(f"Recorded metric {name}: {value}")

    def record_check_result(self, success: bool, response_time_ms: float):
        """
        Record a check result.

        Args:
            success: Whether the check was successful
            response_time_ms: Response time in milliseconds
        """
        self.check_count += 1
        self.record_metric("response_time_ms", response_time_ms)

        if success:
            self.record_metric("success", 1)
            if self.downtime_start:
                # Ending downtime period
                downtime_duration = datetime.now() - self.downtime_start
                self.total_downtime += downtime_duration
                self.downtime_start = None
                self.logger.info(f"Downtime ended, duration: {downtime_duration}")

            if not self.uptime_start:
                self.uptime_start = datetime.now()
        else:
            self.failure_count += 1
            self.record_metric("success", 0)

            if self.uptime_start:
                # Ending uptime period
                uptime_duration = datetime.now() - self.uptime_start
                self.total_uptime += uptime_duration
                self.uptime_start = None
                self.logger.info(f"Uptime ended, duration: {uptime_duration}")

            if not self.downtime_start:
                self.downtime_start = datetime.now()

    def get_statistics(self, metric_name: str) -> Dict[str, Any]:
        """
        Get statistics for a metric.

        Args:
            metric_name: Name of the metric

        Returns:
            Dictionary with statistics
        """
        if metric_name not in self.metrics or not self.metrics[metric_name]:
            return {
                "count": 0,
                "mean": None,
                "median": None,
                "min": None,
                "max": None,
                "std_dev": None,
                "p95": None,
                "p99": None,
            }

        values = [point["value"] for point in self.metrics[metric_name]]

        stats = {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
        }

        if len(values) > 1:
            stats["std_dev"] = statistics.stdev(values)

            # Calculate percentiles
            sorted_values = sorted(values)
            p95_index = int(len(sorted_values) * 0.95)
            p99_index = int(len(sorted_values) * 0.99)

            stats["p95"] = sorted_values[min(p95_index, len(sorted_values) - 1)]
            stats["p99"] = sorted_values[min(p99_index, len(sorted_values) - 1)]
        else:
            stats["std_dev"] = 0
            stats["p95"] = values[0]
            stats["p99"] = values[0]

        return stats

    def get_availability(self) -> Dict[str, Any]:
        """
        Calculate availability metrics.

        Returns:
            Dictionary with availability metrics
        """
        # Update current period
        now = datetime.now()
        current_uptime = self.total_uptime
        current_downtime = self.total_downtime

        if self.uptime_start:
            current_uptime += now - self.uptime_start

        if self.downtime_start:
            current_downtime += now - self.downtime_start

        total_time = current_uptime + current_downtime

        if total_time.total_seconds() == 0:
            availability_percentage = 100.0
        else:
            availability_percentage = (
                current_uptime.total_seconds() / total_time.total_seconds() * 100
            )

        return {
            "availability_percentage": round(availability_percentage, 2),
            "total_uptime": str(current_uptime),
            "total_downtime": str(current_downtime),
            "total_checks": self.check_count,
            "failed_checks": self.failure_count,
            "success_rate": round(
                ((self.check_count - self.failure_count) / self.check_count * 100)
                if self.check_count > 0
                else 100,
                2,
            ),
        }

    def get_recent_metrics(
        self, metric_name: str, count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent metric values.

        Args:
            metric_name: Name of the metric
            count: Number of recent values to return

        Returns:
            List of recent metric values
        """
        if metric_name not in self.metrics:
            return []

        recent = list(self.metrics[metric_name])[-count:]
        return [
            {"value": point["value"], "timestamp": point["timestamp"].isoformat()}
            for point in recent
        ]

    def get_all_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of all metrics.

        Returns:
            Dictionary with all metrics summaries
        """
        summary = {"availability": self.get_availability(), "metrics": {}}

        for metric_name in self.metrics:
            summary["metrics"][metric_name] = self.get_statistics(metric_name)

        return summary

    def reset(self):
        """Reset all metrics."""
        self.metrics.clear()
        self.uptime_start = None
        self.downtime_start = None
        self.total_uptime = timedelta()
        self.total_downtime = timedelta()
        self.check_count = 0
        self.failure_count = 0
        self.logger.info("Metrics reset")
