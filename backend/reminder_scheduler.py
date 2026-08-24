"""
Cloud-side reminder checker.

Meant to be run hourly (e.g. by a Claude Code Remote Routine / cron job).
Reads data/reminders.json (synced from the local Remy GUI via git) and
figures out which reminders are due for the current hour.

Because it only runs once an hour, "at a specific time" reminders fire
sometime during the hour that contains that time (matched by hour, not
exact minute), and "every hour" reminders fire once per run while inside
their configured window. That granularity is a deliberate trade-off for
running on a low-cost hourly schedule rather than an always-on process.

No delivery provider is wired up yet — deliver_reminder() below is where
one goes. Until then, this just logs what's due.
"""
import os
import sys
import logging
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.reminders_storage import RemindersManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def deliver_reminder(message):
    """
    Send a due reminder somewhere. No provider is configured yet — plug one
    in here (e.g. an HTTP call to an SMS/email/push API) when one is chosen.
    """
    raise NotImplementedError("No delivery provider configured yet.")


def is_due(schedule, now):
    days = schedule.get("days_of_week") or []
    if days and now.weekday() not in days:
        return False

    if schedule.get("type") == "hourly":
        start_h = schedule.get("start_hour", 0)
        end_h = schedule.get("end_hour", 23)
        return start_h <= now.hour <= end_h
    else:
        time_str = schedule.get("time", "00:00")
        try:
            target_hour = int(time_str.split(":")[0])
        except (ValueError, IndexError):
            return False
        return now.hour == target_hour


def run():
    manager = RemindersManager()
    tz_name = manager.get_timezone()
    now = datetime.now(ZoneInfo(tz_name)) if ZoneInfo else datetime.now()

    logger.info(f"Checking reminders at {now.isoformat()} ({tz_name})")

    reminders = manager.list_reminders()
    due_count = 0
    for reminder in reminders:
        if not reminder.get("active", True):
            continue
        schedule = reminder.get("schedule", {})
        if not is_due(schedule, now):
            continue

        due_count += 1
        message = reminder.get("message", "")
        try:
            deliver_reminder(message)
            logger.info(f"Delivered reminder {reminder.get('id')}: {message!r}")
        except NotImplementedError:
            logger.info(f"Due but not delivered (no provider configured) {reminder.get('id')}: {message!r}")
        except Exception as e:
            logger.error(f"Failed to deliver reminder {reminder.get('id')} ({message!r}): {e}")

    logger.info(f"Done. {due_count} reminder(s) due, {len(reminders)} total.")


if __name__ == "__main__":
    run()
