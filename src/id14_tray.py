import ctypes as c
import ctypes.wintypes as wt
import json
import os
import sys
import threading
import time
import tkinter as tk
import winreg
from pathlib import Path
from tkinter import messagebox

import pystray
from PIL import Image, ImageDraw

from id14_volume import AudientError, AudientId14
from volume_curve import MUTE_DB, db_to_percent, percent_to_db


APP_NAME = "Audient iD Volume Control"
CONFIG_ROOT = Path(os.environ.get("APPDATA", Path.home()))
CONFIG_PATH = CONFIG_ROOT / "Audient iD Volume Control" / "config.json"
PREVIOUS_CONFIG_PATH = CONFIG_ROOT / "iD14 Volume" / "config.json"
LEGACY_CONFIG_PATH = Path(os.environ.get("APPDATA", Path.home())) / "id14-volume-tray.json"
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_VALUE = "Audient iD Volume Control"
PREVIOUS_AUTOSTART_VALUE = "iD14 Volume Control"
HOTKEY_STEP = 5


class GlobalHotkeys(threading.Thread):
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    WM_HOTKEY = 0x0312

    def __init__(self, root, louder, quieter, mute):
        super().__init__(name="Audient iD global hotkeys", daemon=True)
        self.root = root
        self.callbacks = {1: louder, 2: quieter, 3: mute}

    def run(self):
        user32 = c.WinDLL("user32", use_last_error=True)
        modifiers = self.MOD_CONTROL | self.MOD_ALT
        bindings = {1: 0x26, 2: 0x28, 3: 0x4D}  # Up, Down, M
        registered = []
        try:
            for hotkey_id, virtual_key in bindings.items():
                if user32.RegisterHotKey(None, hotkey_id, modifiers, virtual_key):
                    registered.append(hotkey_id)
            message = wt.MSG()
            while user32.GetMessageW(c.byref(message), None, 0, 0) > 0:
                if message.message == self.WM_HOTKEY:
                    callback = self.callbacks.get(int(message.wParam))
                    if callback is not None:
                        self.root.after(0, callback)
        finally:
            for hotkey_id in registered:
                user32.UnregisterHotKey(None, hotkey_id)


def make_icon():
    image = Image.new("RGBA", (64, 64), (22, 24, 27, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((3, 3, 60, 60), radius=13, outline=(220, 224, 228), width=3)
    draw.ellipse((17, 17, 47, 47), outline=(245, 245, 245), width=4)
    draw.line((32, 32, 43, 21), fill=(77, 181, 255), width=5)
    draw.ellipse((28, 28, 36, 36), fill=(245, 245, 245))
    return image


class VolumeOSD:
    WIDTH = 280
    HEIGHT = 66
    TRANSPARENT = "#010203"

    def __init__(self, root):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.0)
        self.window.attributes("-transparentcolor", self.TRANSPARENT)
        self.window.configure(bg=self.TRANSPARENT)
        self.canvas = tk.Canvas(
            self.window,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=self.TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self.hide_job = None
        self.fade_job = None

    def _rounded_rect(self, x1, y1, x2, y2, radius, **options):
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        return self.canvas.create_polygon(
            points, smooth=True, splinesteps=24, **options
        )

    def show(self, percent, db):
        if self.hide_job is not None:
            self.root.after_cancel(self.hide_job)
        if self.fade_job is not None:
            self.root.after_cancel(self.fade_job)
        self.hide_job = None
        self.fade_job = None

        muted = percent <= 0 or db <= MUTE_DB + 0.01
        text = "Audient iD  ·  MUTE" if muted else f"Audient iD  ·  {percent}%  ·  {db:.1f} dB"
        accent = "#e65050" if muted else "#258bd2"
        self.canvas.delete("all")
        self._rounded_rect(
            2, 2, self.WIDTH - 2, self.HEIGHT - 2, 17,
            fill="#f8f9fa", outline="#d9dde2", width=1,
        )
        self.canvas.create_text(
            18, 25, text=text, anchor="w",
            fill=accent if muted else "#202428",
            font=("Segoe UI Semibold", 12),
        )
        bar_left, bar_right, bar_y = 18, self.WIDTH - 18, 49
        self.canvas.create_line(
            bar_left, bar_y, bar_right, bar_y,
            fill="#dfe3e7", width=6, capstyle=tk.ROUND,
        )
        fill_right = bar_left + (bar_right - bar_left) * max(0, min(100, percent)) / 100
        if fill_right > bar_left:
            self.canvas.create_line(
                bar_left, bar_y, fill_right, bar_y,
                fill=accent, width=6, capstyle=tk.ROUND,
            )

        x = (self.root.winfo_screenwidth() - self.WIDTH) // 2
        y = self.root.winfo_screenheight() - self.HEIGHT - 82
        self.window.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        self.window.attributes("-alpha", 0.96)
        self.window.deiconify()
        self.window.lift()
        self.hide_job = self.root.after(850, self._fade)

    def _fade(self, alpha=0.86):
        self.hide_job = None
        if alpha <= 0.02:
            self.window.withdraw()
            self.window.attributes("-alpha", 0.0)
            self.fade_job = None
            return
        self.window.attributes("-alpha", alpha)
        self.fade_job = self.root.after(28, lambda: self._fade(alpha - 0.10))


class TrayApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.device = None
        self.ceiling_db = None
        self.current_db = None
        self.last_nonzero_percent = 100
        self.pending_write = None
        self.lock = threading.Lock()

        self._connect()
        actual = self.device.get_db()
        config = self._load_config()
        self.ceiling_db = max(MUTE_DB, min(0.0, float(config.get("ceiling_db", actual))))
        saved_percent = int(config.get("percent", db_to_percent(actual, self.ceiling_db)))
        saved_percent = max(0, min(100, saved_percent))
        if saved_percent > 0:
            self.last_nonzero_percent = saved_percent

        self.percent = tk.IntVar(value=saved_percent)
        self.status = tk.StringVar()
        self.ceiling_status = tk.StringVar()
        self._build_window()
        self.osd = VolumeOSD(self.root)
        self._set_hardware(percent_to_db(saved_percent, self.ceiling_db), persist=True)

        self.icon = pystray.Icon(
            "id14-volume-control",
            make_icon(),
            APP_NAME,
            menu=pystray.Menu(
                pystray.MenuItem("Open volume control", self._tray_show, default=True),
                pystray.MenuItem("Mute / restore", self._tray_mute),
                pystray.MenuItem("Use current level as ceiling", self._tray_set_ceiling),
                pystray.MenuItem(
                    "Start with Windows",
                    self._tray_toggle_autostart,
                    checked=self._autostart_checked,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", self._tray_exit),
            ),
        )
        self.hotkeys = GlobalHotkeys(
            self.root,
            lambda: self.adjust_percent(HOTKEY_STEP),
            lambda: self.adjust_percent(-HOTKEY_STEP),
            self.toggle_mute,
        )

    def _connect(self):
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass
        self.device = AudientId14()
        self.device.__enter__()

    def _load_config(self):
        for path in (CONFIG_PATH, PREVIOUS_CONFIG_PATH, LEGACY_CONFIG_PATH):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
        return {}

    def _save_config(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp = CONFIG_PATH.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                {"ceiling_db": round(self.ceiling_db, 4), "percent": self.percent.get()},
                indent=2,
            ),
            encoding="utf-8",
        )
        temp.replace(CONFIG_PATH)

    def _build_window(self):
        self.root.configure(bg="#17191c")
        frame = tk.Frame(self.root, bg="#17191c", padx=18, pady=14)
        frame.pack()

        tk.Label(
            frame, text="Audient iD Main Volume",
            fg="#f3f4f5", bg="#17191c", font=("Segoe UI Semibold", 11),
        ).pack(anchor="w")
        tk.Label(
            frame, textvariable=self.status,
            fg="#4db5ff", bg="#17191c", font=("Segoe UI", 15),
        ).pack(anchor="w", pady=(3, 8))

        self.scale = tk.Scale(
            frame, from_=0, to=100, orient="horizontal", variable=self.percent,
            command=self._slider_changed, showvalue=False, length=310,
            sliderlength=18, resolution=1, bg="#17191c", fg="#f3f4f5",
            troughcolor="#34383e", activebackground="#4db5ff",
            highlightthickness=0, bd=0,
        )
        self.scale.pack()

        controls = tk.Frame(frame, bg="#17191c")
        controls.pack(fill="x", pady=(10, 0))
        tk.Button(
            controls, text="Mute / restore", command=self.toggle_mute,
            bg="#2c3035", fg="#f3f4f5", activebackground="#3a4047",
            activeforeground="#ffffff", relief="flat", padx=12, pady=5,
        ).pack(side="left")
        tk.Label(
            controls, textvariable=self.ceiling_status,
            fg="#9ba1a8", bg="#17191c", font=("Segoe UI", 9),
        ).pack(side="right")
        tk.Label(
            frame, text="Ctrl+Alt+Up/Down  volume     Ctrl+Alt+M  mute",
            fg="#737a82", bg="#17191c", font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(8, 0))
        self._update_ceiling_status()
        self._update_status(percent_to_db(self.percent.get(), self.ceiling_db))

    def _update_ceiling_status(self):
        self.ceiling_status.set(f"ceiling {self.ceiling_db:.2f} dB")

    def _update_status(self, db):
        self.current_db = db
        if db <= MUTE_DB + 0.01:
            self.status.set("MUTE  ·  -128.00 dB")
        else:
            self.status.set(f"{self.percent.get()}%  ·  {db:.2f} dB")
        if hasattr(self, "icon"):
            self.icon.title = f"{APP_NAME}: {self.status.get()}"

    def _set_hardware(self, db, persist=True):
        try:
            with self.lock:
                self.device.set_db(db)
                actual = self.device.get_db()
        except Exception:
            try:
                self._connect()
                with self.lock:
                    self.device.set_db(db)
                    actual = self.device.get_db()
            except Exception as error:
                self.status.set(f"Audient error: {error}")
                return
        self._update_status(actual)
        if persist:
            try:
                self._save_config()
            except OSError:
                pass

    def _watch_device(self):
        target = percent_to_db(self.percent.get(), self.ceiling_db)
        try:
            with self.lock:
                actual = self.device.get_db()
            if target > MUTE_DB + 0.20 and actual <= MUTE_DB + 0.20:
                self._set_hardware(target, persist=False)
        except Exception:
            try:
                self._connect()
                self._set_hardware(target, persist=False)
            except Exception:
                pass
        finally:
            self.root.after(1000, self._watch_device)

    def _slider_changed(self, _value=None):
        percent = self.percent.get()
        if percent > 0:
            self.last_nonzero_percent = percent
        target = percent_to_db(percent, self.ceiling_db)
        self._update_status(target)
        if self.pending_write is not None:
            self.root.after_cancel(self.pending_write)
        self.pending_write = self.root.after(25, lambda: self._set_hardware(target))

    def toggle_mute(self):
        if self.percent.get() == 0:
            self.percent.set(max(1, self.last_nonzero_percent))
        else:
            self.last_nonzero_percent = self.percent.get()
            self.percent.set(0)
        self._slider_changed()
        self.osd.show(
            self.percent.get(), percent_to_db(self.percent.get(), self.ceiling_db)
        )

    def adjust_percent(self, delta):
        new_value = max(0, min(100, self.percent.get() + delta))
        if new_value > 0:
            self.last_nonzero_percent = new_value
        self.percent.set(new_value)
        self._slider_changed()
        self.osd.show(new_value, percent_to_db(new_value, self.ceiling_db))

    def set_current_as_ceiling(self):
        try:
            actual = self.device.get_db()
        except Exception as error:
            messagebox.showerror(APP_NAME, str(error), parent=self.root)
            return
        self.ceiling_db = max(MUTE_DB, min(0.0, actual))
        self.percent.set(100)
        self.last_nonzero_percent = 100
        self._update_ceiling_status()
        self._set_hardware(self.ceiling_db)
        messagebox.showinfo(
            APP_NAME,
            f"New safe ceiling: {self.ceiling_db:.2f} dB",
            parent=self.root,
        )

    @staticmethod
    def _startup_command():
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        return f'"{pythonw}" "{Path(__file__).resolve()}"'

    @staticmethod
    def is_autostart_enabled():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
                for value_name in (AUTOSTART_VALUE, PREVIOUS_AUTOSTART_VALUE):
                    try:
                        winreg.QueryValueEx(key, value_name)
                        return True
                    except FileNotFoundError:
                        continue
            return False
        except OSError:
            return False

    def set_autostart(self, enabled):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
            if enabled:
                winreg.SetValueEx(
                    key, AUTOSTART_VALUE, 0, winreg.REG_SZ, self._startup_command()
                )
            for value_name in (PREVIOUS_AUTOSTART_VALUE,) if enabled else (
                AUTOSTART_VALUE,
                PREVIOUS_AUTOSTART_VALUE,
            ):
                try:
                    winreg.DeleteValue(key, value_name)
                except FileNotFoundError:
                    pass

    def _autostart_checked(self, _item):
        return self.is_autostart_enabled()

    def show_window(self):
        self.root.update_idletasks()
        width, height = 350, 200
        x = self.root.winfo_screenwidth() - width - 22
        y = self.root.winfo_screenheight() - height - 75
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()

    def hide_window(self):
        self.root.withdraw()

    def _tray_show(self, _icon=None, _item=None):
        self.root.after(0, self.show_window)

    def _tray_mute(self, _icon=None, _item=None):
        self.root.after(0, self.toggle_mute)

    def _tray_set_ceiling(self, _icon=None, _item=None):
        self.root.after(0, self.set_current_as_ceiling)

    def _tray_toggle_autostart(self, _icon=None, _item=None):
        self.set_autostart(not self.is_autostart_enabled())
        self.icon.update_menu()

    def _tray_exit(self, _icon=None, _item=None):
        self.root.after(0, self.close)

    def close(self):
        try:
            self.icon.stop()
        finally:
            if self.device is not None:
                self.device.close()
            self.root.destroy()

    def run(self):
        self.icon.run_detached()
        self.hotkeys.start()
        self.root.after(1000, self._watch_device)
        self.root.mainloop()


def main():
    kernel32 = c.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = (c.c_void_p, c.c_int, c.c_wchar_p)
    create_mutex.restype = c.c_void_p
    mutex = create_mutex(None, False, r"Local\id14-volume-control")
    if not mutex or c.get_last_error() == 183:
        return
    try:
        TrayApp().run()
    except (AudientError, OSError, RuntimeError) as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            APP_NAME,
            f"Could not open the Audient iD device:\n{error}",
        )
        root.destroy()


if __name__ == "__main__":
    main()
