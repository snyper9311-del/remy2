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

Delivery is via Textbelt's HTTPS SMS API — a single API key, no OAuth,
no email gateway, no phone number to buy. Requires a paid Textbelt key;
the free "textbelt" test key is disabled for US numbers.

Required environment variables:
    TEXTBELT_API_KEY - your paid Textbelt API key (textbelt.com)
    TEXTBELT_PHONE   - the phone number to text, e.g. "19177697261"
"""
import os
import sys
import logging
import urllib.request
import urllib.error
import urllib.parse
import json
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

TEXTBELT_URL = "https://textbelt.com/text"


def deliver_reminder(message):
    """Send a due reminder as a text via Textbelt."""
    api_key = os.environ.get("TEXTBELT_API_KEY")
    phone = os.environ.get("TEXTBELT_PHONE")

    missing = [name for name, val in [
        ("TEXTBELT_API_KEY", api_key),
        ("TEXTBELT_PHONE", phone),
    ] if not val]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    body = urllib.parse.urlencode({"phone": phone, "message": message, "key": api_key}).encode("utf-8")
    request = urllib.request.Request(
        TEXTBELT_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())

    if not result.get("success"):
        raise RuntimeError(f"Textbelt error: {result.get('error', 'unknown error')}")


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
        except Exception as e:
            logger.error(f"Failed to deliver reminder {reminder.get('id')} ({message!r}): {e}")

    logger.info(f"Done. {due_count} reminder(s) due, {len(reminders)} total.")


if __name__ == "__main__":
    run()
