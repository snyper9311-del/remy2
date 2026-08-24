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
The email itself is sent through the Gmail API over HTTPS rather than
raw SMTP — this runs in a sandboxed cloud job whose network policy only
permits HTTP(S) traffic, so a direct smtplib connection cannot open at
all (confirmed: it fails with "Address family not supported by
protocol" regardless of credentials). The Gmail API is a plain HTTPS
POST, which works fine through that same policy.

Authentication is OAuth2 with a stored refresh token — see
scripts/gmail_oauth_setup.py for the one-time local authorization that
produces it (run on your own machine, not here; it needs a real browser).

Required environment variables:
    GMAIL_CLIENT_ID     - OAuth Client ID from Google Cloud Console
    GMAIL_CLIENT_SECRET - OAuth Client Secret from Google Cloud Console
    GMAIL_REFRESH_TOKEN - from the one-time local authorization
                          (scripts/gmail_oauth_setup.py)
    GMAIL_FROM_EMAIL    - the Gmail address that authorized the app
    SMS_GATEWAY_EMAIL   - your phone's carrier gateway address, e.g.
                          "5551234567@tmomail.net" (see docs/setup.md for
                          other carriers' gateway domains)
"""
import os
import sys
import logging
import urllib.request
import urllib.error
import urllib.parse
import json
import base64
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

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def _post_json(url, data=None, headers=None, form=False):
    body = urllib.parse.urlencode(data).encode("utf-8") if form else json.dumps(data).encode("utf-8")
    default_headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    default_headers.update(headers or {})
    request = urllib.request.Request(url, data=body, headers=default_headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def _get_access_token(client_id, client_secret, refresh_token):
    """Exchange a stored refresh token for a short-lived access token."""
    result = _post_json(GOOGLE_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, form=True)
    return result["access_token"]


def deliver_reminder(message):
    """Email a reminder to a carrier's SMS gateway address via the Gmail API."""
    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")
    refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN")
    from_email = os.environ.get("GMAIL_FROM_EMAIL")
    to_gateway = os.environ.get("SMS_GATEWAY_EMAIL")

    missing = [name for name, val in [
        ("GMAIL_CLIENT_ID", client_id),
        ("GMAIL_CLIENT_SECRET", client_secret),
        ("GMAIL_REFRESH_TOKEN", refresh_token),
        ("GMAIL_FROM_EMAIL", from_email),
        ("SMS_GATEWAY_EMAIL", to_gateway),
    ] if not val]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    try:
        access_token = _get_access_token(client_id, client_secret, refresh_token)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Google OAuth token refresh failed ({e.code}): {body}. "
            f"If this is an 'invalid_grant' error, the refresh token has "
            f"expired or been revoked — re-run scripts/gmail_oauth_setup.py."
        )

    # Carrier gateways render the email body as the text; subject is
    # generally ignored or, worse, prepended to the message, so leave it
    # blank rather than risk a mangled reminder.
    email_msg = MIMEText(message)
    email_msg["Subject"] = ""
    email_msg["From"] = from_email
    email_msg["To"] = to_gateway
    raw = base64.urlsafe_b64encode(email_msg.as_bytes()).decode("utf-8")

    try:
        _post_json(GMAIL_SEND_URL, data={"raw": raw}, headers={"Authorization": f"Bearer {access_token}"})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gmail API {e.code}: {body}")


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
