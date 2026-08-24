# Remy

A reminder agent. Set up recurring reminders — "workout for 10 minutes"
every hour, "get groceries" on Fridays — from a desktop GUI, and get them
texted to you on schedule by an hourly cloud job.

## How it works

- **`gui.py`** — desktop app (customtkinter) for managing reminders.
  Saves to `data/reminders.json`.
- **`backend/reminder_scheduler.py`** — runs hourly in the cloud, checks
  which reminders are due, and sends each one as a text via your
  carrier's email-to-SMS gateway (no SMS account or API needed — just
  SMTP).
- `data/reminders.json` is the sync point between the two: the GUI's
  "Push to Cloud" button commits and pushes it so the cloud job sees your
  latest changes.

See [`docs/setup.md`](docs/setup.md) for full setup instructions (SMTP
sender, carrier gateway address, running the app).

## Quick start

```bash
pip install -r requirements.txt
python gui.py
```
