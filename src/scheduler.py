import time
import sys
import logging
import threading
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from src.agent import run_agent
from src import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("SCHEDULER")

_is_running = threading.Event()

def scheduled_job():
    """The task that runs on the schedule."""
    _is_running.set()  
    logger.info("--- TRIGGERING AUTOMATED RUN ---")
    try:
        summary = run_agent(verbose=True)
        logger.info(f"--- RUN COMPLETE: Sent {summary['total_sent']} emails. ---")
    except Exception as e:
        logger.error(f"Scheduled run failed: {str(e)}")
    finally:
        _is_running.clear()

def get_next_run_time(hour, minute, timezone_str):
    """Calculate the next occurrence of the scheduled time."""
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if next_run <= now:
        next_run += timedelta(days=1)
    return next_run

def countdown_monitor(hour, minute, timezone_str):
    """Background thread to print a live ticking clock in the terminal."""
    try:
        while True:
            if _is_running.is_set():
                time.sleep(1)
                continue
                
            next_run = get_next_run_time(hour, minute, timezone_str)
            diff = next_run - datetime.now(pytz.timezone(timezone_str))
            
            total_seconds = int(diff.total_seconds())
            if total_seconds < 0:
                time.sleep(1)
                continue

            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            sys.stdout.write(f"\r[SCHEDULER] Next run in: {hours:02d}h {minutes:02d}m {seconds:02d}s (at {next_run.strftime('%H:%M')} {timezone_str})   ")
            sys.stdout.flush()
            
            time.sleep(1)
    except Exception as e:
        pass

def start_scheduler():
    """Initialize and start the background scheduler with countdown."""
    tz_name = config.TIMEZONE
    hour = config.SCHEDULE_HOUR
    minute = config.SCHEDULE_MINUTE
    
    scheduler = BackgroundScheduler(timezone=tz_name)
    trigger = CronTrigger(hour=hour, minute=minute, timezone=tz_name)
    
    scheduler.add_job(
        scheduled_job,
        trigger=trigger,
        name=f"Daily Finance Follow-up ({tz_name})"
    )
    
    scheduler.start()
    
    logger.info("="*60)
    logger.info(f" FINANCE AGENT SCHEDULER ACTIVE ")
    logger.info(f" Timezone : {tz_name}")
    logger.info(f" Daily Run: {hour:02d}:{minute:02d}")
    logger.info("="*60)
    
    monitor_thread = threading.Thread(
        target=countdown_monitor, 
        args=(hour, minute, tz_name), 
        daemon=True
    )
    monitor_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down...")
        scheduler.shutdown()

if __name__ == "__main__":
    start_scheduler()
