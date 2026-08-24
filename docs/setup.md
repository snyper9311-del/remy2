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

## How delivery works: email-to-SMS gateways, sent via SendGrid

Every US carrier runs an email gateway that turns a plain email into a
text: an email sent to `<your-10-digit-number>@<carrier's domain>`
arrives on the phone as an SMS. That part is free and needs no SMS
account.

The email itself is sent through **SendGrid's HTTPS API**, not raw SMTP.
The cloud scheduler runs in a sandboxed environment whose network policy
only allows HTTP(S) traffic — a direct SMTP connection can't open at all
there, regardless of credentials. SendGrid's API is a plain HTTPS
request, so it works fine.

**Trade-off:** the carrier gateway part is an unofficial, carrier-run
convenience, not a supported API — it generally works reliably, but a
few carriers have discontinued or restricted their gateways over time.
If your carrier's gateway ever stops working, that's the first thing to
suspect. SendGrid itself is a standard, well-supported email API.

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

## 1. Set up SendGrid

1. Sign up free at https://signup.sendgrid.com/ (free tier: 100
   emails/day, no expiration).
2. Verify a sender address — **Settings → Sender Authentication → Single
   Sender Verification**. Verify an email address you own (e.g. your own
   Gmail); you'll get a confirmation email to click. This does *not*
   require owning a domain.
3. Create an API key — **Settings → API Keys → Create API Key**. Give it
   "Mail Send" access (Restricted Access is fine, full access not
   needed). Copy the key now; SendGrid only shows it once.

## 2. Set environment variables for the cloud scheduler

Add these to the cloud environment this project runs in:

| Variable | Example | Notes |
|---|---|---|
| `SENDGRID_API_KEY` | `SG.xxxxxxxxxxxxxxxxxxxx` | From step 1.3 above |
| `SENDGRID_FROM_EMAIL` | `you@gmail.com` | The address you verified in step 1.2 |
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
- SendGrid's free tier is 100 emails/day — far more than a personal
  reminder bot needs, but worth knowing if you ever add many reminders.

## Running the scheduler manually (for testing)

```bash
export SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxx
export SENDGRID_FROM_EMAIL=you@gmail.com
export SMS_GATEWAY_EMAIL=5551234567@tmomail.net
python backend/reminder_scheduler.py
```

Note: raw SMTP (and therefore a from-scratch alternative using it)
cannot be tested from Remy's own cloud job due to the network policy
described above, but works fine from a normal machine — this constraint
is specific to where the scheduler runs, not to SMTP itself.
