"""
Cloud-side WhatsApp reminder sender.

Meant to be run hourly (e.g. by a Claude Code Remote Routine / cron job).
Reads data/reminders.json (synced from the local Remy GUI via git),
figures out which reminders are due for the current hour, and sends each
one as a WhatsApp message via the Twilio API.

Because it only runs once an hour, "at a specific time" reminders fire
sometime during the hour that contains that time (matched by hour, not
exact minute), and "every hour" reminders fire once per run while inside
their configured window. That granularity is a deliberate trade-off for
running on a low-cost hourly schedule rather than an always-on process.

Required environment variables:
    TWILIO_ACCOUNT_SID     - Twilio Account SID
    TWILIO_AUTH_TOKEN      - Twilio Auth Token
    TWILIO_WHATSAPP_FROM   - Twilio WhatsApp-enabled sender, e.g. "whatsapp:+14155238886"
    TWILIO_WHATSAPP_TO     - Your WhatsApp number to receive reminders, e.g. "whatsapp:+15551234567"
"""
import os
import sys
import logging
from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

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

TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

# Twilio codes that all mean the same thing in practice: WhatsApp won't accept
# free-form text right now because more than 24 hours have passed since the
# recipient last messaged the sender. 21654 is the one the sandbox returns.
SESSION_WINDOW_ERRORS = {21654, 63016}


def send_whatsapp_message(body, account_sid, auth_token, from_number, to_number):
    url = TWILIO_API_URL.format(sid=account_sid)
    response = requests.post(
        url,
        auth=HTTPBasicAuth(account_sid, auth_token),
        data={"From": from_number, "To": to_number, "Body": body},
        timeout=30,
    )
    if not response.ok:
        # Twilio's error body has the actual "code"/"message" the generic
        # HTTP status hides.
        try:
            code = response.json().get("code")
        except ValueError:
            code = None
        if code in SESSION_WINDOW_ERRORS:
            raise RuntimeError(
                f"Twilio {code}: WhatsApp's 24-hour window has closed. Send any "
                f"message from your WhatsApp to {from_number.replace('whatsapp:', '')} "
                f"to reopen it, then reminders resume. (raw: {response.text})"
            )
        raise RuntimeError(f"Twilio {response.status_code}: {response.text}")
    return response.json()


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
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM")
    to_number = os.environ.get("TWILIO_WHATSAPP_TO")

    missing = [name for name, val in [
        ("TWILIO_ACCOUNT_SID", account_sid),
        ("TWILIO_AUTH_TOKEN", auth_token),
        ("TWILIO_WHATSAPP_FROM", from_number),
        ("TWILIO_WHATSAPP_TO", to_number),
    ] if not val]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

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
            send_whatsapp_message(message, account_sid, auth_token, from_number, to_number)
            logger.info(f"Sent reminder {reminder.get('id')}: {message!r}")
        except Exception as e:
            logger.error(f"Failed to send reminder {reminder.get('id')} ({message!r}): {e}")

    logger.info(f"Done. {due_count} reminder(s) due, {len(reminders)} total.")


if __name__ == "__main__":
    run()
