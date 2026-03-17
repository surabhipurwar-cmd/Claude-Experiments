"""
scheduler.py — keeps the pipeline running and fires the report daily at EOD.

Usage:
    python scheduler.py

Configure via .env:
    REPORT_TIME=17:00       (24h, default 17:00)
    TIMEZONE=America/New_York
"""

import os
import time
import logging
from datetime import date

import schedule
import pytz
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scheduler] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

REPORT_TIME = os.getenv("REPORT_TIME", "17:00")
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")


def _now_in_tz() -> str:
    tz = pytz.timezone(TIMEZONE)
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def run_daily_report() -> None:
    log.info("Triggering daily report pipeline …")
    try:
        from main import run_pipeline
        url = run_pipeline(since=date.today())
        if url:
            log.info(f"Report complete → {url}")
        else:
            log.warning("Pipeline ran but produced no output (no deals today?).")
    except Exception as exc:
        log.error(f"Pipeline failed: {exc}", exc_info=True)


def main() -> None:
    log.info(f"Scheduler starting. Report will fire daily at {REPORT_TIME} ({TIMEZONE}).")
    schedule.every().day.at(REPORT_TIME).do(run_daily_report)

    while True:
        schedule.run_pending()
        time.sleep(30)  # check every 30 seconds


if __name__ == "__main__":
    main()
