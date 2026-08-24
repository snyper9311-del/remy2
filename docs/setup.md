# Remy Setup

Remy has two halves:

1. **Local GUI** (`gui.py`) — where you create, edit, and delete
   reminders. They're saved to `data/reminders.json` inside the repo.
2. **Cloud scheduler** (`backend/reminder_scheduler.py`) — runs once an
   hour, reads that same `data/reminders.json`, identifies which
   reminders are due, and texts them via Textbelt.

The two halves are connected by git: after changing reminders in the GUI,
click **"Push to Cloud"** to commit and push `data/reminders.json`. The
cloud job pulls the latest copy of the repo before each run.

## Delivery: Textbelt

A single HTTPS API call, no OAuth, no email gateway, no phone number to
buy.

1. Go to https://textbelt.com and buy credits (no subscription — pay
   once, use them over time). A few cents covers a personal reminder bot
   for a long time.
2. **The free "textbelt" test key does not work for US numbers** —
   Textbelt disabled it there due to abuse. Don't spend time on it; go
   straight to a paid key.
3. Set two environment variables in the cloud environment this project
   runs in:

| Variable | Example | Notes |
|---|---|---|
| `TEXTBELT_API_KEY` | `abc123...` | Your paid key from textbelt.com |
| `TEXTBELT_PHONE` | `19177697261` | Your number, no `+`, no dashes |

That's it — no sender verification, no domain, no browser-based
authorization step.

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
- Textbelt charges per text (fractions of a cent) — not free like the
  email-gateway trick, but far simpler and doesn't depend on a carrier's
  unofficial gateway staying up.

## Running the scheduler manually (for testing)

```bash
export TEXTBELT_API_KEY=abc123...
export TEXTBELT_PHONE=19177697261
python backend/reminder_scheduler.py
```
