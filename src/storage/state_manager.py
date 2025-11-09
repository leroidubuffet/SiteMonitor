"""State management for tracking check history and results."""

import json
import logging
import os
import tempfile
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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

        # State data - now per-site
        # Structure: { "site_name": { last_check_time, last_results, history, statistics, circuit_breaker } }
        self.state = {
            "sites": {},
            "global": {
                "last_check_time": None,
                "total_checks": 0,
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
                if "sites" in loaded_state:
                    # New multi-site format
                    self.state.update(loaded_state)
                else:
                    # Old single-site format - migrate to new format
                    self.logger.info(
                        "Migrating old single-site state to multi-site format"
                    )
                    self._migrate_old_state(loaded_state)

                # Convert ISO strings back to datetime objects where needed
                if self.state.get("global", {}).get("last_check_time"):
                    self.state["global"]["last_check_time"] = datetime.fromisoformat(
                        self.state["global"]["last_check_time"]
                    )

                # Convert per-site timestamps
                for site_name, site_state in self.state.get("sites", {}).items():
                    if site_state.get("last_check_time"):
                        site_state["last_check_time"] = datetime.fromisoformat(
                            site_state["last_check_time"]
                        )

                self.logger.info(f"Loaded state from {self.state_file}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")
            return False

    def save_state(self) -> bool:
        """
        Save state to file using atomic write.

        Uses write-to-temp-then-rename pattern to prevent corruption
        if the program crashes mid-write.

        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Prepare state for JSON serialization
            state_to_save = self._prepare_for_serialization(self.state)

            # Atomic write: write to temporary file, then rename
            # This ensures either the old file or new file exists, never corrupted partial file
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.state_file.parent,
                prefix=f".{self.state_file.name}.",
                suffix=".tmp"
            )

            try:
                # Write to temporary file
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(state_to_save, f, indent=2, default=str)
                    # Ensure data is written to disk
                    f.flush()
                    os.fsync(f.fileno())

                # Atomically replace old file with new file
                # On POSIX systems, rename() is atomic
                os.replace(temp_path, str(self.state_file))

                self.logger.debug(f"Saved state to {self.state_file} (atomic write)")
                return True

            except Exception as write_error:
                # Clean up temp file if write failed
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass  # Temp file already deleted, ignore
                raise write_error

        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
            return False

    def _get_site_state(self, site_name: str) -> Dict[str, Any]:
        """
        Get or create state for a specific site.

        Args:
            site_name: Name of the site

        Returns:
            Site state dictionary
        """
        if site_name not in self.state["sites"]:
            self.state["sites"][site_name] = {
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
                "circuit_breaker": {
                    "is_open": False,
                    "failure_count": 0,
                    "last_failure": None,
                },
            }
        return self.state["sites"][site_name]

    def record_result(self, result: CheckResult, site_name: str = "default"):
        """
        Record a check result for a specific site.

        Args:
            result: Check result to record
            site_name: Name of the site being checked
        """
        check_type = result.check_type

        # Update global last check time
        self.state["global"]["last_check_time"] = datetime.now()
        self.state["global"]["total_checks"] += 1

        # Get site-specific state
        site_state = self._get_site_state(site_name)

        # Update site's last check time
        site_state["last_check_time"] = datetime.now()

        # Store last result
        site_state["last_results"][check_type] = result.to_dict()

        # Update history
        if check_type not in site_state["history"]:
            site_state["history"][check_type] = []

        history = site_state["history"][check_type]
        history.append(result.to_dict())

        # Trim history to size limit
        if len(history) > self.history_size:
            site_state["history"][check_type] = history[-self.history_size :]

        # Update statistics
        stats = site_state["statistics"]
        stats["total_checks"] += 1

        if result.is_failure:
            stats["total_failures"] += 1

            # Update consecutive failures
            if check_type not in stats["consecutive_failures"]:
                stats["consecutive_failures"][check_type] = 0
            stats["consecutive_failures"][check_type] += 1

            # Record failure time
            stats["last_failure_time"][check_type] = result.timestamp.isoformat()

            # Update circuit breaker
            site_state["circuit_breaker"]["failure_count"] += 1
            site_state["circuit_breaker"]["last_failure"] = result.timestamp.isoformat()
        else:
            # Reset consecutive failures on success
            if check_type in stats["consecutive_failures"]:
                if stats["consecutive_failures"][check_type] > 0:
                    # This is a recovery
                    stats["last_recovery_time"][check_type] = (
                        result.timestamp.isoformat()
                    )
                stats["consecutive_failures"][check_type] = 0

            # Reset circuit breaker on success
            site_state["circuit_breaker"]["failure_count"] = 0

        # Auto-save state
        self.save_state()

    def get_last_result(
        self, check_type: str, site_name: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """
        Get the last result for a check type on a specific site.

        Args:
            check_type: Type of check
            site_name: Name of the site

        Returns:
            Last result dictionary or None
        """
        site_state = self._get_site_state(site_name)
        return site_state["last_results"].get(check_type)

    def get_history(
        self, check_type: str, count: int = 10, site_name: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        Get recent history for a check type on a specific site.

        Args:
            check_type: Type of check
            count: Number of results to return
            site_name: Name of the site

        Returns:
            List of recent results
        """
        site_state = self._get_site_state(site_name)
        if check_type not in site_state["history"]:
            return []

        history = site_state["history"][check_type]
        return history[-count:] if history else []

    def get_statistics(self, site_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get monitoring statistics.

        Args:
            site_name: Name of the site, or None for global statistics

        Returns:
            Statistics dictionary
        """
        if site_name:
            site_state = self._get_site_state(site_name)
            return site_state["statistics"].copy()
        else:
            # Return global statistics
            return self.state["global"].copy()

    def get_consecutive_failures(
        self, check_type: str, site_name: str = "default"
    ) -> int:
        """
        Get consecutive failure count for a check type on a specific site.

        Args:
            check_type: Type of check
            site_name: Name of the site

        Returns:
            Number of consecutive failures
        """
        site_state = self._get_site_state(site_name)
        return site_state["statistics"]["consecutive_failures"].get(check_type, 0)

    def is_recovering(self, check_type: str, site_name: str = "default") -> bool:
        """
        Check if a check type is recovering from failures on a specific site.

        Args:
            check_type: Type of check
            site_name: Name of the site

        Returns:
            True if recovering
        """
        site_state = self._get_site_state(site_name)
        stats = site_state["statistics"]

        last_failure = stats["last_failure_time"].get(check_type)
        last_recovery = stats["last_recovery_time"].get(check_type)

        if not last_failure:
            return False

        if not last_recovery:
            return True

        # Check if failure is more recent than recovery
        return last_failure > last_recovery

    def get_all_sites(self) -> List[str]:
        """
        Get list of all monitored sites.

        Returns:
            List of site names
        """
        return list(self.state["sites"].keys())

    def get_summary(self, site_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a summary of the current state.

        Args:
            site_name: Name of the site, or None for all sites

        Returns:
            Summary dictionary
        """
        if site_name:
            # Single site summary
            site_state = self._get_site_state(site_name)
            summary = {
                "site_name": site_name,
                "last_check": site_state["last_check_time"].isoformat()
                if site_state["last_check_time"]
                else None,
                "statistics": site_state["statistics"].copy(),
                "current_status": {},
                "circuit_breaker": site_state["circuit_breaker"].copy(),
            }

            # Add current status for each check type
            for check_type, result in site_state["last_results"].items():
                summary["current_status"][check_type] = {
                    "status": result.get("status"),
                    "success": result.get("success"),
                    "last_checked": result.get("timestamp"),
                    "response_time_ms": result.get("response_time_ms"),
                }

            return summary
        else:
            # All sites summary
            summary = {
                "global": self.state["global"].copy(),
                "sites": {},
            }

            if summary["global"].get("last_check_time"):
                summary["global"]["last_check_time"] = summary["global"][
                    "last_check_time"
                ].isoformat()

            for site in self.get_all_sites():
                summary["sites"][site] = self.get_summary(site)

            return summary

    def clear_history(
        self, check_type: Optional[str] = None, site_name: Optional[str] = None
    ):
        """
        Clear history.

        Args:
            check_type: Specific check type to clear, or None for all
            site_name: Specific site to clear, or None for all sites
        """
        if site_name:
            # Clear specific site
            site_state = self._get_site_state(site_name)
            if check_type:
                if check_type in site_state["history"]:
                    site_state["history"][check_type] = []
                    self.logger.info(f"Cleared history for {check_type} on {site_name}")
            else:
                site_state["history"] = {}
                self.logger.info(f"Cleared all history for {site_name}")
        else:
            # Clear all sites
            for site in self.get_all_sites():
                self.clear_history(check_type, site)

        self.save_state()

    def _migrate_old_state(self, old_state: Dict[str, Any]):
        """
        Migrate old single-site state to new multi-site format.

        Args:
            old_state: Old state dictionary
        """
        # Migrate to "InfoRuta RCE" site (the original single site)
        site_name = "InfoRuta RCE"
        self.state["sites"][site_name] = {
            "last_check_time": old_state.get("last_check_time"),
            "last_results": old_state.get("last_results", {}),
            "history": old_state.get("history", {}),
            "statistics": old_state.get("statistics", {}),
            "circuit_breaker": {
                "is_open": False,
                "failure_count": 0,
                "last_failure": None,
            },
        }

        # Migrate global stats
        if "statistics" in old_state:
            self.state["global"]["total_checks"] = old_state["statistics"].get(
                "total_checks", 0
            )

        self.logger.info(f"Migrated old state to site '{site_name}'")

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
