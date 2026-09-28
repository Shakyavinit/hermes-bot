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
    """Return True if laptop sent a ping in the last 60 seconds."""
    return (time.time() - _last_heartbeat[0]) < 60.0


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


def laptop_unlock() -> str:
    return dispatch_to_laptop("__ACTION_UNLOCK__")


def laptop_lock_toggle() -> str:
    return dispatch_to_laptop("__ACTION_LOCK_TOGGLE__")


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


def laptop_key_num(num: int) -> str:
    return dispatch_to_laptop(f"__ACTION_KEY_NUM__{num}")


def laptop_type(text: str) -> str:
    return dispatch_to_laptop(f"__ACTION_TYPE__{text}")


def laptop_ai_status() -> str:
    return dispatch_to_laptop("__ACTION_AI_STATUS__")


def laptop_remote_toggle() -> str:
    return dispatch_to_laptop("__ACTION_REMOTE_TOGGLE__")


def laptop_remote_on() -> str:
    return dispatch_to_laptop("__ACTION_REMOTE_ON__")


def laptop_remote_off() -> str:
    return dispatch_to_laptop("__ACTION_REMOTE_OFF__")


def laptop_remote_status() -> str:
    return dispatch_to_laptop("__ACTION_REMOTE_STATUS__")


def laptop_auto_toggle() -> str:
    return dispatch_to_laptop("__ACTION_AUTO_APPROVE_TOGGLE__")


def laptop_auto_on() -> str:
    return dispatch_to_laptop("__ACTION_AUTO_APPROVE_ON__")


def laptop_auto_always() -> str:
    return dispatch_to_laptop("__ACTION_AUTO_APPROVE_ALWAYS__")


def laptop_auto_off() -> str:
    return dispatch_to_laptop("__ACTION_AUTO_APPROVE_OFF__")


def laptop_auto_status() -> str:
    return dispatch_to_laptop("__ACTION_AUTO_APPROVE_STATUS__")


def laptop_clean_photos() -> str:
    return dispatch_to_laptop("__ACTION_CLEAN_PHOTOS__")


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
    return dispatch_to_laptop("__ACTION_WEBCAM_VIDEO__", timeout=60)


def laptop_cctv_toggle() -> str:
    return dispatch_to_laptop("__ACTION_CCTV_TOGGLE__")


def laptop_alarm() -> str:
    return dispatch_to_laptop("__ACTION_ALARM__")


def laptop_stop_alarm() -> str:
    return dispatch_to_laptop("__ACTION_STOP_ALARM__")


def laptop_location() -> str:
    return dispatch_to_laptop("__ACTION_LOCATION__")


def laptop_ghost_mode() -> str:
    return dispatch_to_laptop("__ACTION_GHOST_MODE__")


def laptop_open_url(url: str) -> str:
    return dispatch_to_laptop(f"__ACTION_OPEN_URL__{url}")


def laptop_screen_on() -> str:
    return dispatch_to_laptop("__ACTION_SCREEN_ON__")


# Human GUI & Vision Remote Helpers
def laptop_human_open_app(app_name: str) -> str:
    return dispatch_to_laptop(f"__ACTION_HUMAN_OPEN_APP__{app_name}", timeout=45)


def laptop_human_click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> str:
    x_str = str(x) if x is not None else ""
    y_str = str(y) if y is not None else ""
    return dispatch_to_laptop(f"__ACTION_HUMAN_CLICK__{x_str}|{y_str}|{button}|{clicks}", timeout=35)


def laptop_human_move(x: int, y: int) -> str:
    return dispatch_to_laptop(f"__ACTION_HUMAN_MOVE__{x}|{y}", timeout=25)


def laptop_human_type(text: str, press_enter: bool = False) -> str:
    return dispatch_to_laptop(f"__ACTION_HUMAN_TYPE__{text}|||{press_enter}", timeout=35)


def laptop_human_scroll(direction: str = "down", amount: int = 5) -> str:
    return dispatch_to_laptop(f"__ACTION_HUMAN_SCROLL__{direction}|{amount}", timeout=25)


def laptop_screen_inspect(query: str = "") -> str:
    return dispatch_to_laptop(f"__ACTION_SCREEN_INSPECT__{query}", timeout=45)


def laptop_screen_vision_click(target: str, instruction: str = "") -> str:
    return dispatch_to_laptop(f"__ACTION_SCREEN_VISION_CLICK__{target}|||{instruction}", timeout=50)


# Offline Mobile Hub (Zero Internet)
def laptop_offline_url() -> str:
    return dispatch_to_laptop("__ACTION_OFFLINE_URL__")


def laptop_offline_qr() -> str:
    return dispatch_to_laptop("__ACTION_OFFLINE_QR__")


def laptop_hotspot_start() -> str:
    return dispatch_to_laptop("__ACTION_HOTSPOT_START__", timeout=25)


def laptop_hotspot_stop() -> str:
    return dispatch_to_laptop("__ACTION_HOTSPOT_STOP__", timeout=20)


def laptop_hotspot_status() -> str:
    return dispatch_to_laptop("__ACTION_HOTSPOT_STATUS__", timeout=15)



