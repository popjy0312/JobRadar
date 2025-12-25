"""
Scheduler module
Periodically checks job postings and sends notifications.
"""

import schedule
import time
import json
import os
from typing import List, Dict, Optional
import logging
from datetime import datetime, time as dt_time
import pytz
from .parser import get_parser
from .matcher import JobMatcher
from .notifier import Notifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobScheduler:
    """Job posting scheduler"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.job_keywords = config.get('job_keywords', [])
        self.exclude_keywords = config.get('exclude_keywords', [])
        self.sites = config.get('sites', [])
        self.sites_config = config.get('sites_config', [])
        
        # Schedule configuration
        schedule_config = config.get('schedule', {})
        self.schedule_times = schedule_config.get('times')  # Specific times list
        self.start_time = schedule_config.get('start_time')  # Start time for range
        self.end_time = schedule_config.get('end_time')  # End time for range
        self.interval_minutes = schedule_config.get('interval_minutes', 60)  # Interval in minutes
        
        # Legacy support: if old check_interval exists, use it
        if 'check_interval' in config and not schedule_config:
            self.interval_minutes = config.get('check_interval', 60)
        
        # Timezone: KST (UTC+9)
        self.tz_kst = pytz.timezone('Asia/Seoul')
        
        # Matcher and notification settings
        self.matcher = JobMatcher(
            keywords=self.job_keywords,
            exclude_keywords=self.exclude_keywords,
            threshold=config.get('similarity_threshold', 0.3)
        )
        self.notifier = Notifier(config.get('notifications', {}))
        
        # Track seen postings (prevent duplicate notifications)
        self.data_dir = 'data'
        os.makedirs(self.data_dir, exist_ok=True)
        self.history_file = os.path.join(self.data_dir, 'job_history.json')
        self.seen_jobs = self._load_history()
    
    def _load_history(self) -> set:
        """Load previously seen postings"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get('seen_job_ids', []))
            except Exception as e:
                logger.error(f"Error loading history: {e}")
        return set()
    
    def _save_history(self):
        """Save seen postings"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({'seen_job_ids': list(self.seen_jobs)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving history: {e}")
    
    def _get_job_id(self, job: Dict) -> str:
        """Generate unique ID for posting"""
        return f"{job.get('source', '')}_{job.get('link', '')}_{job.get('title', '')}"
    
    def _filter_new_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """Filter only new postings"""
        new_jobs = []
        for job in jobs:
            job_id = self._get_job_id(job)
            if job_id not in self.seen_jobs:
                new_jobs.append(job)
                self.seen_jobs.add(job_id)
        
        if new_jobs:
            self._save_history()
        
        return new_jobs
    
    def check_jobs(self):
        """Check job postings and send notifications"""
        logger.info("Checking for new job postings...")
        
        all_jobs = []
        
        # Collect postings from each site
        for site in self.sites:
            parser = get_parser(site, self.sites_config)
            if not parser:
                logger.warning(f"Unknown site: {site}. Check if it's configured in sites_config.")
                continue
            
            # Search with each keyword
            for keyword in self.job_keywords:
                try:
                    jobs = parser.parse(keyword)
                    if jobs:
                        all_jobs.extend(jobs)
                    time.sleep(1)  # Prevent site overload
                except Exception as e:
                    logger.error(f"Error parsing {site} with keyword {keyword}: {e}")
                    # Continue with other sites/keywords even if one fails
                    continue
        
        # Remove duplicates (same link)
        seen_links = set()
        unique_jobs = []
        for job in all_jobs:
            link = job.get('link', '')
            if link and link not in seen_links:
                seen_links.add(link)
                unique_jobs.append(job)
        
        # Job matching
        matched_jobs = self.matcher.filter_jobs(unique_jobs)
        
        # Filter only new postings
        new_jobs = self._filter_new_jobs(matched_jobs)
        
        # Send notifications
        if new_jobs:
            logger.info(f"Found {len(new_jobs)} new matching jobs!")
            self.notifier.notify(new_jobs)
        else:
            logger.info("No new matching jobs found.")
    
    def _parse_time(self, time_str: str) -> dt_time:
        """Parse time string (HH:MM) to time object"""
        try:
            hour, minute = map(int, time_str.split(':'))
            return dt_time(hour, minute)
        except ValueError:
            logger.error(f"Invalid time format: {time_str}. Expected HH:MM")
            raise
    
    def _get_kst_now(self) -> datetime:
        """Get current time in KST"""
        return datetime.now(self.tz_kst)
    
    def _is_within_time_range(self, current_time: dt_time, start_time: dt_time, end_time: dt_time) -> bool:
        """Check if current time is within the specified time range"""
        if start_time <= end_time:
            # Normal case: 09:00 to 18:00
            return start_time <= current_time <= end_time
        else:
            # Overnight case: 22:00 to 06:00
            return current_time >= start_time or current_time <= end_time
    
    def _should_check_now(self) -> bool:
        """Check if we should run check based on current time and schedule"""
        now_kst = self._get_kst_now()
        current_time = now_kst.time()
        
        # Method 1: Specific times list
        if self.schedule_times:
            current_time_str = current_time.strftime('%H:%M')
            return current_time_str in self.schedule_times
        
        # Method 2: Time range with interval
        if self.start_time and self.end_time:
            start = self._parse_time(self.start_time)
            end = self._parse_time(self.end_time)
            return self._is_within_time_range(current_time, start, end)
        
        # Method 3: 24-hour interval (always return True, schedule library handles timing)
        return True
    
    def _schedule_jobs(self):
        """Set up scheduled jobs based on configuration"""
        # Method 1: Specific times
        if self.schedule_times:
            for time_str in self.schedule_times:
                # Schedule at specific times (will check KST timezone in wrapper)
                schedule.every().day.at(time_str).do(self._check_jobs_with_time_validation)
            logger.info(f"Scheduled checks at: {', '.join(self.schedule_times)} (KST)")
        
        # Method 2: Time range with interval
        elif self.start_time and self.end_time:
            # For time range, we check every minute and validate if within range
            schedule.every(1).minutes.do(self._check_jobs_with_time_validation)
            logger.info(f"Scheduled checks from {self.start_time} to {self.end_time} "
                       f"every {self.interval_minutes} minutes (KST)")
            logger.info("Note: Checks will only run when within the specified time range")
        
        # Method 3: 24-hour interval
        else:
            schedule.every(self.interval_minutes).minutes.do(self.check_jobs)
            logger.info(f"Scheduled checks every {self.interval_minutes} minutes (24/7)")
    
    def _check_jobs_with_time_validation(self):
        """Wrapper to check jobs only if within scheduled time and interval"""
        if not self._should_check_now():
            return  # Outside scheduled time range
        
        # For interval-based scheduling, track last check time
        if self.start_time and self.end_time:
            if not hasattr(self, '_last_check_time'):
                self._last_check_time = None
            
            now_kst = self._get_kst_now()
            
            # Check if enough time has passed since last check
            if self._last_check_time:
                time_diff = (now_kst - self._last_check_time).total_seconds() / 60
                if time_diff < self.interval_minutes:
                    return  # Not enough time has passed, skip this check
            
            self._last_check_time = now_kst
        
        # Run the actual check
        self.check_jobs()
    
    def start(self):
        """Start scheduler"""
        logger.info("="*60)
        logger.info("Starting job scheduler")
        logger.info(f"Timezone: KST (Asia/Seoul, UTC+9)")
        logger.info(f"Current KST time: {self._get_kst_now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"Monitoring sites: {', '.join(self.sites)}")
        logger.info(f"Job keywords: {', '.join(self.job_keywords)}")
        logger.info("="*60)
        
        # First run (only if within time range)
        if self._should_check_now():
            logger.info("Running initial check (within scheduled time range)")
            self.check_jobs()
        else:
            logger.info("Skipping initial check (outside scheduled time range)")
        
        # Set up scheduled jobs
        self._schedule_jobs()
        
        # Run scheduler
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        finally:
            self._save_history()

