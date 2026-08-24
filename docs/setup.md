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

## How delivery works: email-to-SMS gateway, sent via the Gmail API

Every US carrier runs an email gateway that turns a plain email into a
text: an email sent to `<your-10-digit-number>@<carrier's domain>`
arrives on the phone as an SMS. That part is free and needs no SMS
account — it's confirmed working for this setup.

The email itself is sent through the **Gmail API**, not raw SMTP. The
cloud scheduler runs in a sandboxed environment whose network policy only
allows HTTP(S) traffic — a direct SMTP connection can't open at all
there. The Gmail API is a plain HTTPS request, so it works fine, and it
sends as your own Gmail account rather than through a third-party email
service.

**Trade-off — read this before relying on it:** Google issues OAuth
refresh tokens that expire after **7 days** for apps in "Testing"
publishing status. If that turns out to apply here even after moving the
app to "Production" without full verification (untested — Google's own
docs don't spell out that specific case), reminders could silently stop
after a week until you re-run the authorization script below. If that
happens, `deliver_reminder()`'s error message will say `invalid_grant`
and tell you to re-authorize.

Carrier gateways are also unofficial and carrier-run, not a supported
API — a few carriers have discontinued or restricted theirs over time.

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

## 1. Set up a Google Cloud OAuth app

All in [console.cloud.google.com](https://console.cloud.google.com):

1. Create a project (or use an existing one).
2. **APIs & Services → Library** — search for and enable the **Gmail
   API**.
3. **APIs & Services → OAuth consent screen** — configure it:
   - User type: **External** (fine for a personal Gmail account).
   - Add the scope `https://www.googleapis.com/auth/gmail.send`.
   - Under Test users, add your own Gmail address.
   - Try **Publish App** to move it from Testing to Production — for a
     single personal user requesting this scope, Google may or may not
     require verification to do this. If it lets you publish without
     review, do it; that's the step that should avoid the 7-day token
     expiry above. If Google blocks it and demands verification, you can
     skip that for now and just accept re-running the authorization
     script periodically.
4. **APIs & Services → Credentials → Create Credentials → OAuth client
   ID**. Application type: **Desktop app**. Note the Client ID and
   Client Secret it gives you.

## 2. Run the one-time local authorization

**On your own machine**, not in a cloud session — this needs to open a
real browser for you to click "Allow":

```bash
git clone https://github.com/snyper9311-del/remy2
cd remy2
python scripts/gmail_oauth_setup.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
```

It opens your browser to Google's consent screen, you approve, and it
prints a refresh token.

## 3. Set environment variables for the cloud scheduler

Add these to the cloud environment this project runs in:

| Variable | Notes |
|---|---|
| `GMAIL_CLIENT_ID` | From step 1.4 |
| `GMAIL_CLIENT_SECRET` | From step 1.4 |
| `GMAIL_REFRESH_TOKEN` | Printed by the script in step 2 |
| `GMAIL_FROM_EMAIL` | The Gmail address you authorized with |
| `SMS_GATEWAY_EMAIL` | Your number + carrier gateway domain, e.g. `5551234567@tmomail.net` |

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
- Possible 7-day refresh token expiry — see the trade-off note above. If
  reminders stop and the error mentions `invalid_grant`, re-run
  `scripts/gmail_oauth_setup.py` and update `GMAIL_REFRESH_TOKEN`.

## Running the scheduler manually (for testing)

```bash
export GMAIL_CLIENT_ID=...
export GMAIL_CLIENT_SECRET=...
export GMAIL_REFRESH_TOKEN=...
export GMAIL_FROM_EMAIL=you@gmail.com
export SMS_GATEWAY_EMAIL=5551234567@tmomail.net
python backend/reminder_scheduler.py
```

Note: raw SMTP cannot be used from Remy's own cloud job due to the
network policy described above, but works fine from a normal machine —
that constraint is specific to where the scheduler runs, not to SMTP
itself.
