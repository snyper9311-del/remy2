# Remy Setup

Remy sends you scheduled WhatsApp messages (e.g. "workout for 10 minutes"
every hour, "get groceries" on Fridays). It has two halves:

1. **Local GUI** (`gui.py`) — where you create, edit, and delete
   reminders. They're saved to `data/reminders.json` inside the repo.
2. **Cloud scheduler** (`backend/reminder_scheduler.py`) — runs once an
   hour, reads that same `data/reminders.json`, and sends any due
   reminders to your WhatsApp via Twilio.

The two halves are connected by git: after changing reminders in the GUI,
click **"Push to Cloud"** to commit and push `data/reminders.json`. The
cloud job pulls the latest copy of the repo before each run.

## 1. Create a Twilio account & WhatsApp sender

1. Sign up for a free account at https://www.twilio.com/try-twilio.
2. In the Twilio Console, open **Messaging → Try it out → Send a WhatsApp message**
   to activate the WhatsApp Sandbox. You'll get:
   - A sandbox WhatsApp number (usually `+1 415 523 8886`).
   - A join code, e.g. "join some-word" — send that exact message from
     your own WhatsApp to the sandbox number to opt your number in.
     (The sandbox requires re-joining every ~72 hours of inactivity; for
     always-on use later, Twilio also supports provisioning your own
     WhatsApp-enabled number, which doesn't expire.)
3. From the Console dashboard, copy your **Account SID** and **Auth Token**.

## 2. Set environment variables for the cloud scheduler

The scheduler script (`backend/reminder_scheduler.py`) reads credentials
from environment variables — never hardcode them into the repo. Add these
to the cloud environment this project runs in:

| Variable | Example | Notes |
|---|---|---|
| `TWILIO_ACCOUNT_SID` | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` | From the Twilio Console |
| `TWILIO_AUTH_TOKEN` | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` | From the Twilio Console |
| `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` | Sandbox number (or your own), prefixed with `whatsapp:` |
| `TWILIO_WHATSAPP_TO` | `whatsapp:+15551234567` | Your personal WhatsApp number, prefixed with `whatsapp:` |

Once these are set, an hourly scheduled job can run `backend/reminder_scheduler.py`
to pull the latest repo and send due reminders.

## 3. Managing reminders

Run `python gui.py` to open Remy:

- **+ Add Reminder** — set the message text, and either:
  - *Every hour (within a window)* — fires once every hour between a
    start and end hour on the days you pick (e.g. 9:00–21:00, every day).
  - *At a specific time* — fires once during the hour containing that
    time, on the days you pick (e.g. 10:00 on Fridays).
- **Active** switch — pause a reminder without deleting it.
- **Timezone** — set the IANA timezone (e.g. `America/New_York`) used to
  evaluate schedules.
- **Push to Cloud** — commits and pushes `data/reminders.json` so the
  cloud job picks up your changes on its next hourly run.

## Known limitations

- The scheduler runs **once an hour**, so "at a specific time" reminders
  fire sometime during that hour, not necessarily at the exact minute.
- Changes only take effect after you click "Push to Cloud" — the cloud
  job doesn't see local, unpushed edits.
- The Twilio WhatsApp **sandbox** requires periodically re-sending the
  join code from your phone if you go ~72 hours without a message.
  Provisioning your own WhatsApp sender in Twilio removes this limit.

## Running the scheduler manually (for testing)

```bash
export TWILIO_ACCOUNT_SID=...
export TWILIO_AUTH_TOKEN=...
export TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
export TWILIO_WHATSAPP_TO=whatsapp:+15551234567
python backend/reminder_scheduler.py
```
