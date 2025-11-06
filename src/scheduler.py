"""Scheduler for periodic monitoring checks using APScheduler."""

import logging
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.executors.pool import ThreadPoolExecutor


class MonitorScheduler:
    """Manage scheduled monitoring tasks."""

    def __init__(self, config: Dict[str, Any], blocking: bool = True):
        """
        Initialize the scheduler.

        Args:
            config: Configuration dictionary
            blocking: Whether to use blocking scheduler (for main thread)
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.jobs = {}

        # Configure executors
        executors = {"default": ThreadPoolExecutor(max_workers=5)}

        # Configure job defaults
        job_defaults = {
            "coalesce": True,  # Coalesce missed jobs
            "max_instances": 1,  # Only one instance of each job at a time
            "misfire_grace_time": 30,  # Grace time for misfired jobs
        }

        # Create scheduler
        if blocking:
            self.scheduler = BlockingScheduler(
                executors=executors, job_defaults=job_defaults, timezone="UTC"
            )
        else:
            self.scheduler = BackgroundScheduler(
                executors=executors, job_defaults=job_defaults, timezone="UTC"
            )

        # Add event listeners
        self.scheduler.add_listener(self._handle_job_error, EVENT_JOB_ERROR)

        self.scheduler.add_listener(self._handle_job_executed, EVENT_JOB_EXECUTED)

        self.logger.info(
            f"Scheduler initialized ({'blocking' if blocking else 'background'} mode)"
        )

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        minutes: Optional[int] = None,
        seconds: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Add a job that runs at intervals.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            minutes: Interval in minutes
            seconds: Interval in seconds
            **kwargs: Additional arguments for the function

        Returns:
            Job ID
        """
        # Get interval from config if not specified
        if minutes is None and seconds is None:
            minutes = self.config.get("monitoring", {}).get("interval_minutes", 15)

        # Create trigger
        if minutes:
            trigger = IntervalTrigger(minutes=minutes)
            interval_str = f"{minutes} minutes"
        else:
            trigger = IntervalTrigger(seconds=seconds)
            interval_str = f"{seconds} seconds"

        # Add job
        job = self.scheduler.add_job(
            func,
            trigger,
            id=job_id,
            name=f"Monitor Job: {job_id}",
            kwargs=kwargs,
            replace_existing=True,
        )

        self.jobs[job_id] = job
        self.logger.info(f"Added interval job '{job_id}' running every {interval_str}")

        return job_id

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        hour: int = None,
        minute: int = None,
        day_of_week: str = None,
        **kwargs,
    ) -> str:
        """
        Add a job that runs on a cron schedule.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            hour: Hour to run (0-23)
            minute: Minute to run (0-59)
            day_of_week: Day of week (mon, tue, wed, thu, fri, sat, sun)
            **kwargs: Additional arguments for the function

        Returns:
            Job ID
        """
        # Create cron trigger
        trigger = CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week)

        # Add job
        job = self.scheduler.add_job(
            func,
            trigger,
            id=job_id,
            name=f"Cron Job: {job_id}",
            kwargs=kwargs,
            replace_existing=True,
        )

        self.jobs[job_id] = job

        schedule_desc = []
        if hour is not None:
            schedule_desc.append(f"hour={hour}")
        if minute is not None:
            schedule_desc.append(f"minute={minute}")
        if day_of_week:
            schedule_desc.append(f"day={day_of_week}")

        self.logger.info(
            f"Added cron job '{job_id}' with schedule: {', '.join(schedule_desc)}"
        )

        return job_id

    def add_one_time_job(
        self, job_id: str, func: Callable, run_date: datetime, **kwargs
    ) -> str:
        """
        Add a one-time job.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            run_date: When to run the job
            **kwargs: Additional arguments for the function

        Returns:
            Job ID
        """
        job = self.scheduler.add_job(
            func,
            "date",
            run_date=run_date,
            id=job_id,
            name=f"One-time Job: {job_id}",
            kwargs=kwargs,
            replace_existing=True,
        )

        self.jobs[job_id] = job
        self.logger.info(f"Added one-time job '{job_id}' scheduled for {run_date}")

        return job_id

    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job.

        Args:
            job_id: Job identifier

        Returns:
            True if removed successfully
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.jobs:
                del self.jobs[job_id]
            self.logger.info(f"Removed job '{job_id}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove job '{job_id}': {e}")
            return False

    def pause_job(self, job_id: str) -> bool:
        """
        Pause a scheduled job.

        Args:
            job_id: Job identifier

        Returns:
            True if paused successfully
        """
        try:
            self.scheduler.pause_job(job_id)
            self.logger.info(f"Paused job '{job_id}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to pause job '{job_id}': {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        """
        Resume a paused job.

        Args:
            job_id: Job identifier

        Returns:
            True if resumed successfully
        """
        try:
            self.scheduler.resume_job(job_id)
            self.logger.info(f"Resumed job '{job_id}'")
            return True
        except Exception as e:
            self.logger.error(f"Failed to resume job '{job_id}': {e}")
            return False

    def get_job_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a job.

        Args:
            job_id: Job identifier

        Returns:
            Dictionary with job information or None
        """
        job = self.scheduler.get_job(job_id)
        if job:
            return {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time,
                "pending": job.pending,
                "trigger": str(job.trigger),
            }
        return None

    def list_jobs(self) -> List[Dict[str, Any]]:
        """
        List all scheduled jobs.

        Returns:
            List of job information dictionaries
        """
        jobs_info = []
        for job in self.scheduler.get_jobs():
            jobs_info.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time,
                    "pending": job.pending,
                    "trigger": str(job.trigger),
                }
            )
        return jobs_info

    def start(self):
        """Start the scheduler."""
        self.logger.info("Starting scheduler...")
        self.scheduler.start()
        self.logger.info("Scheduler started")

    def shutdown(self, wait: bool = True):
        """
        Shutdown the scheduler.

        Args:
            wait: Wait for running jobs to complete
        """
        self.logger.info("Shutting down scheduler...")
        self.scheduler.shutdown(wait=wait)
        self.logger.info("Scheduler shut down")

    def run_job_now(self, job_id: str) -> bool:
        """
        Run a job immediately.

        Args:
            job_id: Job identifier

        Returns:
            True if job was triggered
        """
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now())
                self.logger.info(f"Triggered immediate execution of job '{job_id}'")
                return True
            else:
                self.logger.error(f"Job '{job_id}' not found")
                return False
        except Exception as e:
            self.logger.error(f"Failed to run job '{job_id}' immediately: {e}")
            return False

    def _handle_job_error(self, event):
        """Handle job execution errors."""
        job = self.scheduler.get_job(event.job_id)
        if job:
            self.logger.error(
                f"Job '{job.name}' (ID: {event.job_id}) failed with error: {event.exception}"
            )

    def _handle_job_executed(self, event):
        """Handle successful job execution."""
        job = self.scheduler.get_job(event.job_id)
        if job:
            self.logger.debug(
                f"Job '{job.name}' (ID: {event.job_id}) executed successfully"
            )

    def get_next_run_times(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Get the next scheduled run times.

        Args:
            count: Number of upcoming runs to retrieve

        Returns:
            List of upcoming job runs
        """
        upcoming = []
        jobs = self.scheduler.get_jobs()

        # Sort jobs by next run time
        jobs_sorted = sorted(
            [j for j in jobs if j.next_run_time], key=lambda x: x.next_run_time
        )

        for job in jobs_sorted[:count]:
            upcoming.append(
                {"job_id": job.id, "job_name": job.name, "next_run": job.next_run_time}
            )

        return upcoming
