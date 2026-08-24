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

Delivery is via an email-to-SMS carrier gateway: an email to
<phone-number>@<carrier's gateway domain> arrives on the phone as a text.
The email itself is sent through SendGrid's HTTPS API rather than raw
SMTP — this runs in a sandboxed cloud job whose network policy only
permits HTTP(S) traffic, so a direct smtplib connection cannot open at
all (confirmed: it fails with "Address family not supported by
protocol" regardless of credentials). SendGrid's API is a plain HTTPS
POST, which works fine through that same policy.

Required environment variables:
    SENDGRID_API_KEY   - SendGrid API key (Settings > API Keys in the
                          SendGrid dashboard; needs "Mail Send" access)
    SENDGRID_FROM_EMAIL - the email address you verified in SendGrid under
                          Settings > Sender Authentication > Single Sender
                          Verification
    SMS_GATEWAY_EMAIL  - your phone's carrier gateway address, e.g.
                          "5551234567@tmomail.net" (see docs/setup.md for
                          other carriers' gateway domains)
"""
import os
import sys
import logging
import urllib.request
import urllib.error
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

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def deliver_reminder(message):
    """Email a reminder to a carrier's SMS gateway address via SendGrid's API."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL")
    to_gateway = os.environ.get("SMS_GATEWAY_EMAIL")

    missing = [name for name, val in [
        ("SENDGRID_API_KEY", api_key),
        ("SENDGRID_FROM_EMAIL", from_email),
        ("SMS_GATEWAY_EMAIL", to_gateway),
    ] if not val]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    # Carrier gateways render the email body as the text; subject is
    # generally ignored or, worse, prepended to the message, so leave it
    # blank rather than risk a mangled reminder.
    payload = {
        "personalizations": [{"to": [{"email": to_gateway}]}],
        "from": {"email": from_email},
        "subject": " ",
        "content": [{"type": "text/plain", "value": message}],
    }
    request = urllib.request.Request(
        SENDGRID_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"SendGrid {e.code}: {body}")


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
