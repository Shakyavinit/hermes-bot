"""
Hermes Telegram Bot Gateway - COMPLETE EDITION
Fully organized with nested menu system, all requested features integrated.
"""

import http.server
import io
import json
import logging
import os
import random
import re
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional
import urllib.parse
import requests

from agent import AgentEngine
from bridge import (
    get_pending_task, is_laptop_online, laptop_ai_status, laptop_alarm,
    laptop_apps, laptop_auto_always, laptop_auto_off, laptop_auto_on,
    laptop_auto_status, laptop_auto_toggle, laptop_battery, laptop_cctv_toggle,
    laptop_clean_photos, laptop_clipboard, laptop_ghost_mode, laptop_key_ctrlc,
    laptop_key_enter, laptop_key_n, laptop_key_num, laptop_key_y, laptop_location,
    laptop_lock, laptop_lock_toggle, laptop_unlock, laptop_mic, laptop_mute,
    laptop_open_url, laptop_play_music, laptop_playpause, laptop_popup,
    laptop_power_poweroff, laptop_power_reboot, laptop_power_sleep,
    laptop_remote_off, laptop_remote_on, laptop_remote_status, laptop_remote_toggle,
    laptop_screen_on, laptop_screenshot, laptop_speak, laptop_stop_alarm,
    laptop_stop_music, laptop_emergency_stop_all, laptop_stop_cctv,
    laptop_stop_recording, laptop_type, laptop_vol_down, laptop_vol_up, laptop_webcam,
    laptop_webcam_video, laptop_wifi, laptop_human_open_app, laptop_human_click,
    laptop_human_move, laptop_human_type, laptop_human_scroll, laptop_screen_inspect,
    laptop_screen_vision_click, laptop_offline_url, laptop_offline_qr,
    laptop_hotspot_start, laptop_hotspot_stop, laptop_hotspot_status,
    record_heartbeat, store_task_result,
)
from config import (
    BASE_DIR, TELEGRAM_BOT_TOKEN, WORKSPACE_DIR, get_runtime_config,
    is_user_allowed, set_owner,
)
from memory import clear_history, get_all_facts, save_fact
from tools import (
    execute_bash,
    execute_cloud_bash,
    execute_on_laptop,
    list_directory,
    run_system_diagnostics,
    smart_execute,
    system_status,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("HermesTelegramBot")

API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
UPLOADS_DIR = BASE_DIR / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# GLOBAL STATE TRACKERS
# ==============================================================================
_is_remote_active = True
_is_locked = False
_is_muted = False
_is_auto_approve_active = False
_is_cctv_active = False
_is_hotspot_active = False
_is_ghost_mode = False
_is_alarm_active = False
_user_menu_state: Dict[int, str] = {}  # Track which menu user is on
_user_pending_input: Dict[int, str] = {}  # Track expected input (e.g., "typing_text", "url", etc.)
_notes_storage: Dict[int, List[str]] = {}  # Local notes

# ==============================================================================
# NESTED KEYBOARD SYSTEM - Well Organized & Categorized
# ==============================================================================

def kb(rows: List[List[str]], resize: bool = True, persistent: bool = True) -> dict:
    """Helper to build persistent reply keyboard."""
    return {
        "keyboard": [[{"text": btn} for btn in row] for row in rows],
        "resize_keyboard": resize,
        "is_persistent": persistent,
    }


def get_main_menu_kb() -> dict:
    """Main persistent bottom keyboard."""
    return get_main_bottom_kb()


def get_laptop_dashboard_kb() -> dict:
    """💻 LAPTOP CONTROL PANEL (Physical Laptop Hardware Controls)"""
    return {"remove_keyboard": True}


def get_extra_tools_kb() -> dict:
    """🌟 EXTRA TOOLS PANEL (Apps, Network, Terminal, Memory)"""
    return kb([
        ["🌐 Browser & Apps", "📶 Network & Hotspot"],
        ["📋 Clipboard & Notes", "🔧 Terminal & Files"],
        ["🖥️ System Info", "⏰ Reminders & Memory"],
        ["🔙 Laptop Menu", "🏠 Main Menu"],
    ])


def get_cloud_dashboard_kb() -> dict:
    """☁️ CLOUD SERVER PANEL (24/7 Render Cloud Container)"""
    return kb([
        ["📊 Cloud Status", "📁 Cloud Files"],
        ["⚡ Cloud Quick Test", "🧹 Reset AI Memory"],
        ["🩺 Self-Diagnostics", "🌐 24/7 Hosting Info"],
        ["🏠 Main Menu"],
    ])


def get_camera_media_kb() -> dict:
    """📸 CAMERA & MEDIA MENU"""
    return kb([
        ["📸 Screenshot", "📷 Front Camera Photo"],
        ["🎥 5s Webcam Video", "🎥 10s Webcam Video"],
        ["🖼️ AI Photo Analysis", "🧹 Clean Photos"],
        ["🔙 Laptop Menu", "🏠 Main Menu"],
    ])


def get_audio_voice_kb() -> dict:
    """🎙️ AUDIO & VOICE MENU"""
    return kb([
        ["🎙️ Record Mic 10s", "🎙️ Record Mic 30s"],
        ["🗣️ Text-to-Speech", "📝 Voice Transcribe"],
        ["🔙 Laptop Menu", "🏠 Main Menu"],
    ])


def get_system_info_kb() -> dict:
    """🖥️ SYSTEM INFO MENU"""
    return kb([
        ["🔋 Battery Status", "💻 CPU & RAM Usage"],
        ["💾 Disk Space", "🌡️ CPU Temperature"],
        ["🌍 Public IP", "📍 Laptop Location"],
        ["🔙 Extra Tools", "🏠 Main Menu"],
    ])


def get_power_screen_kb() -> dict:
    """⚡ POWER & SCREEN MENU"""
    global _is_locked, _is_ghost_mode
    lock_btn = "🔓 Unlock Screen" if _is_locked else "🔒 Lock Screen"
    ghost_btn = "☀️ Display ON" if _is_ghost_mode else "🕶️ Ghost Mode (Screen OFF)"
    return kb([
        [lock_btn, ghost_btn],
        ["💤 Sleep Laptop", "🔄 Reboot Laptop"],
        ["⛔ Shutdown Laptop"],
        ["🔙 Laptop Menu", "🏠 Main Menu"],
    ])


def get_volume_media_kb() -> dict:
    """🔊 VOLUME & MEDIA MENU"""
    global _is_muted
    mute_btn = "🔊 Unmute" if _is_muted else "🔇 Mute"
    return kb([
        ["🔉 Vol -", "🔊 Vol +", mute_btn],
        ["⏯️ Play/Pause", "⏹️ Stop Music"],
        ["⏭️ Next Track", "⏮️ Prev Track"],
        ["🎵 Play Song", "🎚️ Set Volume %"],
        ["🔙 Laptop Menu", "🏠 Main Menu"],
    ])


# Aliases for backward compatibility
get_volume_sound_kb = get_volume_media_kb
get_media_control_kb = get_volume_media_kb


def get_mouse_keyboard_kb() -> dict:
    """🖱️ MOUSE & KEYBOARD MENU (Compact 5 Rows)"""
    return kb([
        ["🖱️ Left Click", "🖱️ Right Click", "🎯 Click Element"],
        ["⬆️ Scroll Up", "⬇️ Scroll Down", "👁️ AI Vision Click"],
        ["⌨️ Type Text", "⌨️ Human Type"],
        ["↩️ Press Enter", "🛑 Press Ctrl+C", "⎋ Press Esc"],
        ["🏠 Main Menu"],
    ])


def get_browser_apps_kb() -> dict:
    """🌐 BROWSER & APPS MENU"""
    return kb([
        ["🌐 Open Chrome", "💻 Open VS Code"],
        ["⌨️ Open Terminal", "🎵 Open Spotify"],
        ["🌐 Open URL", "📱 Running Apps"],
        ["🔙 Extra Tools", "🏠 Main Menu"],
    ])


def get_security_spy_kb() -> dict:
    """🚨 SECURITY & SPY MENU"""
    global _is_cctv_active
    cctv_btn = "🛑 Stop CCTV" if _is_cctv_active else "👁️ Start CCTV Motion"
    return kb([
        ["🚨 Siren Alarm", "⏹️ Stop Alarm"],
        [cctv_btn, "📍 Find Laptop"],
        ["📷 Silent Snap", "🎥 Silent Video"],
        ["🔙 Laptop Menu", "🏠 Main Menu"],
    ])


def get_ai_automation_kb() -> dict:
    """🤖 AI & AUTOMATION MENU (Sandbox Approvals & Status)"""
    global _is_auto_approve_active, _is_remote_active
    auto_btn = "⚡ Auto: ON 🟢" if _is_auto_approve_active else "⚡ Auto: OFF 🔴"
    self_btn = "🟢 Remote Mode" if not _is_remote_active else "🔴 Self-Use Mode"
    return kb([
        [self_btn, auto_btn],
        ["✅ Approve (Enter)", "🛑 Cancel Ctrl+C"],
        ["🟢 Send 'y'", "🔴 Send 'n'"],
        ["1️⃣", "2️⃣", "3️⃣", "📊 AI Status"],
        ["🔙 Laptop Menu", "🏠 Main Menu"],
    ])


def get_clipboard_notes_kb() -> dict:
    """📋 CLIPBOARD & NOTES MENU"""
    return kb([
        ["📋 Read Clipboard", "✏️ Write Clipboard"],
        ["📝 Save Note", "📖 Recall Notes"],
        ["🔙 Extra Tools", "🏠 Main Menu"],
    ])


def get_network_offline_kb() -> dict:
    """📶 NETWORK & OFFLINE MENU"""
    global _is_hotspot_active
    hotspot_btn = "🛑 Stop Hotspot" if _is_hotspot_active else "📡 Start Hotspot"
    return kb([
        ["📶 WiFi Status", "🌍 Check Internet"],
        [hotspot_btn, "📊 Hotspot Status"],
        ["🌐 Offline Hub URL", "📱 Offline Hub QR"],
        ["🔙 Extra Tools", "🏠 Main Menu"],
    ])


def get_terminal_files_kb() -> dict:
    """🔧 TERMINAL & FILES MENU"""
    return kb([
        ["💻 Run Bash Command", "📁 List Files"],
        ["⬇️ Download File", "⬆️ Upload File Info"],
        ["🔙 Extra Tools", "🏠 Main Menu"],
    ])


def get_reminders_memory_kb() -> dict:
    """⏰ REMINDERS & MEMORY MENU"""
    return kb([
        ["⏰ Set Reminder", "🧠 Save to Memory"],
        ["📖 Show Memory", "🧹 Reset History"],
        ["🔙 Extra Tools", "🏠 Main Menu"],
    ])


def get_quick_toggles_kb() -> dict:
    """🎛️ QUICK TOGGLES MENU"""
    global _is_remote_active, _is_auto_approve_active, _is_locked, _is_muted, _is_cctv_active, _is_ghost_mode
    self_btn = "🟢 Enable Remote" if not _is_remote_active else "🔴 Self-Use Pause"
    auto_btn = "⚡ Auto: ON 🟢" if _is_auto_approve_active else "⚡ Auto: OFF 🔴"
    lock_btn = "🔓 Unlock" if _is_locked else "🔒 Lock"
    mute_btn = "🔊 Unmute" if _is_muted else "🔇 Mute"
    cctv_btn = "🛑 CCTV OFF" if _is_cctv_active else "👁️ CCTV ON"
    ghost_btn = "☀️ Screen ON" if _is_ghost_mode else "🕶️ Ghost Mode"
    return kb([
        [self_btn, auto_btn],
        [lock_btn, mute_btn],
        [cctv_btn, ghost_btn],
        ["🏠 Main Menu"],
    ])


def get_help_status_kb() -> dict:
    """❓ HELP & STATUS MENU"""
    return kb([
        ["📊 Full Status", "🩺 Self-Diagnostics"],
        ["💻 Laptop Status", "☁️ Cloud Status"],
        ["💡 Help Guide", "🌐 24/7 Hosting Info"],
        ["🏠 Main Menu"],
    ])


# ==============================================================================
# MENU ROUTER - Maps menu names to keyboards
# ==============================================================================
MENU_MAP = {
    "main": get_main_menu_kb,
    "laptop": get_laptop_dashboard_kb,
    "cloud": get_cloud_dashboard_kb,
    "extra": get_extra_tools_kb,
    "camera": get_camera_media_kb,
    "audio": get_audio_voice_kb,
    "system": get_system_info_kb,
    "power": get_power_screen_kb,
    "volume": get_volume_media_kb,
    "media": get_volume_media_kb,
    "mouse": get_mouse_keyboard_kb,
    "browser": get_browser_apps_kb,
    "security": get_security_spy_kb,
    "ai": get_ai_automation_kb,
    "clipboard": get_clipboard_notes_kb,
    "network": get_network_offline_kb,
    "terminal": get_terminal_files_kb,
    "reminders": get_reminders_memory_kb,
    "toggles": get_quick_toggles_kb,
    "help": get_help_status_kb,
}


def get_home_kb() -> dict:
    """Root selector: Laptop Mode vs Cloud Mode."""
    return {
        "inline_keyboard": [
            [
                {"text": "💻 Laptop Mode", "callback_data": "mode_laptop"},
                {"text": "☁️ Cloud Mode", "callback_data": "mode_cloud"},
            ],
            [
                {"text": "📊 System Status", "callback_data": "btn_status"},
                {"text": "❓ Help & Guide", "callback_data": "btn_help"},
            ],
        ]
    }


def get_home_text() -> str:
    """Root selector header text."""
    _laptop = "ONLINE 🟢" if is_laptop_online() else "OFFLINE 🔴"
    _remote = "ACTIVE 🟢" if _is_remote_active else "PAUSED (Self-Use) 🔴"
    _auto = "ON 🟢" if _is_auto_approve_active else "OFF 🔴"
    return (
        "🤖 *Hermes Central Hub*\n\n"
        f"> 💻 *Laptop:* `{_laptop}`\n"
        f"> 🎮 *Remote Access:* `{_remote}`\n"
        f"> ⚡ *Auto Approve:* `{_auto}`\n\n"
        "_Niche diye gaye 6 buttons se select karein:_"
    )


def get_cloud_kb() -> dict:
    """Cloud Mode inline controls."""
    return {
        "inline_keyboard": [
            [
                {"text": "📊 Cloud Telemetry", "callback_data": "btn_cloud_status"},
                {"text": "📁 Cloud Files", "callback_data": "btn_cloud_files"},
            ],
            [
                {"text": "⚡ Cloud Quick Test", "callback_data": "btn_cloud_test"},
                {"text": "🩺 Self-Diagnostics", "callback_data": "btn_diagnose"},
            ],
            [
                {"text": "🧹 Reset AI Memory", "callback_data": "btn_reset_memory"},
                {"text": "🌐 24/7 Hosting Info", "callback_data": "btn_hosting_info"},
            ],
            [
                {"text": "🏠 Back to Main Hub", "callback_data": "mode_home"},
            ],
        ]
    }


def get_cloud_page_text() -> str:
    """Cloud Mode header text."""
    return (
        "☁️ *Hermes Cloud Mode (Render 24/7)*\n\n"
        "> 🌐 *Status:* `ONLINE 24/7 🟢`\n"
        "> 🚀 *Hosting:* `Render Cloud Server`\n"
        "> 🩺 *Health Port:* `7860 (Active)`\n"
        "> 🧠 *AI Core:* `Gemini / Dual-Engine`\n\n"
        "_Select a Cloud action below:_"
    )


def get_page_kb(page: int = 1) -> dict:
    """Multi-page inline keyboard for Laptop Mode with explicit ON/OFF toggle states."""
    global _is_auto_approve_active, _is_remote_active, _is_locked, _is_muted
    global _is_cctv_active, _is_ghost_mode, _is_alarm_active, _is_hotspot_active

    auto_text = f"⚡ Auto: {'ON 🟢' if _is_auto_approve_active else 'OFF 🔴'}"
    remote_text = f"🎮 Remote: {'ON 🟢' if _is_remote_active else 'OFF 🔴'}"
    mute_text = f"🔇 Mute: {'ON 🟢' if _is_muted else 'OFF 🔴'}"
    lock_text = f"🔒 Lock: {'ON 🟢' if _is_locked else 'OFF 🔴'}"
    ghost_text = f"🕶️ Ghost: {'ON 🟢' if _is_ghost_mode else 'OFF 🔴'}"
    cctv_text = f"👁️ CCTV: {'ON 🟢' if _is_cctv_active else 'OFF 🔴'}"
    alarm_text = f"🚨 Alarm: {'ON 🚨' if _is_alarm_active else 'OFF 🔴'}"
    hotspot_text = f"📡 Hotspot: {'ON 🟢' if _is_hotspot_active else 'OFF 🔴'}"

    if page == 1:
        # Page 1: Core Recon & Modes
        rows = [
            [
                {"text": "📸 Screenshot", "callback_data": "btn_screenshot"},
                {"text": "📷 Webcam Photo", "callback_data": "btn_webcam"},
            ],
            [
                {"text": "🔋 Battery Level", "callback_data": "btn_battery"},
                {"text": "📊 System Status", "callback_data": "btn_status"},
            ],
            [
                {"text": auto_text, "callback_data": "btn_auto_toggle"},
                {"text": remote_text, "callback_data": "btn_remote_toggle"},
            ],
            [
                {"text": "📄 1/4", "callback_data": "page_1"},
                {"text": "Next ➡️", "callback_data": "page_2"},
                {"text": "🏠 Hub", "callback_data": "mode_home"},
            ]
        ]
    elif page == 2:
        # Page 2: Audio, Volume & Media
        rows = [
            [
                {"text": "🔊 Volume +10%", "callback_data": "btn_vol_up"},
                {"text": "🔉 Volume -10%", "callback_data": "btn_vol_down"},
            ],
            [
                {"text": mute_text, "callback_data": "btn_mute_toggle"},
                {"text": "🎙️ Record Mic 10s", "callback_data": "btn_mic10"},
            ],
            [
                {"text": "🎥 5s Video Clip", "callback_data": "btn_video5"},
                {"text": "🎵 Play/Pause", "callback_data": "btn_playpause"},
            ],
            [
                {"text": "⬅️ Prev", "callback_data": "page_1"},
                {"text": "📄 2/4", "callback_data": "page_2"},
                {"text": "Next ➡️", "callback_data": "page_3"},
                {"text": "🏠 Hub", "callback_data": "mode_home"},
            ]
        ]
    elif page == 3:
        # Page 3: Security, Power & Screen Controls (All with ON / OFF)
        rows = [
            [
                {"text": lock_text, "callback_data": "btn_lock_toggle"},
                {"text": "⚡ Sleep Laptop", "callback_data": "btn_sleep"},
            ],
            [
                {"text": ghost_text, "callback_data": "btn_ghost_mode"},
                {"text": cctv_text, "callback_data": "btn_cctv_toggle"},
            ],
            [
                {"text": alarm_text, "callback_data": "btn_alarm_toggle"},
                {"text": hotspot_text, "callback_data": "btn_hotspot_toggle"},
            ],
            [
                {"text": "⬅️ Prev", "callback_data": "page_2"},
                {"text": "📄 3/4", "callback_data": "page_3"},
                {"text": "Next ➡️", "callback_data": "page_4"},
                {"text": "🏠 Hub", "callback_data": "mode_home"},
            ]
        ]
    else:
        # Page 4: Network, Files & Tools
        rows = [
            [
                {"text": "📶 WiFi Status", "callback_data": "btn_wifi"},
                {"text": "📍 Location", "callback_data": "btn_location"},
            ],
            [
                {"text": "📁 List Files", "callback_data": "btn_files"},
                {"text": "📋 Clipboard", "callback_data": "btn_clip_read"},
            ],
            [
                {"text": "🩺 Diagnostics", "callback_data": "btn_diagnose"},
                {"text": "🧹 Reset Memory", "callback_data": "btn_reset_memory"},
            ],
            [
                {"text": "⬅️ Prev", "callback_data": "page_3"},
                {"text": "📄 4/4", "callback_data": "page_4"},
                {"text": "🔄 Top", "callback_data": "page_1"},
                {"text": "🏠 Hub", "callback_data": "mode_home"},
            ]
        ]

    return {"inline_keyboard": rows}


def get_page_text(page: int = 1) -> str:
    """Header text with live summary of all switch states."""
    _laptop = "ONLINE 🟢" if is_laptop_online() else "OFFLINE 🔴"
    _remote = "ON 🟢" if _is_remote_active else "OFF 🔴"
    _auto = "ON 🟢" if _is_auto_approve_active else "OFF 🔴"

    if page == 1:
        return (
            "💻 *Laptop Mode — Control Panel* — `Page 1/4`\n\n"
            f"> 💻 *Laptop:* `{_laptop}`\n"
            f"> 🎮 *Remote Access:* `{_remote}` (30m)\n"
            f"> ⚡ *Auto-Approve:* `{_auto}`\n\n"
            "_Tap any button below to toggle or execute:_"
        )
    elif page == 2:
        return (
            "🔊 *Laptop Mode — Audio & Media* — `Page 2/4`\n\n"
            f"> 🔇 *Mute Audio:* `{'ON 🟢' if _is_muted else 'OFF 🔴'}`\n"
            "> • Volume control (+/- 10%)\n"
            "> • Microphone recording (10s)\n"
            "> • Webcam video clip & Music toggle\n\n"
            "_Tap a control or use navigation buttons below:_"
        )
    elif page == 3:
        return (
            "⚡ *Laptop Mode — Power & Security* — `Page 3/4`\n\n"
            f"> 🔒 *Screen Lock:* `{'ON 🟢' if _is_locked else 'OFF 🔴'}`\n"
            f"> 🕶️ *Ghost Mode:* `{'ON 🟢' if _is_ghost_mode else 'OFF 🔴'}`\n"
            f"> 👁️ *CCTV Mode:* `{'ON 🟢' if _is_cctv_active else 'OFF 🔴'}`\n"
            f"> 🚨 *Siren Alarm:* `{'ON 🚨' if _is_alarm_active else 'OFF 🔴'}`\n"
            f"> 📡 *Hotspot:* `{'ON 🟢' if _is_hotspot_active else 'OFF 🔴'}`\n\n"
            "_Tap any toggle button to switch ON/OFF:_"
        )
    else:
        return (
            "🌐 *Laptop Mode — Network & Tools* — `Page 4/4`\n\n"
            "> • WiFi connection & Geolocation\n"
            "> • Workspace files & Clipboard reader\n"
            "> • Diagnostics & AI Memory reset\n\n"
            "_Tap a control or use navigation buttons below:_"
        )


def get_main_bottom_kb() -> dict:
    """Main persistent bottom keyboard - exactly 6 buttons (3 rows x 2 cols)."""
    global _is_remote_active
    remote_btn = "🔴 Self-Use Mode" if _is_remote_active else "🟢 Remote Mode"
    return {
        "keyboard": [
            [{"text": "💻 Laptop Mode"}, {"text": "🎵 Music Player"}],
            [{"text": remote_btn}, {"text": "⚡ Auto Approve"}],
            [{"text": "☁️ Cloud Mode"}, {"text": "📊 Status"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": "🎮 Select an option below...",
    }


def get_music_bottom_kb() -> dict:
    """Dedicated Music Player persistent bottom keyboard - exactly 6 buttons."""
    return {
        "keyboard": [
            [{"text": "⏯️ Play / Pause"}, {"text": "⏹️ Stop Music"}],
            [{"text": "🔊 Vol Up (+10%)"}, {"text": "🔉 Vol Down (-10%)"}],
            [{"text": "🔍 Search & Play"}, {"text": "🔙 Main Menu"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": "🎵 Music Player Controls...",
    }


def get_laptop_bottom_kb() -> dict:
    """Laptop controls persistent bottom keyboard - exactly 6 buttons."""
    return {
        "keyboard": [
            [{"text": "📸 Screenshot"}, {"text": "📷 Webcam"}],
            [{"text": "🎙️ Record Mic"}, {"text": "🔒 Lock Screen"}],
            [{"text": "🌟 Extra Tools"}, {"text": "🔙 Main Menu"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": "💻 Laptop Controls...",
    }


def get_extra_bottom_kb() -> dict:
    """Extra tools persistent bottom keyboard - exactly 6 buttons."""
    global _is_alarm_active, _is_cctv_active, _is_ghost_mode
    alarm_btn = "⏹️ Stop Alarm" if _is_alarm_active else "🚨 Alarm Siren"
    cctv_btn = "🛑 Stop CCTV" if _is_cctv_active else "👁️ CCTV Mode"
    ghost_btn = "☀️ Screen ON" if _is_ghost_mode else "🕶️ Ghost Mode"
    return {
        "keyboard": [
            [{"text": "🖱️ Mouse Controls"}, {"text": alarm_btn}],
            [{"text": "📍 Find Location"}, {"text": cctv_btn}],
            [{"text": ghost_btn}, {"text": "🔙 Main Menu"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": "🌟 Extra Tools...",
    }


def get_mouse_bottom_kb() -> dict:
    """Mouse & Keyboard persistent bottom keyboard - exactly 6 buttons."""
    return {
        "keyboard": [
            [{"text": "🖱️ Left Click"}, {"text": "🖱️ Right Click"}],
            [{"text": "⬆️ Scroll Up"}, {"text": "⬇️ Scroll Down"}],
            [{"text": "↩️ Press Enter"}, {"text": "🔙 Main Menu"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": "🖱️ Mouse & Keyboard...",
    }


def get_cloud_bottom_kb() -> dict:
    """Cloud server persistent bottom keyboard - exactly 6 buttons."""
    return {
        "keyboard": [
            [{"text": "📊 Cloud Telemetry"}, {"text": "📁 Cloud Files"}],
            [{"text": "⚡ Cloud Quick Test"}, {"text": "🩺 Self-Diagnostics"}],
            [{"text": "🧹 Reset AI Memory"}, {"text": "🔙 Main Menu"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "input_field_placeholder": "☁️ Cloud Mode...",
    }


def get_bottom_reply_kb(chat_id: Optional[int] = None) -> dict:
    """Return active persistent bottom keyboard based on user's active section."""
    state = _user_menu_state.get(chat_id, "main") if chat_id else "main"
    if state == "music":
        return get_music_bottom_kb()
    elif state == "laptop":
        return get_laptop_bottom_kb()
    elif state == "extra":
        return get_extra_bottom_kb()
    elif state == "mouse":
        return get_mouse_bottom_kb()
    elif state == "cloud":
        return get_cloud_bottom_kb()
    return get_main_bottom_kb()


def get_kb_for(menu: str = None, chat_id: Optional[int] = None) -> dict:
    """Always return clean bottom reply keyboard with 6 buttons."""
    if menu in ("music", "volume", "media"):
        return get_music_bottom_kb()
    elif menu in ("laptop", "camera", "power", "security", "system", "browser"):
        return get_laptop_bottom_kb()
    elif menu == "extra":
        return get_extra_bottom_kb()
    elif menu == "mouse":
        return get_mouse_bottom_kb()
    elif menu == "cloud":
        return get_cloud_bottom_kb()
    return get_bottom_reply_kb(chat_id)


# ==============================================================================
# TELEGRAM API HELPERS
# ==============================================================================
_recent_bot_msgs: Dict[int, List[int]] = {}


def track_bot_msg(chat_id: int, msg_id: Optional[int]) -> None:
    if not msg_id:
        return
    _recent_bot_msgs.setdefault(chat_id, []).append(msg_id)
    if len(_recent_bot_msgs[chat_id]) > 50:
        _recent_bot_msgs[chat_id] = _recent_bot_msgs[chat_id][-50:]


# ==============================================================================
# EXCLUSIVE USER STICKER PACK (II_SH3R_II_uunv_by_fStikBot)
# ==============================================================================
SHER_STICKERS_FILE = WORKSPACE_DIR / "sher_stickers.json"
SHER_STICKER_PACK_NAME = "II_SH3R_II_uunv_by_fStikBot"
_sher_stickers_cache: List[str] = []


def get_sher_stickers() -> List[str]:
    """Retrieve all sticker file_ids from the exclusive II_SH3R_II_uunv_by_fStikBot pack."""
    global _sher_stickers_cache
    if _sher_stickers_cache:
        return _sher_stickers_cache

    if SHER_STICKERS_FILE.exists():
        try:
            with open(SHER_STICKERS_FILE, "r") as f:
                _sher_stickers_cache = json.load(f)
                if _sher_stickers_cache:
                    return _sher_stickers_cache
        except Exception:
            pass

    try:
        resp = requests.get(f"{API_BASE}/getStickerSet", params={"name": SHER_STICKER_PACK_NAME}, timeout=10)
        res = resp.json()
        if res.get("ok"):
            _sher_stickers_cache = [s["file_id"] for s in res["result"].get("stickers", []) if "file_id" in s]
            with open(SHER_STICKERS_FILE, "w") as f:
                json.dump(_sher_stickers_cache, f, indent=2)
    except Exception as e:
        logger.error(f"Error loading Sher stickers: {e}")

    return _sher_stickers_cache


def maybe_send_sher_sticker(chat_id: int, force: bool = False, chance: float = 0.20) -> Optional[int]:
    """Occasionally send a random sticker from the exclusive Sher pack (kabhi kabhi random)."""
    if not force and random.random() > chance:
        return None

    stickers = get_sher_stickers()
    if not stickers:
        return None

    sticker_id = random.choice(stickers)
    try:
        resp = requests.post(
            f"{API_BASE}/sendSticker",
            json={"chat_id": chat_id, "sticker": sticker_id},
            timeout=8,
        )
        res = resp.json()
        if res.get("ok"):
            msg_id = res.get("result", {}).get("message_id")
            track_bot_msg(chat_id, msg_id)
            return msg_id
    except Exception as e:
        logger.error(f"Error sending Sher sticker: {e}")
    return None


# Verified Telegram Premium Custom Emojis (Neon & Animated Official Packs)
PREMIUM_CUSTOM_EMOJIS: Dict[str, str] = {
    "⚡": "5373066076558996568",  # Neon glowing lightning
    "🔋": "5449587434402623682",  # Neon glowing battery
    "💻": "5431376038628171216",  # Animated Cyber laptop
    "☁️": "5287571024500498635",  # Animated Cloud
    "🚀": "5445284980978621387",  # Animated Rocket
    "🔥": "5420315771991497307",  # Animated Flame
    "🤖": "5372981976804366741",  # Animated Robot
    "💯": "5188208446461188962",  # Animated 100
    "👑": "5467406098367521267",  # Animated Crown
    "✨": "5472164874886846699",  # Animated Sparkles
    "👀": "5424885441100782420",  # Animated Eyes
    "👍": "5469770542288478598",  # Animated Thumbs up
    "💡": "5472146462362048818",  # Animated Idea lightbulb
    "🎵": "5188621441926438751",  # Animated Music note
    "✅": "5427009714745517609",  # Animated Checkmark
    "❌": "5465665476971471368",  # Animated Cross
    "⏰": "5413704112220949842",  # Animated Clock
}


def to_premium_emoji(char: str) -> str:
    """Wrap emoji in Telegram paid custom_emoji tag if available."""
    cid = PREMIUM_CUSTOM_EMOJIS.get(char)
    if cid:
        return f'<tg-emoji emoji-id="{cid}">{char}</tg-emoji>'
    return char


def import_full_pack(set_name: str) -> Optional[dict]:
    """Fetch all stickers or custom emojis from an entire pack and save them."""
    if not set_name:
        return None
    try:
        resp = requests.get(f"{API_BASE}/getStickerSet", params={"name": set_name}, timeout=15)
        res = resp.json()
        if res.get("ok"):
            result = res["result"]
            stickers = result.get("stickers", [])
            title = result.get("title", set_name)
            stype = result.get("sticker_type", "regular")

            pack_file = WORKSPACE_DIR / "imported_pack.json"
            pack_data = {
                "set_name": set_name,
                "title": title,
                "type": stype,
                "count": len(stickers),
                "items": [],
            }

            for s in stickers:
                item = {
                    "file_id": s.get("file_id"),
                    "emoji": s.get("emoji", ""),
                    "custom_emoji_id": s.get("custom_emoji_id"),
                }
                pack_data["items"].append(item)
                if s.get("custom_emoji_id") and s.get("emoji"):
                    PREMIUM_CUSTOM_EMOJIS[s["emoji"]] = s["custom_emoji_id"]
                if s.get("emoji") and s.get("file_id"):
                    BOT_STICKERS[s["emoji"]] = s.get("file_id")

            with open(pack_file, "w") as f:
                json.dump(pack_data, f, indent=2)

            logger.info(f"Imported pack: {title} ({len(stickers)} items)")
            return pack_data
    except Exception as e:
        logger.error(f"Error importing pack: {e}")
    return None


def tg_set_reaction(chat_id: int, message_id: Optional[int], emoji: str = "⚡") -> bool:
    """Set an instant emoji reaction on a message for sleek responsive feedback."""
    if not chat_id or not message_id:
        return False
    try:
        resp = requests.post(
            f"{API_BASE}/setMessageReaction",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction": [{"type": "emoji", "emoji": emoji}],
            },
            timeout=5,
        )
        return resp.json().get("ok", False)
    except Exception:
        return False


def tg_react_smart(chat_id: int, message_id: Optional[int], text: str = "") -> bool:
    """Dynamically pick the most relevant Telegram emoji reaction based on message context."""
    if not chat_id or not message_id:
        return False
    t = text.lower()

    if any(k in t for k in ("lock", "unlock", "alarm", "ghost", "security", "spy", "protect", "siren")):
        emoji = "🫡"
    elif any(k in t for k in ("screenshot", "webcam", "camera", "photo", "pic", "snap", "cctv", "dekho")):
        emoji = "👀"
    elif any(k in t for k in ("run", "bash", "exec", "terminal", "code", "cmd", "fast", "speed", "test")):
        emoji = "🚀"
    elif any(k in t for k in ("song", "music", "play", "sound", "volume", "mic", "speak", "audio")):
        emoji = "🔥"
    elif any(k in t for k in ("battery", "charging", "wifi", "ip", "location", "disk", "cpu", "temp")):
        emoji = "⚡"
    elif any(k in t for k in ("screen", "desktop", "display")):
        emoji = "👀"
    elif any(k in t for k in ("ok", "done", "theek", "shukriya", "thanks", "good", "sahi", "badhiya")):
        emoji = "💯"
    elif any(k in t for k in ("status", "help", "guide", "info", "diagnose")):
        emoji = "👨‍💻"
    elif any(k in t for k in ("kya", "kaise", "kyun", "who", "what", "how", "why", "?")):
        emoji = "🤔"
    else:
        emoji = "⚡"

    return tg_set_reaction(chat_id, message_id, emoji)


def tg_send_sticker(chat_id: int, sticker_type_or_id: str = "ready") -> Optional[int]:
    """Send a sticker by predefined key or raw Telegram file_id."""
    sticker_id = get_sticker_for(sticker_type_or_id) if sticker_type_or_id in BOT_STICKERS else sticker_type_or_id
    try:
        resp = requests.post(
            f"{API_BASE}/sendSticker",
            json={"chat_id": chat_id, "sticker": sticker_id},
            timeout=10,
        )
        res = resp.json()
        if res.get("ok"):
            msg_id = res.get("result", {}).get("message_id")
            track_bot_msg(chat_id, msg_id)
            return msg_id
    except Exception as e:
        logger.error(f"Error sending sticker: {e}")
    return None


def format_stylish_response(title: str, content: str = "") -> str:
    """Format bot responses with sleek native Telegram blockquotes and badges."""
    parts = []
    if title and title.strip():
        parts.append(title.strip())
    if content and content.strip():
        clean = content.strip()
        # If content contains code blocks or is already blockquoted, preserve as is
        if "```" in clean or clean.startswith(">"):
            parts.append(clean)
        else:
            lines = clean.splitlines()
            quoted = [f"> {line}" if line.strip() else ">" for line in lines]
            parts.append("\n".join(quoted))
    return "\n\n".join(parts) if parts else ""


def tg_delete_message(chat_id: int, message_id: Optional[int]) -> bool:
    if not chat_id or not message_id:
        return False
    try:
        resp = requests.post(
            f"{API_BASE}/deleteMessage",
            json={"chat_id": chat_id, "message_id": message_id},
            timeout=8,
        )
        return resp.status_code == 200
    except Exception:
        return False


def tg_send_message(
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = "Markdown",
    reply_markup: Optional[dict] = None,
) -> Optional[int]:
    if len(text) > 4000:
        if len(text) > 8000:
            tg_send_document(chat_id, text.encode("utf-8"), "output.txt", "📄 Long output attached")
            text = text[:800] + "\n\n...(Full output in document above)..."
        else:
            text = text[:4000]

    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=20)
        res_json = resp.json()
        if res_json.get("ok"):
            msg_id = res_json.get("result", {}).get("message_id")
            track_bot_msg(chat_id, msg_id)
            return msg_id
        else:
            payload.pop("parse_mode", None)
            resp2 = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=20)
            if resp2.json().get("ok"):
                msg_id = resp2.json().get("result", {}).get("message_id")
                track_bot_msg(chat_id, msg_id)
                return msg_id
    except Exception as e:
        logger.error(f"Error sending: {e}")
    return None


def tg_edit_message(chat_id: int, message_id: int, new_text: str) -> bool:
    try:
        resp = requests.post(
            f"{API_BASE}/editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": new_text},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def tg_edit_reply_markup(chat_id: int, message_id: int, reply_markup: dict) -> bool:
    try:
        resp = requests.post(
            f"{API_BASE}/editMessageReplyMarkup",
            json={"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def tg_answer_callback(cq_id: str, text: str = "", show_alert: bool = False) -> None:
    try:
        requests.post(
            f"{API_BASE}/answerCallbackQuery",
            json={"callback_query_id": cq_id, "text": text, "show_alert": show_alert},
            timeout=5,
        )
    except Exception:
        pass


def tg_send_chat_action(chat_id: int, action: str = "typing") -> None:
    try:
        requests.post(f"{API_BASE}/sendChatAction", json={"chat_id": chat_id, "action": action}, timeout=5)
    except Exception:
        pass


def animate_jarvis_status(chat_id: int, stop_event: threading.Event) -> Optional[int]:
    """Clean animated loading indicator."""
    frames = [
        "⏳ *Processing...*",
        "⚡ *Processing...*",
        "⏳ *Processing...*",
    ]
    msg_id = tg_send_message(chat_id, frames[0])
    if not msg_id:
        return None

    def _anim():
        i = 1
        while not stop_event.wait(0.8):
            try:
                tg_edit_message(chat_id, msg_id, frames[i % len(frames)])
                i += 1
            except Exception:
                break

    threading.Thread(target=_anim, daemon=True).start()
    return msg_id


def tg_send_document(chat_id: int, file_bytes: bytes, filename: str, caption: str = "") -> None:
    try:
        files = {"document": (filename, io.BytesIO(file_bytes))}
        data = {"chat_id": chat_id, "caption": caption}
        requests.post(f"{API_BASE}/sendDocument", data=data, files=files, timeout=30)
    except Exception as e:
        logger.error(f"Error sending doc: {e}")


def download_telegram_file(file_id: str) -> Optional[bytes]:
    try:
        resp = requests.get(f"{API_BASE}/getFile", params={"file_id": file_id}, timeout=15)
        res = resp.json()
        if res.get("ok"):
            fp = res["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{fp}"
            down = requests.get(file_url, timeout=35)
            if down.status_code == 200:
                return down.content
    except Exception as e:
        logger.error(f"Download error: {e}")
    return None


def schedule_reminder(chat_id: int, delay_seconds: int, reminder_text: str) -> None:
    def send_later():
        tg_send_message(chat_id, f"⏰ *Reminder:*\n{reminder_text}", reply_markup=get_main_menu_kb())
    t = threading.Timer(delay_seconds, send_later)
    t.daemon = True
    t.start()


def sync_bot_commands() -> None:
    commands = [
        {"command": "start", "description": "🏠 Main Hub (Laptop / Cloud)"},
        {"command": "laptop", "description": "💻 Laptop Controls & Toggles"},
        {"command": "cloud", "description": "☁️ Cloud Server Operations"},
        {"command": "screenshot", "description": "📸 Capture Screen"},
        {"command": "webcam", "description": "📷 Capture Webcam Photo"},
        {"command": "battery", "description": "🔋 Battery & Power Level"},
        {"command": "lock", "description": "🔒 Lock / Unlock Screen"},
        {"command": "mute", "description": "🔇 Mute / Unmute Audio"},
        {"command": "status", "description": "📊 Live System Status"},
        {"command": "help", "description": "❓ Help & Command Guide"},
    ]
    try:
        requests.post(f"{API_BASE}/setMyCommands", json={"commands": commands}, timeout=10)
    except Exception as e:
        logger.error(f"Cmd sync failed: {e}")


# ==============================================================================
# STATUS TEXT HELPERS
# ==============================================================================
def get_status_text() -> str:
    sys_stat = system_status()
    cfg = get_runtime_config()
    facts = get_all_facts()
    laptop_status = "ONLINE 🟢" if is_laptop_online() else "OFFLINE 🔴"
    owner = cfg.get("owner_username", "kissbilla2")
    return (
        "⚡ *Hermes System Status*\n\n"
        f"> 👤 *User:* `@{owner}`\n"
        f"> 💻 *Laptop:* `{laptop_status}`\n"
        f"> ☁️ *Cloud Server:* `ONLINE 🟢`\n"
        f"> 🎮 *Remote Access:* `{'ON 🟢' if _is_remote_active else 'OFF 🔴'}`\n"
        f"> ⚡ *Auto-Approve:* `{'ON 🟢' if _is_auto_approve_active else 'OFF 🔴'}`\n"
        f"> 🧠 *Active Facts:* `{len(facts)} items`\n\n"
        f"```\n{sys_stat}\n```"
    )


def get_help_text() -> str:
    return (
        "📖 *Hermes Quick Guide*\n\n"
        "> ⚡ *Quick Shortcuts:*\n"
        "> • `/screenshot` — Capture screen photo\n"
        "> • `/webcam` — Take camera photo\n"
        "> • `/battery` — Check battery level\n"
        "> • `/status` — System dashboard\n"
        "> • `/remind 10m [task]` — Set timer\n"
        "> • `/self` — Toggle self-use mode\n"
        "> • `/auto` — Toggle auto-approve\n\n"
        "> 🗣️ *Natural Language:*\n"
        "> Just type naturally: _'screenshot le'_, _'chrome kholo'_, _'volume 50'_\n\n"
        "🔒 *Private & Encrypted* — Locked to `@kissbilla2`"
    )


# ==============================================================================
# HEALTH SERVER
# ==============================================================================
def start_health_server(port: int = 7860) -> None:
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed.query)

            if "remote_enabled" in query_params:
                global _is_remote_active
                _is_remote_active = query_params["remote_enabled"][0] == "1"

            if "auto_approve" in query_params:
                global _is_auto_approve_active
                _is_auto_approve_active = query_params["auto_approve"][0] == "1"

            if parsed.path == "/health":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
                return
            elif parsed.path == "/api/laptop/poll":
                record_heartbeat()
                task = get_pending_task()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "task": task}).encode("utf-8"))
                return
            elif parsed.path == "/api/laptop/heartbeat":
                record_heartbeat()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
                return
            elif parsed.path == "/api/laptop/status":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"online": is_laptop_online()}).encode("utf-8"))
                return

            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK - Hermes running 24/7")

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/laptop/result":
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len)
                try:
                    data = json.loads(body.decode("utf-8"))
                    task_id = data.get("task_id")
                    output = data.get("output", "")
                    if task_id:
                        store_task_result(task_id, output)
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"ok": true}')
                    return
                except Exception:
                    self.send_response(400)
                    self.end_headers()
                    return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):
            return

    port = int(os.getenv("PORT", port))
    try:
        socketserver.TCPServer.allow_reuse_address = True
        server = socketserver.TCPServer(("0.0.0.0", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info(f"Health server on port {port}")
    except Exception as e:
        logger.warning(f"Server bind failed: {e}")


def start_cloud_keep_alive() -> None:
    """
    Render Free Tier Web Service sleeps after 15 minutes of inactivity.
    This background thread pings the public health endpoint every 7 minutes,
    keeping Render awake 24/7 even when the physical laptop is powered off!
    """
    cloud_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("HERMES_CLOUD_URL", "https://hermes-bot-kqv8.onrender.com")
    cloud_url = cloud_url.rstrip("/")
    target = f"{cloud_url}/health"

    def _keep_alive_loop():
        time.sleep(20)
        logger.info(f"🔄 Render Keep-Alive active: Pinging {target} every 7 mins.")
        while True:
            try:
                r = requests.get(target, timeout=35)
                if r.status_code == 200:
                    logger.debug("Render keep-alive ping OK (200)")
                else:
                    logger.warning(f"Render keep-alive status: {r.status_code}")
            except Exception as e:
                logger.warning(f"Render keep-alive error: {e}")
            time.sleep(420)  # Every 7 minutes

    threading.Thread(target=_keep_alive_loop, daemon=True).start()


# ==============================================================================
# MAIN BOT RUNNER
# ==============================================================================
class TelegramBotRunner:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN missing!")
        self.agent = AgentEngine()
        self.offset = 0
        sync_bot_commands()
        start_health_server()
        start_cloud_keep_alive()

    def send_result(self, chat_id: int, title: str, result: str, menu: str = None) -> None:
        """Send result with bottom shortcuts keyboard and sleek styling, occasionally attaching Sher sticker."""
        text = format_stylish_response(title, result)
        tg_send_message(chat_id, text, reply_markup=get_bottom_reply_kb(chat_id))
        maybe_send_sher_sticker(chat_id, chance=0.20)

    def switch_menu(self, chat_id: int, menu_name: str, title: str = None) -> None:
        """Switch to a submenu."""
        _user_menu_state[chat_id] = menu_name
        _laptop = "ONLINE 🟢" if is_laptop_online() else "OFFLINE 🔴"
        _remote = "ACTIVE 🟢" if _is_remote_active else "PAUSED 🔴"
        _auto = "ON 🟢" if _is_auto_approve_active else "OFF 🔴"
        menu_titles = {
            "main": get_home_text(),
            "home": get_home_text(),
            "cloud": get_cloud_page_text(),
            "music": (
                "🎵 *Hermes Music Player*\n\n"
                "• Play/Pause · Stop Music\n"
                "• Volume Up/Down (+10% / -10%)\n"
                "• Search & Play Song\n\n"
                "_Niche diye gaye 6 buttons se operate karein:_"
            ),
            "laptop": (
                "💻 *Laptop Control Panel*\n\n"
                f"• Status: `{_laptop}`\n\n"
                "• Screenshot · Webcam\n"
                "• Record Mic · Lock Screen\n"
                "• Extra Tools\n\n"
                "_Niche diye gaye 6 buttons se operate karein:_"
            ),
            "cloud": (
                "☁️ *Cloud Server (24/7 Live)*\n\n"
                "• Status & Telemetry\n"
                "• Workspace Files & Quick Test\n"
                "• Self-Diagnostics & Reset Memory\n\n"
                "_Niche diye gaye 6 buttons se operate karein:_"
            ),
            "extra": (
                "🌟 *Extra Tools*\n\n"
                "• Mouse Controls\n"
                "• Alarm Siren & CCTV Mode\n"
                "• Find Location & Ghost Mode\n\n"
                "_Niche diye gaye 6 buttons se operate karein:_"
            ),
            "mouse": (
                "🖱️ *Mouse & Keyboard Controls*\n\n"
                "• Left Click · Right Click\n"
                "• Scroll Up · Scroll Down\n"
                "• Press Enter\n\n"
                "_Niche diye gaye 6 buttons se operate karein:_"
            ),
            "browser": (
                "🌐 *Browser & Apps*\n\n"
                "• `open [app name]` (e.g. `open chrome`)\n"
                "• `open [URL]`"
            ),
            "security": (
                "🚨 *Security & Surveillance*\n\n"
                "• `lock` · `unlock`\n"
                "• `alarm on` · `alarm off`\n"
                "• `cctv on` · `cctv off`"
            ),
            "ai": (
                "🤖 *AI & Automation*\n\n"
                "• `/auto` — Toggle auto-approve\n"
                "• `/diagnose` — Test API health\n"
                "• Antigravity task approval"
            ),
            "clipboard": (
                "📋 *Clipboard & Notes*\n\n"
                "• `clipboard read`\n"
                "• `clipboard write [text]`\n"
                "• `save note [text]`"
            ),
            "network": (
                "📶 *Network & Hotspot*\n\n"
                "• `wifi` — WiFi status\n"
                "• `hotspot start` · `hotspot stop`"
            ),
            "terminal": (
                "🔧 *Terminal & Files*\n\n"
                "• `run [bash command]`\n"
                "• `list files`\n"
                "• `read file [path]`"
            ),
            "reminders": (
                "⏰ *Reminders & Timer*\n\n"
                "• `/remind 10m [task]` — Set timer\n"
                "• `show memory`"
            ),
            "toggles": (
                "🎛️ *Quick Switches*\n\n"
                f"• Self-Use Mode: `{'ON' if not _is_remote_active else 'OFF'}`\n"
                f"• Auto-Approve: `{'ON' if _is_auto_approve_active else 'OFF'}`\n"
                f"• Screen Lock: `{'LOCKED' if _is_locked else 'UNLOCKED'}`\n"
                f"• Audio: `{'MUTED' if _is_muted else 'UNMUTED'}`\n"
                f"• CCTV Mode: `{'ON' if _is_cctv_active else 'OFF'}`"
            ),
            "help": (
                "❓ *Help & Commands*\n\n"
                "• `/screenshot` — Capture screen\n"
                "• `/webcam` — Camera photo\n"
                "• `/battery` — Battery percentage\n"
                "• `/status` — System telemetry\n"
                "• `/remind 10m [task]` — Set reminder\n"
                "• `/self` — Toggle self-use mode\n"
                "• `/auto` — Toggle auto-approve\n"
                "• `/diagnose` — Test API connectivity\n"
                "• `/reset` — Clear memory\n\n"
                "_Chat me kuch bhi normal bhasha me bolein, AI execute karega._"
            ),
        }
        text = title or menu_titles.get(menu_name, "📱 *Hermes AI*\n\nCommand bhejein:")
        tg_send_message(chat_id, text, reply_markup=get_kb_for(menu_name, chat_id))

    def handle_button_or_command(self, chat_id: int, user_id: int, text: str) -> bool:
        """Main button/command router - clean and organized."""
        global _is_remote_active, _is_locked, _is_muted, _is_auto_approve_active
        global _is_cctv_active, _is_hotspot_active, _is_ghost_mode, _is_alarm_active

        clean = text.strip()
        cmd = clean.split()[0].lower() if clean else ""
        low = clean.lower()

        # ==================== HANDLE PENDING INPUT ====================
        if chat_id in _user_pending_input:
            if low in ("stop", "cancel", "chup", "band", "exit", "back", "ruk", "ruko", "/cancel", "/stop", "🛑"):
                _user_pending_input.pop(chat_id, None)
                self.send_result(chat_id, "🚫 *Action Cancelled:*", "Pending input cancel kar diya gaya hai.")
                return True
            pending = _user_pending_input.pop(chat_id)
            if pending == "type_text":
                res = laptop_type(clean)
                self.send_result(chat_id, "⌨️ *Text Typed:*", res)
                return True
            elif pending == "human_type":
                res = laptop_human_type(clean, press_enter=False)
                self.send_result(chat_id, "⌨️ *Human Typed:*", res)
                return True
            elif pending == "url":
                res = laptop_open_url(clean)
                self.send_result(chat_id, "🌐 *URL Opened:*", res)
                return True
            elif pending == "open_app":
                res = laptop_human_open_app(clean)
                self.send_result(chat_id, f"🚀 *Opening {clean}:*", res)
                return True
            elif pending == "click_element":
                res = laptop_screen_vision_click(clean)
                self.send_result(chat_id, f"🎯 *Clicking '{clean}':*", res)
                return True
            elif pending == "tts":
                res = laptop_speak(clean)
                self.send_result(chat_id, "🗣️ *Speaking:*", res)
                return True
            elif pending == "play_song":
                res = laptop_play_music(clean)
                self.send_result(chat_id, f"🎵 *Playing '{clean}':*", res)
                return True
            elif pending == "volume_percent":
                try:
                    vol = int(clean.replace("%", "").strip())
                    res = execute_on_laptop(f"pactl set-sink-volume @DEFAULT_SINK@ {vol}%")
                    self.send_result(chat_id, f"🎚️ *Volume set to {vol}%*", res)
                except Exception as e:
                    self.send_result(chat_id, "❌ Invalid number", str(e))
                return True
            elif pending == "bash_cmd":
                res = execute_on_laptop(clean)
                self.send_result(chat_id, "💻 *Command Output:*", f"```\n{res}\n```")
                return True
            elif pending == "clipboard_write":
                res = laptop_clipboard(clean)
                self.send_result(chat_id, "✏️ *Clipboard Updated:*", res)
                return True
            elif pending == "save_note":
                _notes_storage.setdefault(user_id, []).append(clean)
                save_fact(f"note_{int(time.time())}", clean)
                self.send_result(chat_id, "📝 *Note Saved:*", f"_{clean}_")
                return True
            elif pending == "reminder":
                parts = clean.split(maxsplit=1)
                if len(parts) >= 2:
                    time_str = parts[0].lower()
                    msg = parts[1]
                    seconds = 0
                    if time_str.endswith("s"):
                        seconds = int(time_str[:-1])
                    elif time_str.endswith("m"):
                        seconds = int(time_str[:-1]) * 60
                    elif time_str.endswith("h"):
                        seconds = int(time_str[:-1]) * 3600
                    elif time_str.isdigit():
                        seconds = int(time_str) * 60
                    if seconds > 0:
                        schedule_reminder(chat_id, seconds, msg)
                        self.send_result(chat_id, "⏰ *Reminder Set!*", f"After {time_str}: _{msg}_")
                        return True
                self.send_result(chat_id, "❌ Invalid Format", "Use: `10m task name`")
                return True

        # ==================== 0. MASTER UNIVERSAL EMERGENCY STOP ====================
        UNIVERSAL_STOP_WORDS = {
            "stop", "stop!", "stop.", "/stop", "🛑",
            "chup", "chup kar", "chup karo", "chup ho ja", "chup raho", "chup!",
            "band", "band kar", "band karo", "band kar do", "band ho ja",
            "shhh", "shh", "quiet", "silence",
            "halt", "kill", "abort", "ruk", "ruko", "rok", "roko",
            "emergency stop", "emergency stop!", "/kill",
            "sab band", "sab band kar", "sab band karo", "sab roko", "sab stop",
            "stop all", "stop everything", "kill all",
        }
        if low in UNIVERSAL_STOP_WORDS:
            _user_pending_input.pop(chat_id, None)
            _is_alarm_active = False
            _is_cctv_active = False
            _is_auto_approve_active = False
            _is_ghost_mode = False
            res = laptop_emergency_stop_all()
            self.send_result(
                chat_id,
                "🛑 *EMERGENCY STOP (SAB BAND):*",
                f"{res}\n\n_Malik, sabhi loud sirens, music, CCTV motion alerts, background audio aur tasks turant band kar diye gaye hain!_"
            )
            return True

        # ==================== 0B. GRANULAR TARGETED STOP COMMANDS ====================
        # 1. Alarm / Siren Stop
        ALARM_STOP_WORDS = {
            "stop alarm", "stop siren", "alarm stop", "siren stop",
            "alarm band", "alarm band kar", "alarm band karo", "alarm off",
            "siren band", "siren band kar", "siren band karo", "siren off",
            "silence alarm", "quiet alarm", "/stopalarm",
        }
        if low in ALARM_STOP_WORDS or clean == "⏹️ Stop Alarm":
            _is_alarm_active = False
            res = laptop_stop_alarm()
            self.send_result(chat_id, "⏹️ *Alarm Siren Stopped:*", res)
            return True

        # 2. Music / Audio Stop
        MUSIC_STOP_WORDS = {
            "stop music", "stop song", "music stop", "song stop",
            "stop gana", "stop gaana", "gana band", "gaana band",
            "gana band kar", "gaana band kar", "gana band karo", "gaana band karo",
            "music band", "music band kar", "music band karo", "music off",
            "pause music", "stop audio", "/stopmusic",
        }
        if low in MUSIC_STOP_WORDS or clean in ("⏹️ Stop Music", "⏹️ Stop"):
            res = laptop_stop_music()
            self.send_result(chat_id, "⏹️ *Music Stopped:*", res)
            return True

        # 3. CCTV Motion Watcher Stop
        CCTV_STOP_WORDS = {
            "stop cctv", "cctv stop", "cctv band", "cctv band kar", "cctv band karo",
            "cctv off", "stop motion", "motion stop", "motion off",
            "camera band", "camera band kar", "/stopcctv",
        }
        if low in CCTV_STOP_WORDS or clean in ("🛑 Stop CCTV",):
            _is_cctv_active = False
            res = laptop_stop_cctv()
            self.send_result(chat_id, "🛑 *CCTV Motion Watcher Stopped:*", res)
            return True

        # 4. Recording Stop (Mic / Webcam Video)
        RECORD_STOP_WORDS = {
            "stop recording", "stop record", "recording stop", "stop mic",
            "mic stop", "stop video", "video stop", "recording band",
            "recording band kar", "mic band kar", "video band kar",
        }
        if low in RECORD_STOP_WORDS:
            res = laptop_stop_recording()
            self.send_result(chat_id, "⏹️ *Recording Aborted:*", res)
            return True

        # 5. Auto-Approve / Task Runner Stop
        AUTO_STOP_WORDS = {
            "stop auto", "auto stop", "auto off", "cancel auto", "abort auto",
            "stop approve", "stop approval", "cancel task", "abort task", "task band kar",
        }
        if low in AUTO_STOP_WORDS or clean == "⚡ Auto Mode: OFF":
            _is_auto_approve_active = False
            res = laptop_auto_off()
            laptop_key_ctrlc()
            self.send_result(chat_id, "⚡ *Auto Mode Stopped:*", "Autonomous approvals band kar diye gaye aur task cancel kiya gaya.")
            return True

        # 6. Ghost Mode / Screen Wake
        GHOST_STOP_WORDS = {
            "stop ghost", "ghost off", "ghost stop", "screen on", "display on",
            "screen chalu", "screen chalu kar", "light on", "wake up", "wake screen",
            "☀️ display on", "☀️ screen on",
        }
        if low in GHOST_STOP_WORDS or clean in ("☀️ Display ON", "☀️ Screen ON"):
            _is_ghost_mode = False
            res = laptop_screen_on()
            self.send_result(chat_id, "☀️ *Display Awakened:*", res)
            return True

        # 7. Speech / TTS Stop
        TTS_STOP_WORDS = {
            "stop speaking", "stop speak", "stop tts", "tts stop", "chup bolna", "speaking off",
        }
        if low in TTS_STOP_WORDS:
            execute_on_laptop("killall spd-say espeak-ng espeak 2>/dev/null")
            self.send_result(chat_id, "🤐 *Speech Muted:*", "Laptop speech/TTS mute kar diya gaya hai.")
            return True

        # ==================== ROOT COMMANDS ====================
        if cmd in ("/start", "/menu", "/main", "/home") or clean in ("🏠 Main Menu", "🔙 Main Menu", "📱 Menu", "Main Menu"):
            cfg = get_runtime_config()
            if cfg.get("owner_user_id") is None:
                set_owner(user_id)
            self.switch_menu(chat_id, "main")
            return True

        if cmd == "/setsticker":
            parts = clean.split()
            if len(parts) >= 2:
                action = parts[1].lower()
                last_id = _last_received_sticker.get(chat_id)
                if last_id:
                    save_custom_sticker(action, last_id)
                    tg_send_sticker(chat_id, last_id)
                    self.send_result(
                        chat_id,
                        f"✅ *Custom Sticker Set for '{action}'!*",
                        f"Abse jab bhi `{action}` execute hoga, ye sticker bhejunga!",
                    )
                    return True
                else:
                    self.send_result(
                        chat_id,
                        "⚠️ *Pehle koi sticker bhejein!*",
                        "Telegram pe koi bhi sticker bhejein, fir type karein: `/setsticker <action>`\n\nAvailable actions: `screenshot`, `webcam`, `battery`, `music`, `lock`, `done`, `ready`",
                    )
                    return True
            else:
                self.send_result(
                    chat_id,
                    "💡 *Usage:* `/setsticker [action]`",
                    "Available actions: `screenshot`, `webcam`, `battery`, `music`, `lock`, `done`, `ready`",
                )
                return True

        if cmd in ("/sher", "/sticker"):
            maybe_send_sher_sticker(chat_id, force=True)
            return True

        # ==================== CATEGORY SWITCHES ====================
        category_map = {
            # Dedicated Music Player Section
            "🎵 Music Player": "music",
            "🎵 Music": "music",
            "/music": "music",
            "Music Player": "music",
            "🎵 Music Dashboard": "music",

            # Top-Level Dashboards & Navigation
            "💻 Laptop Mode": "laptop",
            "💻 Laptop Control Panel": "laptop",
            "💻 Laptop Controls": "laptop",
            "💻 Laptop": "laptop",
            "/laptop": "laptop",
            "☁️ Cloud Server": "cloud",
            "☁️ Cloud Mode": "cloud",
            "☁️ Cloud": "cloud",
            "/cloud": "cloud",
            "/server": "cloud",
            "🌟 Extra Tools ➡️": "extra",
            "🌟 Extra Tools": "extra",
            "🔙 Extra Tools": "extra",
            "🔙 Laptop Menu": "laptop",
            "🔙 Back to Laptop": "laptop",
            "🔙 Back": "laptop",

            # Sub-category menus
            "📸 Camera & Media": "camera",
            "🎙️ Audio & Voice": "audio",
            "🖥️ System Info": "system",
            "⚡ Power & Screen": "power",
            "⚡ Power & Ghost Mode": "power",
            "⚡ Power Mode": "power",
            "/power": "power",
            "🔊 Volume & Sound": "volume",
            "🔊 Volume & Media": "volume",
            "🎵 Media & Sound": "volume",
            "🎵 Media Control": "volume",
            "/volume": "volume",
            "/sound": "volume",
            "🖱️ Mouse Controls": "mouse",
            "🖱️ Mouse & Keyboard": "mouse",
            "/mouse": "mouse",
            "🌐 Browser & Apps": "browser",
            "/browser": "browser",
            "/apps": "browser",
            "🚨 Security & Spy": "security",
            "🛡️ Spy & Security": "security",
            "/security": "security",
            "/spy": "security",
            "🤖 AI & Automation": "ai",
            "🤖 Sandbox & AI": "ai",
            "🤖 AI & Terminal": "ai",
            "🤖 Sandbox": "ai",
            "/ai": "ai",
            "/sandbox": "ai",
            "📋 Clipboard & Notes": "clipboard",
            "/clipboard": "clipboard",
            "📶 Network & Offline": "network",
            "📶 Network & Hotspot": "network",
            "/network": "network",
            "/wifi": "network",
            "🔧 Terminal & Files": "terminal",
            "/terminal": "terminal",
            "/bash": "terminal",
            "⏰ Reminders & Memory": "reminders",
            "/remind": "reminders",
            "🎛️ Quick Toggles": "toggles",
            "/toggles": "toggles",
            "❓ Help & Status": "help",
            "/help": "help",
        }
        if clean in category_map:
            self.switch_menu(chat_id, category_map[clean])
            return True

        # ==================== CAMERA & MEDIA ====================
        if clean in ("📸 Quick Screen", "📸 Screenshot", "📸 Screen Peek") or cmd == "/screenshot" or low in ("screenshot", "screen shot", "quick screen"):
            temp = tg_send_message(chat_id, "📸 Capturing screen...")
            res = laptop_screenshot()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "📸 *Screenshot Sent!*", "Screen photo bhej di gayi hai.")
            return True

        if clean in ("📷 Front Camera Photo", "📷 Webcam") or cmd == "/webcam" or low in ("selfie", "webcam", "camera photo"):
            temp = tg_send_message(chat_id, "📷 Capturing webcam...")
            res = laptop_webcam()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "📷 *Webcam Photo Sent!*", "Front camera photo delivered.")
            return True

        if clean == "🎥 5s Webcam Video":
            temp = tg_send_message(chat_id, "🎥 Recording 5s video...")
            res = laptop_webcam_video()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "🎥 *5s Video Sent!*", "Video clip delivered.")
            return True

        if clean == "🎥 10s Webcam Video":
            temp = tg_send_message(chat_id, "🎥 Recording 10s video...")
            res = laptop_webcam_video()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "🎥 *10s Video Sent!*", "Video clip delivered.")
            return True

        if clean == "🧹 Clean Photos":
            res = laptop_clean_photos()
            self.send_result(chat_id, "🧹 *Photos Cleaned:*", res)
            return True

        if clean == "🖼️ AI Photo Analysis":
            self.send_result(chat_id, "🖼️ *AI Photo Analysis:*", "Ab koi bhi photo bhejein, AI usay analyze karega!")
            return True

        # ==================== AUDIO & VOICE ====================
        if clean in ("🎙️ Record Mic 10s", "🎙️ Record Mic") or cmd == "/mic" or low in ("mic", "record audio"):
            temp = tg_send_message(chat_id, "🎙️ Recording 10s audio...")
            res = laptop_mic(10)
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "🎙️ *10s Audio Sent!*", "Voice note delivered.")
            return True

        if clean == "🎙️ Record Mic 30s":
            temp = tg_send_message(chat_id, "🎙️ Recording 30s audio...")
            res = laptop_mic(30)
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "🎙️ *30s Audio Sent!*", "Voice note delivered.")
            return True

        if clean == "🗣️ Text-to-Speech":
            _user_pending_input[chat_id] = "tts"
            self.send_result(chat_id, "🗣️ *TTS Mode:*", "Ab wo text bhejein jo laptop bolega:")
            return True

        if clean == "📝 Voice Transcribe":
            self.send_result(chat_id, "📝 *Voice Transcription:*", "Voice note bhejein, main transcribe karunga!")
            return True

        # ==================== SYSTEM INFO ====================
        if clean in ("🔋 Battery Status", "🔋 Battery") or cmd == "/battery" or low in ("battery", "charge"):
            res = laptop_battery()
            self.send_result(chat_id, "🔋 *Battery Status:*", res)
            return True

        if clean == "⚡ Charging Alert":
            res = laptop_battery()
            self.send_result(chat_id, "⚡ *Charging Info:*", res)
            return True

        if clean == "💻 CPU & RAM Usage":
            res = execute_on_laptop("top -bn1 | head -20 && free -h")
            self.send_result(chat_id, "💻 *CPU & RAM:*", f"```\n{res}\n```")
            return True

        if clean == "💾 Disk Space":
            res = execute_on_laptop("df -h")
            self.send_result(chat_id, "💾 *Disk Space:*", f"```\n{res}\n```")
            return True

        if clean == "🌡️ CPU Temperature":
            res = execute_on_laptop("sensors 2>/dev/null | grep -E 'Core|Package' || cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -5")
            self.send_result(chat_id, "🌡️ *CPU Temperature:*", f"```\n{res}\n```")
            return True

        if clean == "📶 WiFi Name":
            res = execute_on_laptop("iwgetid -r 2>/dev/null || nmcli -t -f active,ssid dev wifi | grep '^yes' | cut -d: -f2")
            self.send_result(chat_id, "📶 *Connected WiFi:*", f"`{res.strip()}`")
            return True

        if clean == "🌍 Public IP":
            res = execute_on_laptop("curl -s ifconfig.me || curl -s ipinfo.io/ip")
            self.send_result(chat_id, "🌍 *Public IP:*", f"`{res.strip()}`")
            return True

        if clean == "🏠 Local IP":
            res = execute_on_laptop("hostname -I | awk '{print $1}'")
            self.send_result(chat_id, "🏠 *Local IP:*", f"`{res.strip()}`")
            return True

        if clean in ("📍 Laptop Location", "📍 Find Location") or cmd == "/locate" or low in ("location", "find laptop"):
            temp = tg_send_message(chat_id, "📍 Fetching location...")
            res = laptop_location()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "📍 *Location:*", res)
            return True

        if clean in ("📊 Full System Status", "📊 Status", "📊 System Status") or cmd == "/status" or low == "status":
            self.send_result(chat_id, "", get_status_text())
            return True

        # ==================== POWER & SCREEN ====================
        if clean in ("🔒 Lock Screen", "🔓 Unlock Screen") or cmd in ("/lock", "/unlock") or low in ("lock", "unlock"):
            res = laptop_lock_toggle()
            _is_locked = not _is_locked if "LOCKED" not in res.upper() and "UNLOCKED" not in res.upper() else ("LOCKED" in res.upper() and "UNLOCKED" not in res.upper())
            self.send_result(chat_id, "🔒 *Screen Lock Toggled:*", res)
            return True

        if clean in ("🕶️ Display OFF (Ghost)", "☀️ Display ON", "🕶️ Ghost Mode") or low in ("ghost", "display off", "screen off", "ghost mode"):
            if _is_ghost_mode:
                res = laptop_screen_on()
                _is_ghost_mode = False
            else:
                res = laptop_ghost_mode()
                _is_ghost_mode = True
            self.send_result(chat_id, "🕶️ *Ghost Mode Toggled:*", res)
            return True

        if clean == "💤 Sleep Laptop" or low in ("sleep", "suspend"):
            res = laptop_power_sleep()
            self.send_result(chat_id, "💤 *Sleep:*", res)
            return True

        if clean == "🔄 Reboot Laptop" or low in ("reboot", "restart"):
            res = laptop_power_reboot()
            self.send_result(chat_id, "🔄 *Reboot:*", res)
            return True

        if clean == "⛔ Shutdown Laptop" or low == "shutdown":
            res = laptop_power_poweroff()
            self.send_result(chat_id, "⛔ *Shutdown:*", res)
            return True

        # ==================== VOLUME & SOUND ====================
        if clean in ("🔉 Vol -", "🔉 Volume Down", "🔉 Vol Down (-10%)") or low in ("vol down", "volume down", "vol -", "voldown", "-10%"):
            res = laptop_vol_down()
            self.send_result(chat_id, "🔉 *Volume Down:*", res)
            return True

        if clean in ("🔊 Vol +", "🔊 Volume Up", "🔊 Vol Up (+10%)") or low in ("vol up", "volume up", "vol +", "volup", "+10%"):
            res = laptop_vol_up()
            self.send_result(chat_id, "🔊 *Volume Up:*", res)
            return True

        if clean in ("🔇 Mute", "🔊 Unmute", "🔇 Mute / Unmute") or cmd in ("/mute", "/unmute") or low in ("mute", "unmute", "mute / unmute"):
            res = laptop_mute()
            _is_muted = not _is_muted
            self.send_result(chat_id, "🔇 *Audio Mute/Unmute:*", res)
            return True

        if clean == "🎚️ Set Volume %":
            _user_pending_input[chat_id] = "volume_percent"
            self.send_result(chat_id, "🎚️ *Set Volume:*", "Volume percentage bhejein (e.g., 50):")
            return True

        # ==================== MEDIA CONTROL ====================
        if clean in ("⏯️ Play/Pause", "⏯️ Play / Pause") or low in ("play/pause", "play / pause", "pause"):
            res = laptop_playpause()
            self.send_result(chat_id, "⏯️ *Media:*", res)
            return True

        if clean in ("⏹️ Stop Music", "⏹️ Stop") or low in ("stop music", "stop"):
            res = laptop_stop_music()
            self.send_result(chat_id, "⏹️ *Music Stopped:*", res)
            return True

        if clean == "⏭️ Next Track":
            res = execute_on_laptop("playerctl next 2>/dev/null || xdotool key XF86AudioNext")
            self.send_result(chat_id, "⏭️ *Next Track:*", res)
            return True

        if clean in ("⏮️ Prev Track", "⏮️ Previous Track"):
            res = execute_on_laptop("playerctl previous 2>/dev/null || xdotool key XF86AudioPrev")
            self.send_result(chat_id, "⏮️ *Previous Track:*", res)
            return True

        if clean in ("🎵 Play Song", "🎵 Play Song (Search)", "🔍 Search & Play") or low in ("search & play", "play song"):
            _user_pending_input[chat_id] = "play_song"
            self.send_result(chat_id, "🔍 *Search & Play:*", "YouTube ya gaane ka naam bhejein, laptop pe play ho jayega:")
            return True

        # ==================== MOUSE & KEYBOARD ====================
        if clean == "🖱️ Left Click":
            res = laptop_human_click()
            self.send_result(chat_id, "🖱️ *Left Click:*", res)
            return True

        if clean == "🖱️ Right Click":
            res = execute_on_laptop("xdotool click 3")
            self.send_result(chat_id, "🖱️ *Right Click:*", res or "Right clicked!")
            return True

        if clean == "⬆️ Scroll Up":
            res = laptop_human_scroll("up", 5)
            self.send_result(chat_id, "⬆️ *Scroll Up:*", res)
            return True

        if clean == "⬇️ Scroll Down":
            res = laptop_human_scroll("down", 5)
            self.send_result(chat_id, "⬇️ *Scroll Down:*", res)
            return True

        if clean == "👁️ AI Vision Click":
            temp = tg_send_message(chat_id, "👁️ Analyzing screen...")
            res = laptop_screen_inspect("Describe current screen contents")
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "👁️ *Screen Analysis:*", res)
            return True

        if clean == "🎯 Click Element":
            _user_pending_input[chat_id] = "click_element"
            self.send_result(chat_id, "🎯 *AI Click:*", "Element name bhejein (e.g., 'play button'):")
            return True

        if clean == "⌨️ Type Text":
            _user_pending_input[chat_id] = "type_text"
            self.send_result(chat_id, "⌨️ *Type Text:*", "Wo text bhejein jo type karna hai:")
            return True

        if clean == "⌨️ Human Type":
            _user_pending_input[chat_id] = "human_type"
            self.send_result(chat_id, "⌨️ *Human Type:*", "Text bhejein (real human speed se type hoga):")
            return True

        if clean == "↩️ Press Enter":
            res = laptop_key_enter()
            self.send_result(chat_id, "↩️ *Enter Pressed:*", res)
            return True

        if clean == "🛑 Press Ctrl+C":
            res = laptop_key_ctrlc()
            self.send_result(chat_id, "🛑 *Ctrl+C:*", res)
            return True

        if clean == "⎋ Press Esc":
            res = execute_on_laptop("xdotool key Escape")
            self.send_result(chat_id, "⎋ *Esc Pressed:*", res or "Sent!")
            return True

        if clean == "␣ Press Space":
            res = execute_on_laptop("xdotool key space")
            self.send_result(chat_id, "␣ *Space Pressed:*", res or "Sent!")
            return True

        if clean == "⇥ Press Tab":
            res = execute_on_laptop("xdotool key Tab")
            self.send_result(chat_id, "⇥ *Tab Pressed:*", res or "Sent!")
            return True

        if clean == "❌ Press Alt+F4":
            res = execute_on_laptop("xdotool key alt+F4")
            self.send_result(chat_id, "❌ *Alt+F4:*", res or "Window closed!")
            return True

        # ==================== BROWSER & APPS ====================
        if clean == "🌐 Open URL":
            _user_pending_input[chat_id] = "url"
            self.send_result(chat_id, "🌐 *Open URL:*", "URL bhejein (e.g., youtube.com):")
            return True

        if clean == "🌐 Open Chrome":
            res = laptop_human_open_app("chrome")
            self.send_result(chat_id, "🌐 *Chrome:*", res)
            return True

        if clean == "💻 Open VS Code":
            res = laptop_human_open_app("code")
            self.send_result(chat_id, "💻 *VS Code:*", res)
            return True

        if clean == "⌨️ Open Terminal":
            res = laptop_human_open_app("terminal")
            self.send_result(chat_id, "⌨️ *Terminal:*", res)
            return True

        if clean == "🎵 Open Spotify":
            res = laptop_human_open_app("spotify")
            self.send_result(chat_id, "🎵 *Spotify:*", res)
            return True

        if clean == "🚀 Open Any App":
            _user_pending_input[chat_id] = "open_app"
            self.send_result(chat_id, "🚀 *Open App:*", "App name bhejein:")
            return True

        if low in ("antigravity", "antygravity", "open antigravity", "antigravity on kar", "mere antygravity on kar", "mere antigravity on kar", "antigravity chalao", "antigravity open karo"):
            res = laptop_human_open_app("antigravity")
            self.send_result(chat_id, "🚀 *Antigravity IDE:*", "Antigravity IDE launch kar diya hai laptop screen par! ✨")
            return True

        if clean == "📱 Running Apps" or cmd == "/apps":
            res = laptop_apps()
            self.send_result(chat_id, "📱 *Running Apps:*", res)
            return True

        # ==================== SECURITY & SPY ====================
        if clean in ("🚨 Siren Alarm", "🚨 Alarm Siren") or low in ("alarm", "siren"):
            _is_alarm_active = True
            res = laptop_alarm()
            self.send_result(chat_id, "🚨 *Alarm ON:*", res)
            return True

        if clean == "⏹️ Stop Alarm" or low in ("stop alarm", "stop siren"):
            _is_alarm_active = False
            res = laptop_stop_alarm()
            self.send_result(chat_id, "⏹️ *Alarm Stopped:*", res)
            return True

        if clean in ("👁️ Start CCTV Motion", "🛑 Stop CCTV", "👁️ CCTV Mode") or low == "cctv":
            res = laptop_cctv_toggle()
            _is_cctv_active = not _is_cctv_active
            self.send_result(chat_id, "👁️ *CCTV Mode Toggled:*", res)
            return True

        if clean == "📷 Silent Snap":
            temp = tg_send_message(chat_id, "📷 Silent capture...")
            res = laptop_webcam()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "📷 *Silent Snap Sent!*", "")
            return True

        if clean == "🎥 Silent Video":
            temp = tg_send_message(chat_id, "🎥 Silent recording...")
            res = laptop_webcam_video()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "🎥 *Silent Video Sent!*", "")
            return True

        # ==================== AI & AUTOMATION ====================
        if clean in ("🔴 Self-Use Mode", "🟢 Remote Mode", "🟢 Enable Remote", "🔴 Self-Use Pause") or cmd == "/self":
            res = laptop_remote_toggle()
            _is_remote_active = not _is_remote_active
            self.send_result(chat_id, "🎮 *Remote Mode Toggled:*", res)
            return True

        if clean in ("⚡ Auto-Approve: ON 🟢", "⚡ Auto-Approve: OFF 🔴", "⚡ Auto: ON 🟢", "⚡ Auto: OFF 🔴", "⚡ Auto Approve") or cmd == "/auto":
            res = laptop_auto_toggle()
            _is_auto_approve_active = not _is_auto_approve_active
            self.send_result(chat_id, "⚡ *Auto-Approve Toggled:*", res)
            return True

        if clean == "♾️ Auto Always ON":
            res = laptop_auto_always()
            _is_auto_approve_active = True
            self.switch_menu(chat_id, "ai", f"♾️ *Auto Always ON:*\n\n{res}")
            return True

        if clean == "🎯 Auto Task Only":
            res = laptop_auto_on()
            _is_auto_approve_active = True
            self.switch_menu(chat_id, "ai", f"🎯 *Auto Task Mode:*\n\n{res}")
            return True

        if clean == "🛑 Auto OFF":
            res = laptop_auto_off()
            _is_auto_approve_active = False
            self.switch_menu(chat_id, "ai", f"🛑 *Auto OFF:*\n\n{res}")
            return True

        if clean == "📊 AI Status":
            res = laptop_ai_status()
            self.send_result(chat_id, "📊 *AI Status:*", res)
            return True

        if clean == "✅ Approve (Enter)":
            res = laptop_key_enter()
            self.send_result(chat_id, "✅ *Approved:*", res)
            return True

        if clean == "🟢 Send 'y'":
            res = laptop_key_y()
            self.send_result(chat_id, "🟢 *Yes Sent:*", res)
            return True

        if clean == "🔴 Send 'n'":
            res = laptop_key_n()
            self.send_result(chat_id, "🔴 *No Sent:*", res)
            return True

        if clean == "🛑 Cancel Ctrl+C":
            res = laptop_key_ctrlc()
            self.send_result(chat_id, "🛑 *Cancelled:*", res)
            return True

        # Number choices
        if clean in ("1️⃣", "2️⃣", "3️⃣") or (clean.isdigit() and len(clean) <= 2):
            num_map = {"1️⃣": 1, "2️⃣": 2, "3️⃣": 3}
            num = num_map.get(clean) or int(clean)
            res = laptop_key_num(num)
            self.send_result(chat_id, f"🔢 *Choice {num}:*", res)
            return True

        # ==================== CLIPBOARD & NOTES ====================
        if clean == "📋 Read Clipboard":
            res = laptop_clipboard()
            self.send_result(chat_id, "📋 *Clipboard:*", res)
            return True

        if clean == "✏️ Write Clipboard":
            _user_pending_input[chat_id] = "clipboard_write"
            self.send_result(chat_id, "✏️ *Write Clipboard:*", "Text bhejein:")
            return True

        if clean == "📝 Save Note":
            _user_pending_input[chat_id] = "save_note"
            self.send_result(chat_id, "📝 *Save Note:*", "Note text bhejein:")
            return True

        if clean == "📖 Recall Notes":
            notes = _notes_storage.get(user_id, [])
            facts = get_all_facts()
            all_notes = notes + [f"{k}: {v}" for k, v in facts.items() if k.startswith("note_")]
            if all_notes:
                text = "\n".join(f"• {n}" for n in all_notes[-20:])
                self.send_result(chat_id, "📖 *Your Notes:*", text)
            else:
                self.send_result(chat_id, "📖 *Notes:*", "Koi note nahi hai abhi.")
            return True

        # ==================== NETWORK & OFFLINE ====================
        if clean == "📶 WiFi Status" or cmd == "/wifi":
            res = laptop_wifi()
            self.send_result(chat_id, "📶 *WiFi Status:*", res)
            return True

        if clean == "🌍 Check Internet":
            res = execute_on_laptop("ping -c 3 google.com")
            self.send_result(chat_id, "🌍 *Internet Test:*", f"```\n{res}\n```")
            return True

        if clean in ("📡 Start Hotspot", "🛑 Stop Hotspot"):
            if _is_hotspot_active:
                res = laptop_hotspot_stop()
                _is_hotspot_active = False
            else:
                res = laptop_hotspot_start()
                _is_hotspot_active = True
            self.switch_menu(chat_id, "network", f"📡 *Hotspot Toggled:*\n\n{res}")
            return True

        if clean == "📊 Hotspot Status":
            res = laptop_hotspot_status()
            self.send_result(chat_id, "📊 *Hotspot Status:*", res)
            return True

        if clean == "🌐 Offline Hub URL":
            res = laptop_offline_url()
            self.send_result(chat_id, "🌐 *Offline Hub:*", res)
            return True

        if clean == "📱 Offline Hub QR":
            res = laptop_offline_qr()
            self.send_result(chat_id, "📱 *Offline QR:*", res)
            return True

        # ==================== TERMINAL & FILES ====================
        if clean == "💻 Run Bash Command":
            _user_pending_input[chat_id] = "bash_cmd"
            self.send_result(chat_id, "💻 *Bash Command:*", "Command bhejein (e.g., `ls -la`):")
            return True

        if clean == "📁 List Files" or cmd == "/files":
            res = list_directory(".")
            self.send_result(chat_id, "📁 *Workspace Files:*", f"```\n{res}\n```")
            return True

        if clean == "⬇️ Download File":
            self.send_result(chat_id, "⬇️ *Download File:*", "Chat me bolein: 'Download /path/to/file'")
            return True

        if clean == "⬆️ Upload File Info":
            self.send_result(chat_id, "⬆️ *Upload File:*", "Koi bhi file/document bhejein - main workspace me save karunga!")
            return True

        # ==================== REMINDERS & MEMORY ====================
        if clean == "⏰ Set Reminder" or cmd == "/remind":
            if cmd == "/remind":
                parts = clean.split(maxsplit=2)
                if len(parts) >= 3:
                    time_str = parts[1].lower()
                    msg = parts[2]
                    seconds = 0
                    if time_str.endswith("s"):
                        seconds = int(time_str[:-1])
                    elif time_str.endswith("m"):
                        seconds = int(time_str[:-1]) * 60
                    elif time_str.endswith("h"):
                        seconds = int(time_str[:-1]) * 3600
                    elif time_str.isdigit():
                        seconds = int(time_str) * 60
                    if seconds > 0:
                        schedule_reminder(chat_id, seconds, msg)
                        self.send_result(chat_id, "⏰ *Reminder Set!*", f"After {time_str}: _{msg}_")
                        return True
            _user_pending_input[chat_id] = "reminder"
            self.send_result(chat_id, "⏰ *Set Reminder:*", "Format: `10m task name`\nExample: `5m check server`")
            return True

        if clean == "🧠 Save to Memory":
            _user_pending_input[chat_id] = "save_note"
            self.send_result(chat_id, "🧠 *Save to Memory:*", "Fact bhejein:")
            return True

        if clean == "📖 Show Memory":
            facts = get_all_facts()
            if facts:
                text = "\n".join(f"• {k}: {v}" for k, v in list(facts.items())[-20:])
                self.send_result(chat_id, "📖 *Memory:*", text)
            else:
                self.send_result(chat_id, "📖 *Memory:*", "Koi facts saved nahi hai.")
            return True

        if clean == "🧹 Reset History" or cmd == "/reset":
            clear_history(f"tg_{chat_id}")
            self.send_result(chat_id, "🧹 *History Cleared!*", "Conversation reset ho gaya.")
            return True

        # ==================== QUICK TOGGLES ====================
        if clean == "🎨 Toggle Custom Keypad":
            self.send_result(chat_id, "🎨 *Custom Keypad:*", "Web designer par jaayein: `http://localhost:7860/designer`")
            return True

        # ==================== HELP & STATUS ====================
        if clean in ("🩺 Self-Diagnostics", "/diagnose") or cmd == "/diagnose":
            temp = tg_send_message(chat_id, "🩺 Running self-diagnostics across providers...")
            diag = run_system_diagnostics()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, diag, "")
            return True

        if clean in ("📊 Laptop Status", "💻 Laptop Status") or cmd in ("/laptop_status", "/status") or low in ("laptop status", "laptop info"):
            online = is_laptop_online()
            status = f"💻 *Laptop Status:* {'🟢 ONLINE (Connected)' if online else '🔴 OFFLINE'}"
            if online:
                try:
                    batt = laptop_battery()
                    if batt:
                        status += f"\n🔋 **Battery:** {batt}"
                except Exception:
                    pass
                try:
                    ip = execute_on_laptop("hostname -I | awk '{print $1}'")
                    if ip and ip.strip():
                        status += f"\n🌐 **Local IP:** `{ip.strip()}`"
                except Exception:
                    pass
                status += f"\n🎮 **Remote Control:** {'🟢 ENABLED' if _is_remote_active else '🔴 PAUSED (Self-Use)'}"
                status += f"\n⚡ **Auto-Approve:** {'🟢 ON' if _is_auto_approve_active else '🔴 OFF'}"
                status += f"\n🔒 **Screen Lock:** {'🔒 LOCKED' if _is_locked else '🔓 UNLOCKED'}"
            self.send_result(chat_id, status, "", menu="laptop")
            return True

        if clean in ("☁️ Cloud Status", "📊 Cloud Status", "📊 Cloud Telemetry"):
            res = system_status()
            self.send_result(chat_id, "☁️ *Cloud Server:*", f"```\n{res}\n```\n✅ 24/7 Live on Render")
            return True

        if clean in ("📁 Cloud Files", "📁 Workspace Files"):
            res = list_directory(".")
            self.send_result(chat_id, "📁 *Cloud Workspace Files:*", f"```\n{res}\n```")
            return True

        if clean in ("⚡ Cloud Quick Test", "/test"):
            out = execute_cloud_bash("uname -r && uptime -p && python3 --version")
            self.send_result(chat_id, "⚡ *Cloud Quick Diagnostic:*", f"```\n{out}\n```\n✅ Render cloud container responsive.")
            return True

        if clean in ("🧹 Reset AI Memory", "🧹 Reset History"):
            clear_history(f"tg_{chat_id}")
            self.send_result(chat_id, "🧹 *AI Memory Cleared!*", "Context reset ho gaya hai.")
            return True

        if clean == "💡 Help Guide" or cmd == "/help":
            self.send_result(chat_id, "", get_help_text())
            return True

        if clean == "🌐 24/7 Hosting Info":
            self.send_result(chat_id, "🌐 *Hosting Info:*",
                "Bot 24/7 Render Cloud par live hai.\nLaptop band hone par bhi bot chalega.\n"
                "Laptop control ke liye: `./start_laptop_node.sh`")
            return True

        return False

    def process_callback_query(self, cq: dict) -> None:
        """Handle interactive inline button clicks with multi-page navigation."""
        cq_id = cq.get("id")
        from_user = cq.get("from", {})
        user_id = from_user.get("id")
        username = from_user.get("username", "")
        message = cq.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        data = cq.get("data", "")

        if not chat_id or not user_id:
            return

        if not is_user_allowed(user_id, username=username):
            tg_answer_callback(cq_id, "⛔ Access Denied", show_alert=True)
            return

        global _is_auto_approve_active, _is_remote_active, _is_locked, _is_muted, _is_ghost_mode, _is_cctv_active

        # Mode Switchers (Laptop Mode vs Cloud Mode vs Home)
        if data == "mode_home":
            tg_edit_message(chat_id, message_id, get_home_text())
            tg_edit_reply_markup(chat_id, message_id, get_home_kb())
            tg_answer_callback(cq_id, "🏠 Main Hub")
            return
        elif data == "mode_laptop":
            tg_edit_message(chat_id, message_id, get_page_text(1))
            tg_edit_reply_markup(chat_id, message_id, get_page_kb(1))
            tg_answer_callback(cq_id, "💻 Laptop Mode")
            return
        elif data == "mode_cloud":
            tg_edit_message(chat_id, message_id, get_cloud_page_text())
            tg_edit_reply_markup(chat_id, message_id, get_cloud_kb())
            tg_answer_callback(cq_id, "☁️ Cloud Mode")
            return
        elif data == "btn_help":
            tg_answer_callback(cq_id, "💡 Help Guide")
            tg_send_message(chat_id, get_help_text())
            return
        elif data == "btn_cloud_status":
            res = system_status()
            self.send_result(chat_id, "☁️ *Cloud Status:*", f"```\n{res}\n```")
            tg_answer_callback(cq_id, "📊 Cloud status fetched")
            return
        elif data == "btn_cloud_files":
            files = list_directory(".")
            self.send_result(chat_id, "📁 *Cloud Workspace Files:*", f"```\n{files}\n```")
            tg_answer_callback(cq_id, "📁 Files listed")
            return
        elif data == "btn_cloud_test":
            out = execute_cloud_bash("uname -r && uptime -p && python3 --version")
            self.send_result(chat_id, "⚡ *Cloud Diagnostic:*", f"```\n{out}\n```")
            tg_answer_callback(cq_id, "⚡ Cloud tested")
            return
        elif data == "btn_hosting_info":
            info = (
                "🌐 *Render 24/7 Hosting Info*\n\n"
                "• Host: Render Cloud Platform\n"
                "• Status: 24/7 Always Active\n"
                "• Laptop band hone par bhi cloud bot online rehta hai.\n"
                "• Laptop connect karne ke liye: `./start_laptop_node.sh`"
            )
            self.send_result(chat_id, info, "")
            tg_answer_callback(cq_id, "🌐 Hosting info")
            return

        # Handle page navigation
        if data.startswith("page_"):
            page_num = int(data.split("_")[1])
            new_text = get_page_text(page_num)
            new_kb = get_page_kb(page_num)
            tg_edit_message(chat_id, message_id, new_text)
            tg_edit_reply_markup(chat_id, message_id, new_kb)
            tg_answer_callback(cq_id, f"📄 Page {page_num}/4")
            return

        # Page 1 Callbacks: Core Controls
        if data == "btn_screenshot":
            tg_answer_callback(cq_id, "📸 Capturing screenshot...")
            res = laptop_screenshot()
            self.send_result(chat_id, "📸 *Screenshot Captured*", res)
        elif data == "btn_webcam":
            tg_answer_callback(cq_id, "📷 Capturing webcam...")
            res = laptop_webcam()
            self.send_result(chat_id, "📷 *Webcam Photo Captured*", res)
        elif data == "btn_battery":
            batt = laptop_battery()
            tg_answer_callback(cq_id, f"🔋 Battery: {batt}", show_alert=True)
        elif data == "btn_status":
            tg_answer_callback(cq_id, "📊 Status fetched")
            tg_send_message(chat_id, get_status_text())
        elif data == "btn_auto_toggle":
            _is_auto_approve_active = not _is_auto_approve_active
            laptop_auto_toggle()
            tg_edit_message(chat_id, message_id, get_page_text(1))
            tg_edit_reply_markup(chat_id, message_id, get_page_kb(1))
            tg_answer_callback(cq_id, f"⚡ Auto: {'ON 🟢' if _is_auto_approve_active else 'OFF 🔴'}")
        elif data == "btn_remote_toggle":
            _is_remote_active = not _is_remote_active
            laptop_remote_toggle()
            tg_edit_message(chat_id, message_id, get_page_text(1))
            tg_edit_reply_markup(chat_id, message_id, get_page_kb(1))
            tg_answer_callback(cq_id, f"🎮 Remote: {'ON 🟢' if _is_remote_active else 'OFF 🔴'}")

        # Page 2 Callbacks: Media, Volume & Voice
        elif data == "btn_vol_up":
            execute_on_laptop("pactl set-sink-volume @DEFAULT_SINK@ +10%")
            tg_answer_callback(cq_id, "🔊 Volume: +10%")
        elif data == "btn_vol_down":
            execute_on_laptop("pactl set-sink-volume @DEFAULT_SINK@ -10%")
            tg_answer_callback(cq_id, "🔉 Volume: -10%")
        elif data == "btn_mute_toggle":
            _is_muted = not _is_muted
            laptop_mute()
            tg_edit_message(chat_id, message_id, get_page_text(2))
            tg_edit_reply_markup(chat_id, message_id, get_page_kb(2))
            tg_answer_callback(cq_id, f"🔇 Mute: {'ON 🟢' if _is_muted else 'OFF 🔴'}")
        elif data == "btn_mic10":
            tg_answer_callback(cq_id, "🎙️ Recording 10s audio...")
            res = laptop_mic(10)
            self.send_result(chat_id, "🎙️ *Audio Recorded*", res)
        elif data == "btn_video5":
            tg_answer_callback(cq_id, "🎥 Recording 5s video...")
            res = laptop_webcam_video()
            self.send_result(chat_id, "🎥 *5s Video Captured*", res)
        elif data == "btn_playpause":
            laptop_playpause()
            tg_answer_callback(cq_id, "🎵 Play/Pause toggled")

        # Page 3 Callbacks: Power, Security & Screen (All with instant in-place toggle)
        elif data == "btn_lock_toggle":
            _is_locked = not _is_locked
            laptop_lock_toggle()
            tg_edit_message(chat_id, message_id, get_page_text(3))
            tg_edit_reply_markup(chat_id, message_id, get_page_kb(3))
            tg_answer_callback(cq_id, f"🔒 Lock: {'ON 🟢' if _is_locked else 'OFF 🔴'}")
        elif data == "btn_sleep":
            tg_answer_callback(cq_id, "⚡ Sleeping laptop...", show_alert=True)
            laptop_power_sleep()
        elif data == "btn_ghost_mode":
            _is_ghost_mode = not _is_ghost_mode
            if _is_ghost_mode:
                laptop_ghost_mode()
            else:
                laptop_screen_on()
            tg_edit_message(chat_id, message_id, get_page_text(3))
            tg_edit_reply_markup(chat_id, message_id, get_page_kb(3))
            tg_answer_callback(cq_id, f"🕶️ Ghost: {'ON 🟢' if _is_ghost_mode else 'OFF 🔴'}")
        elif data == "btn_cctv_toggle":
            _is_cctv_active = not _is_cctv_active
            laptop_cctv_toggle()
            tg_edit_message(chat_id, message_id, get_page_text(3))
            tg_edit_reply_markup(chat_id, message_id, get_page_kb(3))
            tg_answer_callback(cq_id, f"👁️ CCTV: {'ON 🟢' if _is_cctv_active else 'OFF 🔴'}")
        elif data == "btn_alarm_toggle":
            _is_alarm_active = not _is_alarm_active
            if _is_alarm_active:
                laptop_alarm()
            else:
                laptop_stop_alarm()
            tg_edit_message(chat_id, message_id, get_page_text(3))
            tg_edit_reply_markup(chat_id, message_id, get_page_kb(3))
            tg_answer_callback(cq_id, f"🚨 Alarm: {'ON 🚨' if _is_alarm_active else 'OFF 🔴'}", show_alert=True)
        elif data == "btn_hotspot_toggle":
            _is_hotspot_active = not _is_hotspot_active
            if _is_hotspot_active:
                laptop_hotspot_start()
            else:
                laptop_hotspot_stop()
            tg_edit_message(chat_id, message_id, get_page_text(3))
            tg_edit_reply_markup(chat_id, message_id, get_page_kb(3))
            tg_answer_callback(cq_id, f"📡 Hotspot: {'ON 🟢' if _is_hotspot_active else 'OFF 🔴'}")

        # Page 4 Callbacks: Network, Files & Tools
        elif data == "btn_wifi":
            wifi = laptop_wifi()
            self.send_result(chat_id, "📶 *WiFi Status*", wifi)
            tg_answer_callback(cq_id, "📶 WiFi checked")
        elif data == "btn_location":
            loc = laptop_location()
            self.send_result(chat_id, "📍 *Laptop Location*", loc)
            tg_answer_callback(cq_id, "📍 Location checked")
        elif data == "btn_files":
            files = list_directory(".")
            self.send_result(chat_id, "📁 *Workspace Files*", f"```\n{files}\n```")
            tg_answer_callback(cq_id, "📁 Files listed")
        elif data == "btn_clip_read":
            clip = laptop_clipboard()
            self.send_result(chat_id, "📋 *Clipboard Content*", f"_{clip}_")
            tg_answer_callback(cq_id, "📋 Clipboard read")
        elif data == "btn_diagnose":
            tg_answer_callback(cq_id, "🩺 Running diagnostics...")
            diag = run_system_diagnostics()
            self.send_result(chat_id, diag, "")
        elif data == "btn_reset_memory":
            clear_history(f"tg_{chat_id}")
            tg_answer_callback(cq_id, "🧹 Memory cleared!", show_alert=True)
        else:
            tg_answer_callback(cq_id)

    def process_message(self, message: dict) -> None:
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        from_user = message.get("from", {})
        user_id = from_user.get("id")
        username = from_user.get("username", "")
        text = message.get("text", "").strip()
        msg_id = message.get("message_id")

        if not chat_id or not user_id:
            return

        if not is_user_allowed(user_id, username=username):
            logger.warning(f"Unauthorized: {user_id} (@{username})")
            tg_send_message(chat_id, "⛔ Access Denied - Locked to @kissbilla2")
            return

        # Instant smart contextual reaction feedback
        if msg_id:
            tg_react_smart(chat_id, msg_id, text)

        # 1. Custom / Paid Emoji Pack Import (detects full pack from a single emoji!)
        for entity in message.get("entities", []):
            if entity.get("type") == "custom_emoji":
                cid = entity.get("custom_emoji_id")
                offset = entity.get("offset", 0)
                length = entity.get("length", 1)
                char = text[offset:offset+length] if text and len(text) >= offset+length else "✨"
                if cid:
                    PREMIUM_CUSTOM_EMOJIS[char] = cid
                    try:
                        em_resp = requests.get(
                            f"{API_BASE}/getCustomEmojiStickers",
                            json={"custom_emoji_ids": [cid]},
                            timeout=10,
                        ).json()
                        if em_resp.get("ok") and em_resp.get("result"):
                            set_name = em_resp["result"][0].get("set_name")
                            if set_name:
                                pack_info = import_full_pack(set_name)
                                if pack_info:
                                    tg_send_message(
                                        chat_id,
                                        f"🎉 *Pura Paid Emoji Pack Copy Ho Gaya!*\n\n"
                                        f"> 📦 *Pack Name:* `{pack_info['title']}`\n"
                                        f"> 🏷️ *Set ID:* `{set_name}`\n"
                                        f"> ✨ *Total Emojis:* `{pack_info['count']}`\n\n"
                                        "Aapke is pack ke saare emojis bot ke sath link ho gaye hain!",
                                        reply_markup=get_bottom_reply_kb(chat_id),
                                    )
                                    return
                    except Exception as e:
                        logger.error(f"Error importing custom emoji pack: {e}")

        session_id = f"tg_{chat_id}"

        # 2. Sticker Pack Import (detects full pack from a single sticker!)
        if "sticker" in message:
            sticker = message["sticker"]
            file_id = sticker["file_id"]
            set_name = sticker.get("set_name")
            emoji = sticker.get("emoji", "🎨")
            _last_received_sticker[chat_id] = file_id
            if msg_id:
                tg_set_reaction(chat_id, msg_id, "🔥")

            pack_info = import_full_pack(set_name) if set_name else None
            if pack_info:
                tg_send_message(
                    chat_id,
                    f"🎉 *Pura Sticker Pack Copy Ho Gaya!*\n\n"
                    f"> 📦 *Pack:* `{pack_info['title']}`\n"
                    f"> 🏷️ *Set:* `{set_name}`\n"
                    f"> 🎨 *Total Stickers:* `{pack_info['count']}`\n\n"
                    "Ab is pack ke saare stickers bot me link ho chuke hain!",
                    reply_markup=get_bottom_reply_kb(chat_id),
                )
            else:
                tg_send_message(
                    chat_id,
                    f"🎨 *Sticker Received!* ({emoji})\n> File ID: `{file_id}`",
                    reply_markup=get_bottom_reply_kb(chat_id),
                )
            return

        # PHOTO handling
        if "photo" in message:
            if msg_id:
                tg_set_reaction(chat_id, msg_id, "👀")
            photo_list = message["photo"]
            file_id = photo_list[-1]["file_id"]
            caption = message.get("caption", "Is image ko analyze karein.")
            tg_send_chat_action(chat_id, "typing")
            status_id = tg_send_message(chat_id, "🔍 Analyzing photo...")
            img_bytes = download_telegram_file(file_id)
            if not img_bytes:
                tg_send_message(chat_id, "❌ Download failed")
                return
            try:
                result = self.agent.run_task(
                    session_id=session_id,
                    user_message=caption,
                    image_bytes=img_bytes,
                    image_mime="image/jpeg",
                )
                tg_delete_message(chat_id, status_id)
                current = _user_menu_state.get(chat_id, "main")
                tg_send_message(chat_id, result, reply_markup=get_kb_for(current, chat_id))
                maybe_send_sher_sticker(chat_id, chance=0.45)
            except Exception as e:
                tg_delete_message(chat_id, status_id)
                tg_send_message(chat_id, f"❌ Error: {e}")
            return

        # VOICE handling
        if "voice" in message:
            voice = message["voice"]
            file_id = voice["file_id"]
            tg_send_chat_action(chat_id, "typing")
            status_id = tg_send_message(chat_id, "🎙️ Transcribing voice...")
            audio_bytes = download_telegram_file(file_id)
            if audio_bytes:
                dest = UPLOADS_DIR / f"voice_{int(time.time())}.ogg"
                with open(dest, "wb") as f:
                    f.write(audio_bytes)
                try:
                    result = self.agent.run_task(
                        session_id=session_id,
                        user_message=f"User ne voice note bheji hai (saved: {dest}). Transcribe karein ya samjhein kya bola.",
                    )
                    tg_delete_message(chat_id, status_id)
                    current = _user_menu_state.get(chat_id, "main")
                    tg_send_message(chat_id, result, reply_markup=get_kb_for(current, chat_id))
                    maybe_send_sher_sticker(chat_id, chance=0.45)
                except Exception as e:
                    tg_delete_message(chat_id, status_id)
                    tg_send_message(chat_id, f"❌ Error: {e}")
            return

        # DOCUMENT handling
        if "document" in message:
            doc = message["document"]
            file_id = doc["file_id"]
            file_name = doc.get("file_name", f"file_{int(time.time())}")
            caption = message.get("caption", f"File uploaded: {file_name}")
            tg_send_chat_action(chat_id, "typing")
            status_id = tg_send_message(chat_id, f"📥 Downloading {file_name}...")
            doc_bytes = download_telegram_file(file_id)
            if not doc_bytes:
                tg_delete_message(chat_id, status_id)
                tg_send_message(chat_id, "❌ Download failed")
                return
            dest = UPLOADS_DIR / file_name
            with open(dest, "wb") as f:
                f.write(doc_bytes)
            prompt = f"File '{file_name}' saved at {dest}. Caption: {caption}"
            try:
                text_content = doc_bytes.decode("utf-8")
                if len(text_content) < 5000:
                    prompt += f"\nContent:\n```\n{text_content}\n```"
            except Exception:
                pass
            try:
                result = self.agent.run_task(session_id=session_id, user_message=prompt)
                tg_delete_message(chat_id, status_id)
                current = _user_menu_state.get(chat_id, "main")
                tg_send_message(chat_id, result, reply_markup=get_kb_for(current, chat_id))
                maybe_send_sher_sticker(chat_id, chance=0.45)
            except Exception as e:
                tg_delete_message(chat_id, status_id)
                tg_send_message(chat_id, f"❌ Error: {e}")
            return

        if not text:
            return

        # Handle buttons/commands
        if self.handle_button_or_command(chat_id, user_id, text):
            return

        # Fallback: Natural language → AI Agent with Real-time Animation
        tg_send_chat_action(chat_id, "typing")
        stop_anim = threading.Event()
        status_id = animate_jarvis_status(chat_id, stop_anim)
        try:
            result = self.agent.run_task(session_id=session_id, user_message=text)
            stop_anim.set()
            time.sleep(0.1)
            if status_id:
                tg_delete_message(chat_id, status_id)
            tg_send_message(chat_id, result, reply_markup=get_bottom_reply_kb(chat_id))
            maybe_send_sher_sticker(chat_id, chance=0.50)
        except Exception as e:
            stop_anim.set()
            logger.error(f"Agent error: {e}")
            if status_id:
                tg_delete_message(chat_id, status_id)
            tg_send_message(chat_id, f"❌ *Error:* {e}", reply_markup=get_bottom_reply_kb(chat_id))

    def start_polling(self) -> None:
        logger.info("Starting Telegram polling...")
        print("=" * 60)
        print("🤖 Hermes Telegram Bot RUNNING")
        print(f"📁 Workspace: {WORKSPACE_DIR}")
        print("=" * 60)
        error_delay = 1
        while True:
            try:
                resp = requests.get(
                    f"{API_BASE}/getUpdates",
                    params={"offset": self.offset, "timeout": 20},
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    error_delay = 1
                    for item in data.get("result", []):
                        self.offset = item["update_id"] + 1
                        if "callback_query" in item:
                            self.process_callback_query(item["callback_query"])
                        elif "message" in item:
                            self.process_message(item["message"])
                else:
                    time.sleep(error_delay)
                    error_delay = min(error_delay * 2, 30)
            except requests.exceptions.Timeout:
                # Normal long-polling timeout when idle (no new messages)
                continue
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error: {e}")
                time.sleep(error_delay)
                error_delay = min(error_delay * 2, 30)
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(2)


if __name__ == "__main__":
    runner = TelegramBotRunner()
    runner.start_polling()
