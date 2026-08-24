# Remy Setup

Remy has two halves:

1. **Local GUI** (`gui.py`) — where you create, edit, and delete
   reminders. They're saved to `data/reminders.json` inside the repo.
2. **Cloud scheduler** (`backend/reminder_scheduler.py`) — runs once an
   hour, reads that same `data/reminders.json`, identifies which
   reminders are due, and texts them via an email-to-SMS gateway.

The two halves are connected by git: after changing reminders in the GUI,
click **"Push to Cloud"** to commit and push `data/reminders.json`. The
cloud job pulls the latest copy of the repo before each run.

## How delivery works: email-to-SMS gateways

Every US carrier runs an email gateway that turns a plain email into a
text: an email sent to `<your-10-digit-number>@<carrier's domain>`
arrives on the phone as an SMS. No SMS account, no API key, no
per-message cost — just an email sent over SMTP.

**Trade-off:** this is an unofficial, carrier-run convenience, not a
supported API. It generally works reliably, but a few carriers have
discontinued or restricted their gateways over time, and delivery isn't
guaranteed the way a real SMS API's is. If your carrier's gateway ever
stops working, that's the first thing to suspect.

### Carrier gateway domains

| Carrier | Gateway domain |
|---|---|
| AT&T | `txt.att.net` |
| T-Mobile | `tmomail.net` |
| Verizon | `vtext.com` |
| Sprint (legacy) | `messaging.sprintpcs.com` |
| Google Fi | `msg.fi.google.com` |
| Cricket | `sms.cricketwireless.net` |
| Boost Mobile | `sms.myboostmobile.com` |
| US Cellular | `email.uscc.net` |
| MetroPCS | `mymetropcs.com` |

Your gateway address is your 10-digit number (no dashes or country code)
`@` the domain for your carrier, e.g. `5551234567@tmomail.net`.

## 1. Set up an SMTP sender (Gmail)

1. Turn on **2-Step Verification** on the Google account you'll send
   from, if it isn't already: https://myaccount.google.com/security
2. Generate an **App Password**: https://myaccount.google.com/apppasswords
   — pick any name (e.g. "Remy"), and Google gives you a 16-character
   password. This is what the scheduler authenticates with, not your
   normal Google password.

## 2. Set environment variables for the cloud scheduler

Add these to the cloud environment this project runs in:

| Variable | Example | Notes |
|---|---|---|
| `SMTP_HOST` | `smtp.gmail.com` | |
| `SMTP_PORT` | `587` | Optional, defaults to 587 |
| `SMTP_USERNAME` | `you@gmail.com` | The Gmail address you generated the App Password for |
| `SMTP_PASSWORD` | `abcdabcdabcdabcd` | The 16-character App Password, not your Google account password |
| `SMS_GATEWAY_EMAIL` | `5551234567@tmomail.net` | Your number + your carrier's gateway domain, from the table above |

## Managing reminders

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
- Carrier email-to-SMS gateways are unofficial; delivery can occasionally
  be delayed or dropped in a way a real SMS API wouldn't be.

## Running the scheduler manually (for testing)

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USERNAME=you@gmail.com
export SMTP_PASSWORD=your16charapppassword
export SMS_GATEWAY_EMAIL=5551234567@tmomail.net
python backend/reminder_scheduler.py
```
