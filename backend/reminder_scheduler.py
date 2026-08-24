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

Delivery is via an email-to-SMS carrier gateway: sending a plain email to
<phone-number>@<carrier's gateway domain> arrives on the phone as a text.
No SMS account or API needed — just an SMTP sender.

Required environment variables:
    SMTP_HOST         - SMTP server, e.g. "smtp.gmail.com"
    SMTP_PORT         - SMTP port, e.g. "587" (defaults to 587 if unset)
    SMTP_USERNAME     - SMTP login (e.g. your Gmail address)
    SMTP_PASSWORD     - SMTP password (e.g. a Gmail App Password, not your
                         account password)
    SMS_GATEWAY_EMAIL - your phone's carrier gateway address, e.g.
                         "5551234567@tmomail.net" (see docs/setup.md for
                         other carriers' gateway domains)
"""
import os
import sys
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

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
    """Email a reminder to a carrier's SMS gateway address."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    to_gateway = os.environ.get("SMS_GATEWAY_EMAIL")

    missing = [name for name, val in [
        ("SMTP_HOST", smtp_host),
        ("SMTP_USERNAME", smtp_username),
        ("SMTP_PASSWORD", smtp_password),
        ("SMS_GATEWAY_EMAIL", to_gateway),
    ] if not val]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    # Carrier gateways render the email body as the text; subject is
    # generally ignored or, worse, prepended to the message, so leave it
    # blank rather than risk a mangled reminder.
    email_msg = MIMEText(message)
    email_msg["Subject"] = ""
    email_msg["From"] = smtp_username
    email_msg["To"] = to_gateway

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, [to_gateway], email_msg.as_string())


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
