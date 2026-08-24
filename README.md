# Remy

A reminder agent. Set up recurring reminders — "workout for 10 minutes"
every hour, "get groceries" on Fridays — from a desktop GUI, checked on
schedule by an hourly cloud job.

**Delivery provider not yet configured.** The scheduler identifies which
reminders are due each hour but doesn't send them anywhere yet — see
`backend/reminder_scheduler.py`'s `deliver_reminder()` for where one plugs
in (SMS, email, push, etc.).

## How it works

- **`gui.py`** — desktop app (customtkinter) for managing reminders.
  Saves to `data/reminders.json`.
- **`backend/reminder_scheduler.py`** — runs hourly in the cloud and
  checks which reminders are due. Delivery is a stub until a provider is
  chosen.
- `data/reminders.json` is the sync point between the two: the GUI's
  "Push to Cloud" button commits and pushes it so the cloud job sees your
  latest changes.

See [`docs/setup.md`](docs/setup.md) for running the app.

## Quick start

```bash
pip install -r requirements.txt
python gui.py
```
