"""
Hermes Bridge Module
Enables bidirectional communication between 24/7 Render Cloud Bot
and the user's physical local laptop.
"""

import queue
import time
from typing import Dict, Optional

LAPTOP_SECRET = "hermes_secret_8616271645"

# In-memory queues & state (runs in Render web process)
_task_queue: "queue.Queue[Dict]" = queue.Queue()
_task_results: Dict[str, str] = {}
_last_heartbeat = [0.0]


def is_laptop_online() -> bool:
    """Return True if laptop sent a ping in the last 15 seconds."""
    return (time.time() - _last_heartbeat[0]) < 15.0


def record_heartbeat() -> None:
    """Update last seen timestamp for the physical laptop."""
    _last_heartbeat[0] = time.time()


def get_pending_task() -> Optional[Dict]:
    """Retrieve the next queued command for the laptop (non-blocking)."""
    try:
        return _task_queue.get_nowait()
    except queue.Empty:
        return None


def store_task_result(task_id: str, output: str) -> None:
    """Store output received from the laptop."""
    _task_results[task_id] = output


def dispatch_to_laptop(command: str, timeout: int = 40) -> str:
    """
    Queue a command for the physical laptop and wait synchronously for the result.
    """
    if not is_laptop_online():
        return "⚠️ Laptop is currently OFFLINE (laptop band hai ya laptop_node disconnect hai)."

    task_id = f"task_{int(time.time() * 1000)}"
    _task_queue.put({"task_id": task_id, "command": command})

    start_time = time.time()
    while (time.time() - start_time) < timeout:
        if task_id in _task_results:
            return _task_results.pop(task_id)
        time.sleep(0.5)

    return f"⚠️ Timeout: Laptop did not return response within {timeout} seconds."


# High-level live remote control helpers
def laptop_screenshot() -> str:
    return dispatch_to_laptop("__ACTION_SCREENSHOT__")


def laptop_webcam() -> str:
    return dispatch_to_laptop("__ACTION_WEBCAM__")


def laptop_battery() -> str:
    return dispatch_to_laptop("__ACTION_BATTERY__")


def laptop_vol_up() -> str:
    return dispatch_to_laptop("__ACTION_VOL_UP__")


def laptop_vol_down() -> str:
    return dispatch_to_laptop("__ACTION_VOL_DOWN__")


def laptop_mute() -> str:
    return dispatch_to_laptop("__ACTION_MUTE__")


def laptop_playpause() -> str:
    return dispatch_to_laptop("__ACTION_PLAYPAUSE__")


def laptop_lock() -> str:
    return dispatch_to_laptop("__ACTION_LOCK__")


def laptop_wifi() -> str:
    return dispatch_to_laptop("__ACTION_WIFI__")


def laptop_apps() -> str:
    return dispatch_to_laptop("__ACTION_APPS__")


# Antigravity & Terminal Keystroke Helpers
def laptop_key_enter() -> str:
    return dispatch_to_laptop("__ACTION_KEY_ENTER__")


def laptop_key_y() -> str:
    return dispatch_to_laptop("__ACTION_KEY_Y__")


def laptop_key_n() -> str:
    return dispatch_to_laptop("__ACTION_KEY_N__")


def laptop_key_ctrlc() -> str:
    return dispatch_to_laptop("__ACTION_KEY_CTRLC__")


def laptop_type(text: str) -> str:
    return dispatch_to_laptop(f"__ACTION_TYPE__{text}")


def laptop_ai_status() -> str:
    return dispatch_to_laptop("__ACTION_AI_STATUS__")


# Audio, Mic, Clipboard, and Power Helpers
def laptop_mic(seconds: int = 10) -> str:
    return dispatch_to_laptop(f"__ACTION_MIC__{seconds}", timeout=45)


def laptop_stop_music() -> str:
    return dispatch_to_laptop("__ACTION_STOP_MUSIC__")


def laptop_play_music(query: str) -> str:
    return dispatch_to_laptop(f"__ACTION_PLAY_MUSIC__{query}")


def laptop_clipboard(text: str = "") -> str:
    return dispatch_to_laptop(f"__ACTION_CLIPBOARD__{text}")


def laptop_speak(text: str) -> str:
    return dispatch_to_laptop(f"__ACTION_SPEAK__{text}")


def laptop_popup(title: str, msg: str) -> str:
    return dispatch_to_laptop(f"__ACTION_POPUP__{title}|||{msg}")


def laptop_power_sleep() -> str:
    return dispatch_to_laptop("__ACTION_POWER_SLEEP__")


def laptop_power_reboot() -> str:
    return dispatch_to_laptop("__ACTION_POWER_REBOOT__")


def laptop_power_poweroff() -> str:
    return dispatch_to_laptop("__ACTION_POWER_SHUTDOWN__")


# Security, CCTV, Video & Anti-Theft Helpers
def laptop_webcam_video() -> str:
    return dispatch_to_laptop("__ACTION_WEBCAM_VIDEO__", timeout=35)


def laptop_cctv_toggle() -> str:
    return dispatch_to_laptop("__ACTION_CCTV_TOGGLE__")


def laptop_alarm() -> str:
    return dispatch_to_laptop("__ACTION_ALARM__")


def laptop_stop_alarm() -> str:
    return dispatch_to_laptop("__ACTION_STOP_ALARM__")


def laptop_location() -> str:
    return dispatch_to_laptop("__ACTION_LOCATION__")
