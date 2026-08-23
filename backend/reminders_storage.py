import os
import json
import uuid
import logging

logger = logging.getLogger(__name__)

# Lives inside the repo on purpose: this file is the sync bridge between
# the local GUI and the cloud scheduler. Changes here get committed &
# pushed so the cloud side can pick them up on its next hourly run.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMINDERS_FILE = os.path.join(BASE_DIR, 'data', 'reminders.json')

# 0=Monday ... 6=Sunday, matching Python's date.weekday().
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DEFAULT_DATA = {
    "timezone": "America/New_York",
    "reminders": []
}


class RemindersManager:
    def __init__(self, data_file=None):
        self.data_file = data_file or REMINDERS_FILE
        self._ensure_file()

    def _ensure_file(self):
        data_dir = os.path.dirname(self.data_file)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_DATA, f, indent=2, ensure_ascii=False)

    def _read(self):
        self._ensure_file()
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "timezone" not in data:
                    data["timezone"] = DEFAULT_DATA["timezone"]
                if "reminders" not in data:
                    data["reminders"] = []
                return data
        except Exception as e:
            logger.error(f"Error reading reminders file: {e}")
            return json.loads(json.dumps(DEFAULT_DATA))

    def _write(self, data):
        self._ensure_file()
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_timezone(self):
        return self._read().get("timezone", DEFAULT_DATA["timezone"])

    def set_timezone(self, tz):
        data = self._read()
        data["timezone"] = tz
        self._write(data)

    def list_reminders(self):
        return self._read().get("reminders", [])

    def get_reminder(self, reminder_id):
        for r in self.list_reminders():
            if r.get("id") == reminder_id:
                return r
        return None

    def add_reminder(self, message, schedule, active=True):
        data = self._read()
        reminder = {
            "id": str(uuid.uuid4()),
            "message": message,
            "active": active,
            "schedule": schedule,
        }
        data["reminders"].append(reminder)
        self._write(data)
        return reminder

    def update_reminder(self, reminder_id, message=None, schedule=None, active=None):
        data = self._read()
        for r in data["reminders"]:
            if r.get("id") == reminder_id:
                if message is not None:
                    r["message"] = message
                if schedule is not None:
                    r["schedule"] = schedule
                if active is not None:
                    r["active"] = active
                self._write(data)
                return r
        return None

    def delete_reminder(self, reminder_id):
        data = self._read()
        data["reminders"] = [r for r in data["reminders"] if r.get("id") != reminder_id]
        self._write(data)


def describe_schedule(schedule):
    """Human-readable one-liner for a reminder's schedule, used by the GUI list."""
    days = schedule.get("days_of_week") or []
    if not days or len(days) == 7:
        days_str = "every day"
    else:
        days_str = ", ".join(DAYS_OF_WEEK[d][:3] for d in sorted(days) if 0 <= d <= 6)

    if schedule.get("type") == "hourly":
        start_h = schedule.get("start_hour", 0)
        end_h = schedule.get("end_hour", 23)
        return f"Every hour from {start_h:02d}:00 to {end_h:02d}:00, {days_str}"
    else:
        time_str = schedule.get("time", "00:00")
        return f"At {time_str}, {days_str}"
