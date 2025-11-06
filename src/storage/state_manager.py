"""State management for tracking check history and results."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import deque

from ..checkers.base_checker import CheckResult, CheckStatus


class StateManager:
    """Manage and persist monitoring state."""

    def __init__(
        self, state_file: str = "./logs/monitor_state.json", history_size: int = 100
    ):
        """
        Initialize state manager.

        Args:
            state_file: Path to state persistence file
            history_size: Number of historical results to keep
        """
        self.state_file = Path(state_file)
        self.history_size = history_size
        self.logger = logging.getLogger(self.__class__.__name__)

        # State data
        self.state = {
            "last_check_time": None,
            "last_results": {},
            "history": {},
            "statistics": {
                "total_checks": 0,
                "total_failures": 0,
                "consecutive_failures": {},
                "last_failure_time": {},
                "last_recovery_time": {},
            },
        }

        # Load existing state
        self.load_state()

    def load_state(self) -> bool:
        """
        Load state from file.

        Returns:
            True if loaded successfully
        """
        if not self.state_file.exists():
            self.logger.info("No existing state file, starting fresh")
            return False

        try:
            with open(self.state_file, "r") as f:
                loaded_state = json.load(f)

                # Merge loaded state with defaults
                self.state.update(loaded_state)

                # Convert ISO strings back to datetime objects where needed
                if self.state["last_check_time"]:
                    self.state["last_check_time"] = datetime.fromisoformat(
                        self.state["last_check_time"]
                    )

                self.logger.info(f"Loaded state from {self.state_file}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")
            return False

    def save_state(self) -> bool:
        """
        Save state to file.

        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Prepare state for JSON serialization
            state_to_save = self._prepare_for_serialization(self.state)

            # Write to file
            with open(self.state_file, "w") as f:
                json.dump(state_to_save, f, indent=2, default=str)

            self.logger.debug(f"Saved state to {self.state_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
            return False

    def record_result(self, result: CheckResult):
        """
        Record a check result.

        Args:
            result: Check result to record
        """
        check_type = result.check_type

        # Update last check time
        self.state["last_check_time"] = datetime.now()

        # Store last result
        self.state["last_results"][check_type] = result.to_dict()

        # Update history
        if check_type not in self.state["history"]:
            self.state["history"][check_type] = []

        history = self.state["history"][check_type]
        history.append(result.to_dict())

        # Trim history to size limit
        if len(history) > self.history_size:
            self.state["history"][check_type] = history[-self.history_size :]

        # Update statistics
        stats = self.state["statistics"]
        stats["total_checks"] += 1

        if result.is_failure:
            stats["total_failures"] += 1

            # Update consecutive failures
            if check_type not in stats["consecutive_failures"]:
                stats["consecutive_failures"][check_type] = 0
            stats["consecutive_failures"][check_type] += 1

            # Record failure time
            stats["last_failure_time"][check_type] = result.timestamp.isoformat()
        else:
            # Reset consecutive failures on success
            if check_type in stats["consecutive_failures"]:
                if stats["consecutive_failures"][check_type] > 0:
                    # This is a recovery
                    stats["last_recovery_time"][check_type] = (
                        result.timestamp.isoformat()
                    )
                stats["consecutive_failures"][check_type] = 0

        # Auto-save state
        self.save_state()

    def get_last_result(self, check_type: str) -> Optional[Dict[str, Any]]:
        """
        Get the last result for a check type.

        Args:
            check_type: Type of check

        Returns:
            Last result dictionary or None
        """
        return self.state["last_results"].get(check_type)

    def get_history(self, check_type: str, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent history for a check type.

        Args:
            check_type: Type of check
            count: Number of results to return

        Returns:
            List of recent results
        """
        if check_type not in self.state["history"]:
            return []

        history = self.state["history"][check_type]
        return history[-count:] if history else []

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.

        Returns:
            Statistics dictionary
        """
        return self.state["statistics"].copy()

    def get_consecutive_failures(self, check_type: str) -> int:
        """
        Get consecutive failure count for a check type.

        Args:
            check_type: Type of check

        Returns:
            Number of consecutive failures
        """
        return self.state["statistics"]["consecutive_failures"].get(check_type, 0)

    def is_recovering(self, check_type: str) -> bool:
        """
        Check if a check type is recovering from failures.

        Args:
            check_type: Type of check

        Returns:
            True if recovering
        """
        last_failure = self.state["statistics"]["last_failure_time"].get(check_type)
        last_recovery = self.state["statistics"]["last_recovery_time"].get(check_type)

        if not last_failure:
            return False

        if not last_recovery:
            return True

        # Check if failure is more recent than recovery
        return last_failure > last_recovery

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current state.

        Returns:
            Summary dictionary
        """
        summary = {
            "last_check": self.state["last_check_time"].isoformat()
            if self.state["last_check_time"]
            else None,
            "statistics": self.get_statistics(),
            "current_status": {},
        }

        # Add current status for each check type
        for check_type, result in self.state["last_results"].items():
            summary["current_status"][check_type] = {
                "status": result.get("status"),
                "success": result.get("success"),
                "last_checked": result.get("timestamp"),
                "response_time_ms": result.get("response_time_ms"),
            }

        return summary

    def clear_history(self, check_type: Optional[str] = None):
        """
        Clear history.

        Args:
            check_type: Specific check type to clear, or None for all
        """
        if check_type:
            if check_type in self.state["history"]:
                self.state["history"][check_type] = []
                self.logger.info(f"Cleared history for {check_type}")
        else:
            self.state["history"] = {}
            self.logger.info("Cleared all history")

        self.save_state()

    def _prepare_for_serialization(self, obj: Any) -> Any:
        """
        Prepare object for JSON serialization.

        Args:
            obj: Object to prepare

        Returns:
            Serializable version of object
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._prepare_for_serialization(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._prepare_for_serialization(item) for item in obj]
        else:
            return obj
