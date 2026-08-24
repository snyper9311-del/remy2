import os
import re
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.reminders_storage import RemindersManager, describe_schedule, DAYS_OF_WEEK

APP_VERSION = "v1.0.0"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class RemyApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Remy - WhatsApp Reminders ({APP_VERSION})")
        self.geometry("760x620")
        self.minsize(600, 460)

        self.reminders = RemindersManager()

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_reminders_view()
        self._load_reminders_ui()

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 6))

        lbl_title = ctk.CTkLabel(hdr, text="Remy", font=ctk.CTkFont(size=26, weight="bold"))
        lbl_title.pack(side="left")

        lbl_ver = ctk.CTkLabel(hdr, text=APP_VERSION, font=ctk.CTkFont(size=11, weight="bold"), text_color="#25D366")
        lbl_ver.pack(side="left", padx=(8, 0), pady=(8, 0))

        lbl_sub = ctk.CTkLabel(
            self, text="Recurring text reminders, sent by an hourly cloud job via your carrier's email-to-SMS gateway.",
            font=ctk.CTkFont(size=13), text_color="gray60"
        )
        lbl_sub.grid(row=1, column=0, sticky="w", padx=24, pady=(0, 14))

    def _build_reminders_view(self):
        view = ctk.CTkFrame(self, fg_color="transparent")
        view.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 20))
        view.grid_rowconfigure(1, weight=1)
        view.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(view, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        btn_push = ctk.CTkButton(toolbar, text="Push to Cloud", width=130, fg_color="#25D366", hover_color="#1da851", command=self._push_reminders_to_cloud)
        btn_push.pack(side="right", padx=(8, 0))

        btn_add = ctk.CTkButton(toolbar, text="+ Add Reminder", width=140, command=lambda: self._open_reminder_editor(None))
        btn_add.pack(side="right")

        btn_tz = ctk.CTkButton(toolbar, text="Timezone", width=100, fg_color="gray40", hover_color="gray30", command=self._open_timezone_editor)
        btn_tz.pack(side="left")

        self.reminders_scroll = ctk.CTkScrollableFrame(view, corner_radius=12)
        self.reminders_scroll.grid(row=1, column=0, sticky="nsew")
        self.reminders_scroll.grid_columnconfigure(0, weight=1)

    def _load_reminders_ui(self):
        for widget in self.reminders_scroll.winfo_children():
            widget.destroy()

        reminders = self.reminders.list_reminders()
        if not reminders:
            lbl_empty = ctk.CTkLabel(self.reminders_scroll, text="No reminders yet. Click \"+ Add Reminder\" to create one.", font=ctk.CTkFont(size=14), text_color="gray60")
            lbl_empty.pack(pady=40)
            return

        for reminder in reminders:
            card = ctk.CTkFrame(self.reminders_scroll, corner_radius=8)
            card.pack(fill="x", padx=10, pady=6)
            card.grid_columnconfigure(0, weight=1)

            msg_lbl = ctk.CTkLabel(card, text=reminder.get("message", ""), font=ctk.CTkFont(size=14, weight="bold"), anchor="w", justify="left")
            msg_lbl.grid(row=0, column=0, padx=14, pady=(10, 2), sticky="w")

            schedule_lbl = ctk.CTkLabel(card, text=describe_schedule(reminder.get("schedule", {})), font=ctk.CTkFont(size=12), text_color="gray60", anchor="w")
            schedule_lbl.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.grid(row=0, column=1, rowspan=2, padx=14, pady=10)

            active_switch = ctk.CTkSwitch(btn_frame, text="Active", command=lambda rid=reminder.get("id"), r=reminder: self._toggle_reminder_active(rid, r))
            if reminder.get("active", True):
                active_switch.select()
            else:
                active_switch.deselect()
            active_switch.grid(row=0, column=0, padx=(0, 10))

            btn_edit = ctk.CTkButton(btn_frame, text="Edit", width=70, command=lambda r=reminder: self._open_reminder_editor(r))
            btn_edit.grid(row=0, column=1, padx=(0, 10))

            btn_del = ctk.CTkButton(btn_frame, text="Delete", width=70, fg_color="red", hover_color="darkred", command=lambda rid=reminder.get("id"): self._delete_reminder_ui(rid))
            btn_del.grid(row=0, column=2)

    def _toggle_reminder_active(self, reminder_id, reminder):
        self.reminders.update_reminder(reminder_id, active=not reminder.get("active", True))
        self._load_reminders_ui()

    def _delete_reminder_ui(self, reminder_id):
        if messagebox.askyesno("Confirm", "Delete this reminder?"):
            self.reminders.delete_reminder(reminder_id)
            self._load_reminders_ui()

    def _open_timezone_editor(self):
        editor = ctk.CTkToplevel(self)
        editor.title("Timezone")
        editor.geometry("380x160")
        editor.transient(self)
        editor.grab_set()

        lbl = ctk.CTkLabel(editor, text="IANA timezone (e.g. America/New_York):", font=ctk.CTkFont(size=13, weight="bold"))
        lbl.pack(anchor="w", padx=20, pady=(20, 6))

        entry = ctk.CTkEntry(editor, width=300)
        entry.pack(anchor="w", padx=20)
        entry.insert(0, self.reminders.get_timezone())

        def on_save():
            tz = entry.get().strip()
            if not tz:
                messagebox.showwarning("Input Error", "Timezone cannot be empty.")
                return
            self.reminders.set_timezone(tz)
            editor.destroy()

        btn_frame = ctk.CTkFrame(editor, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20, side="bottom")
        ctk.CTkButton(btn_frame, text="Save", command=on_save).pack(side="right")
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray40", hover_color="gray30", command=editor.destroy).pack(side="right", padx=(0, 10))

    def _open_reminder_editor(self, reminder):
        editor = ctk.CTkToplevel(self)
        editor.title("Edit Reminder" if reminder else "Add Reminder")
        editor.geometry("460x520")
        editor.transient(self)
        editor.grab_set()

        schedule = (reminder or {}).get("schedule", {})

        lbl_msg = ctk.CTkLabel(editor, text="Message:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_msg.pack(anchor="w", padx=20, pady=(16, 4))
        txt_msg = ctk.CTkTextbox(editor, height=70)
        txt_msg.pack(fill="x", padx=20)
        txt_msg.insert("1.0", (reminder or {}).get("message", ""))

        lbl_type = ctk.CTkLabel(editor, text="Repeat:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_type.pack(anchor="w", padx=20, pady=(16, 4))
        option_type = ctk.CTkOptionMenu(editor, values=["Every hour (within a window)", "At a specific time"])
        option_type.pack(anchor="w", padx=20)
        option_type.set("Every hour (within a window)" if schedule.get("type", "hourly") == "hourly" else "At a specific time")

        hourly_frame = ctk.CTkFrame(editor, fg_color="transparent")
        lbl_start = ctk.CTkLabel(hourly_frame, text="Start hour (0-23):")
        lbl_start.grid(row=0, column=0, padx=(0, 8), pady=8, sticky="w")
        entry_start = ctk.CTkEntry(hourly_frame, width=60)
        entry_start.grid(row=0, column=1, padx=(0, 20))
        entry_start.insert(0, str(schedule.get("start_hour", 9)))

        lbl_end = ctk.CTkLabel(hourly_frame, text="End hour (0-23):")
        lbl_end.grid(row=0, column=2, padx=(0, 8))
        entry_end = ctk.CTkEntry(hourly_frame, width=60)
        entry_end.grid(row=0, column=3)
        entry_end.insert(0, str(schedule.get("end_hour", 21)))

        time_frame = ctk.CTkFrame(editor, fg_color="transparent")
        lbl_time = ctk.CTkLabel(time_frame, text="Time (HH:MM, 24h):")
        lbl_time.grid(row=0, column=0, padx=(0, 8), pady=8, sticky="w")
        entry_time = ctk.CTkEntry(time_frame, width=80)
        entry_time.grid(row=0, column=1)
        entry_time.insert(0, schedule.get("time", "09:00"))

        def refresh_schedule_fields(*_):
            hourly_frame.pack_forget()
            time_frame.pack_forget()
            if "specific" not in option_type.get().lower():
                hourly_frame.pack(anchor="w", padx=20, pady=(0, 4))
            else:
                time_frame.pack(anchor="w", padx=20, pady=(0, 4))

        option_type.configure(command=refresh_schedule_fields)
        refresh_schedule_fields()

        lbl_days = ctk.CTkLabel(editor, text="Days:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_days.pack(anchor="w", padx=20, pady=(12, 4))
        days_frame = ctk.CTkFrame(editor, fg_color="transparent")
        days_frame.pack(anchor="w", padx=20)

        selected_days = schedule.get("days_of_week")
        if selected_days is None:
            selected_days = [0, 1, 2, 3, 4, 5, 6]
        day_vars = []
        for i, day_name in enumerate(DAYS_OF_WEEK):
            var = ctk.BooleanVar(value=(i in selected_days))
            chk = ctk.CTkCheckBox(days_frame, text=day_name[:3], variable=var, width=70)
            chk.grid(row=i // 4, column=i % 4, padx=4, pady=4, sticky="w")
            day_vars.append(var)

        def on_save():
            message = txt_msg.get("1.0", "end").strip()
            if not message:
                messagebox.showwarning("Input Error", "Please enter a reminder message.")
                return

            days_of_week = [i for i, v in enumerate(day_vars) if v.get()]
            if not days_of_week:
                messagebox.showwarning("Input Error", "Select at least one day.")
                return

            is_hourly = "specific" not in option_type.get().lower()
            if is_hourly:
                try:
                    start_hour = int(entry_start.get().strip())
                    end_hour = int(entry_end.get().strip())
                    assert 0 <= start_hour <= 23 and 0 <= end_hour <= 23
                except (ValueError, AssertionError):
                    messagebox.showwarning("Input Error", "Start/end hour must be numbers between 0 and 23.")
                    return
                new_schedule = {"type": "hourly", "start_hour": start_hour, "end_hour": end_hour, "days_of_week": days_of_week}
            else:
                time_str = entry_time.get().strip()
                if not re.match(r'^\d{1,2}:\d{2}$', time_str):
                    messagebox.showwarning("Input Error", "Time must be in HH:MM format, e.g. 09:00.")
                    return
                new_schedule = {"type": "at_time", "time": time_str, "days_of_week": days_of_week}

            if reminder:
                self.reminders.update_reminder(reminder["id"], message=message, schedule=new_schedule)
            else:
                self.reminders.add_reminder(message=message, schedule=new_schedule)

            editor.destroy()
            self._load_reminders_ui()

        btn_frame = ctk.CTkFrame(editor, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20, side="bottom")
        btn_save = ctk.CTkButton(btn_frame, text="Save", command=on_save)
        btn_save.pack(side="right")
        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray40", hover_color="gray30", command=editor.destroy)
        btn_cancel.pack(side="right", padx=(0, 10))

    def _push_reminders_to_cloud(self):
        thread = threading.Thread(target=self._worker_push_reminders, daemon=True)
        thread.start()

    def _worker_push_reminders(self):
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=BASE_DIR, text=True
            ).strip()
            subprocess.run(["git", "add", "data/reminders.json"], cwd=BASE_DIR, check=True)

            status = subprocess.check_output(
                ["git", "status", "--porcelain", "data/reminders.json"], cwd=BASE_DIR, text=True
            ).strip()
            if not status:
                self.after(0, lambda: messagebox.showinfo("Nothing to Push", "No reminder changes to push — the cloud copy is already up to date."))
                return

            subprocess.run(["git", "commit", "-m", "Update WhatsApp reminders"], cwd=BASE_DIR, check=True)
            subprocess.run(["git", "push", "-u", "origin", branch], cwd=BASE_DIR, check=True)
            self.after(0, lambda: messagebox.showinfo("Pushed", f"Reminders pushed to origin/{branch}. The cloud job will pick them up on its next hourly run."))
        except subprocess.CalledProcessError as e:
            err = str(e)
            self.after(0, lambda: messagebox.showerror("Push Failed", f"Could not push reminders to the cloud:\n{err}"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: messagebox.showerror("Push Failed", f"Could not push reminders to the cloud:\n{err}"))


if __name__ == "__main__":
    app = RemyApp()
    app.mainloop()
