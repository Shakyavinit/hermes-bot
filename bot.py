"""
Hermes Telegram Bot Gateway
Connects Telegram Bot API to the autonomous AgentEngine.
Includes owner security lock, interactive buttons (Reply & Inline Keyboards),
callback query routing, live progress updates, multimodal image/screenshot analysis,
file/document upload support, background reminders, and robust polling.
"""

import http.server
import io
import json
import logging
import os
import platform
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
    get_pending_task,
    is_laptop_online,
    laptop_ai_status,
    laptop_alarm,
    laptop_apps,
    laptop_auto_always,
    laptop_auto_off,
    laptop_auto_on,
    laptop_auto_status,
    laptop_auto_toggle,
    laptop_battery,
    laptop_cctv_toggle,
    laptop_clean_photos,
    laptop_clipboard,
    laptop_ghost_mode,
    laptop_key_ctrlc,
    laptop_key_enter,
    laptop_key_n,
    laptop_key_num,
    laptop_key_y,
    laptop_location,
    laptop_lock,
    laptop_lock_toggle,
    laptop_unlock,
    laptop_mic,
    laptop_mute,
    laptop_open_url,
    laptop_play_music,
    laptop_playpause,
    laptop_popup,
    laptop_power_poweroff,
    laptop_power_reboot,
    laptop_power_sleep,
    laptop_remote_off,
    laptop_remote_on,
    laptop_remote_status,
    laptop_remote_toggle,
    laptop_screen_on,
    laptop_screenshot,
    laptop_speak,
    laptop_stop_alarm,
    laptop_stop_music,
    laptop_type,
    laptop_vol_down,
    laptop_vol_up,
    laptop_webcam,
    laptop_webcam_video,
    laptop_wifi,
    laptop_human_open_app,
    laptop_human_click,
    laptop_human_move,
    laptop_human_type,
    laptop_human_scroll,
    laptop_screen_inspect,
    laptop_screen_vision_click,
    laptop_offline_url,
    laptop_offline_qr,
    laptop_hotspot_start,
    laptop_hotspot_stop,
    laptop_hotspot_status,
    record_heartbeat,
    store_task_result,
)
from config import (
    BASE_DIR,
    TELEGRAM_BOT_TOKEN,
    WORKSPACE_DIR,
    get_runtime_config,
    is_user_allowed,
    set_owner,
)
from memory import clear_history, get_all_facts, save_fact
from tools import (
    execute_bash,
    execute_on_laptop,
    list_directory,
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
# Multi-Level Nested Bottom Reply Keyboards (Clean, Categorized & Extendable)
# ==============================================================================

# ==============================================================================
# Multi-Level Nested Bottom Reply Keyboards (Clean, Categorized & Extendable)
# ==============================================================================

# 1. Master Root Switcher (All-In-One Persistent Reply Keypad - Zero Hidden Menus)
ROOT_CHOICE_KEYBOARD = {
    "keyboard": [
        [{"text": "🔴 Self-Use Mode"}, {"text": "⚡ Auto Mode: OFF 🔴"}],
        [{"text": "🔒 Lock Screen"}, {"text": "📸 Screenshot"}],
        [{"text": "⭐ Best Option"}, {"text": "🟢 Send 'y'"}, {"text": "🔴 Send 'n'"}],
        [{"text": "✅ Approve (Enter)"}, {"text": "🛑 Ctrl+C"}],
        [{"text": "🔇 Mute"}, {"text": "🔋 Battery"}, {"text": "🌐 Offline Hub"}],
        [{"text": "🕶️ Ghost Mode"}, {"text": "☀️ Screen ON"}],
        [{"text": "📷 Selfie (Webcam)"}, {"text": "🚨 Siren Alarm"}],
        [{"text": "🎥 Video (10s)"}, {"text": "🎙️ Mic (10s)"}],
        [{"text": "📡 Start Hotspot"}, {"text": "💤 Sleep Laptop"}],
        [{"text": "☁️ Cloud Server"}, {"text": "🔄 Refresh Panel"}],
    ],
    "resize_keyboard": True,
    "is_persistent": True,
}

# All keyboards strictly point to the Master Root Keypad (No hidden sub-menus, no categories)
REPLY_KEYBOARD = ROOT_CHOICE_KEYBOARD
LAPTOP_DASHBOARD_KEYBOARD = ROOT_CHOICE_KEYBOARD
MAIN_DASHBOARD_KEYBOARD = ROOT_CHOICE_KEYBOARD
CLOUD_DASHBOARD_KEYBOARD = ROOT_CHOICE_KEYBOARD
SPY_REPLY_KEYBOARD = ROOT_CHOICE_KEYBOARD
AI_REPLY_KEYBOARD = ROOT_CHOICE_KEYBOARD
MEDIA_REPLY_KEYBOARD = ROOT_CHOICE_KEYBOARD
VOLUME_REPLY_KEYBOARD = ROOT_CHOICE_KEYBOARD
POWER_REPLY_KEYBOARD = ROOT_CHOICE_KEYBOARD
LAPTOP_EXTRA_KEYBOARD = ROOT_CHOICE_KEYBOARD
NEXT_SECTION_KEYBOARD = ROOT_CHOICE_KEYBOARD
TOOLS_REPLY_KEYBOARD = ROOT_CHOICE_KEYBOARD
HUMAN_GUI_KEYBOARD = ROOT_CHOICE_KEYBOARD
ALARM_REPLY_KEYBOARD = ROOT_CHOICE_KEYBOARD


_is_remote_active = True
_is_locked = False
_is_muted = False
_is_auto_approve_active = False
_is_cctv_active = False


def update_dynamic_keyboards(remote_active: Optional[bool] = None) -> None:
    """Synchronize persistent reply keyboard button labels dynamically across all menus."""
    global _is_remote_active, _is_auto_approve_active, _is_locked, _is_muted, _is_cctv_active
    if remote_active is not None:
        _is_remote_active = remote_active

    mode_btn_text = "🔴 Self-Use Mode" if _is_remote_active else "🟢 Remote Mode"
    auto_btn_text = "⚡ Auto Mode: ON 🟢" if _is_auto_approve_active else "⚡ Auto Mode: OFF 🔴"
    lock_btn_text = "🔓 Unlock Screen" if _is_locked else "🔒 Lock Screen"
    mute_btn_text = "🔊 Unmute" if _is_muted else "🔇 Mute"
    cctv_btn_text = "🛑 Stop CCTV" if _is_cctv_active else "👁️ CCTV Mode"

    for kb in (
        ROOT_CHOICE_KEYBOARD,
        LAPTOP_DASHBOARD_KEYBOARD,
        AI_REPLY_KEYBOARD,
        POWER_REPLY_KEYBOARD,
        HUMAN_GUI_KEYBOARD,
        SPY_REPLY_KEYBOARD,
        LAPTOP_EXTRA_KEYBOARD,
        MEDIA_REPLY_KEYBOARD,
        ALARM_REPLY_KEYBOARD,
    ):
        try:
            for row in kb.get("keyboard", []):
                for btn in row:
                    txt = btn.get("text", "")
                    if txt in (
                        "🔴 Self-Use Mode",
                        "🟢 Remote Mode",
                        "🔴 Self-Use Mode (Pause)",
                        "🟢 Remote Mode (Activate)",
                    ):
                        btn["text"] = mode_btn_text
                    elif txt in (
                        "⚡ Auto Mode (Toggle)",
                        "⚡ Auto Mode: OFF 🔴",
                        "⚡ Auto Mode: ON 🟢",
                        "⚡ Auto: ON 🟢",
                        "⚡ Auto: OFF 🔴",
                    ):
                        btn["text"] = auto_btn_text
                    elif txt in ("🔒 Lock Screen", "🔓 Unlock Screen"):
                        btn["text"] = lock_btn_text
                    elif txt in ("🔇 Mute", "🔊 Unmute"):
                        btn["text"] = mute_btn_text
                    elif txt in ("👁️ CCTV Mode", "🛑 Stop CCTV", "👁️ CCTV Motion Alert"):
                        btn["text"] = cctv_btn_text
        except Exception:
            pass


def get_laptop_control_keyboard() -> dict:
    """Full remote control keypad for physical laptop with dynamic dual-state toggle buttons."""
    global _is_remote_active, _is_locked, _is_muted, _is_auto_approve_active, _is_cctv_active

    remote_btn = "🔴 Self-Use Mode (Pause)" if _is_remote_active else "🟢 Remote Mode (Activate)"
    auto_btn = "⚡ Auto: ON 🟢" if _is_auto_approve_active else "⚡ Auto: OFF 🔴"
    lock_btn = "🔓 Unlock Screen" if _is_locked else "🔒 Lock Screen"
    mute_btn = "🔊 Unmute" if _is_muted else "🔇 Mute"
    cctv_btn = "🛑 Stop CCTV" if _is_cctv_active else "👁️ CCTV Motion"

    return {
        "inline_keyboard": [
            [
                {"text": remote_btn, "callback_data": "lap_toggle_remote"},
                {"text": auto_btn, "callback_data": "lap_auto_toggle"},
            ],
            [
                {"text": "🌐 Offline Mobile Hub (Bina Net)", "callback_data": "lap_offline_hub"},
            ],
            [
                {"text": "📸 Live Screenshot", "callback_data": "lap_screenshot"},
                {"text": "📷 Front Webcam", "callback_data": "lap_webcam"},
            ],
            [
                {"text": "🎥 Video Clip (10s)", "callback_data": "lap_video"},
                {"text": cctv_btn, "callback_data": "lap_cctv"},
            ],
            [
                {"text": "🚨 Siren Alarm", "callback_data": "lap_alarm"},
                {"text": "📍 Find My Laptop", "callback_data": "lap_location"},
            ],
            [
                {"text": "🤖 AI & Sandbox Keys", "callback_data": "lap_coder_menu"},
                {"text": "🧹 Clean Photos", "callback_data": "lap_clean_photos"},
            ],
            [
                {"text": "🎙️ Record Mic (10s)", "callback_data": "lap_mic"},
                {"text": "⏹️ Stop Music", "callback_data": "lap_stop_music"},
            ],
            [
                {"text": "🔋 Battery Status", "callback_data": "lap_battery"},
                {"text": "📶 Wi-Fi Status", "callback_data": "lap_wifi"},
            ],
            [
                {"text": "🔉 Vol -", "callback_data": "lap_vol_down"},
                {"text": "🔊 Vol +", "callback_data": "lap_vol_up"},
                {"text": mute_btn, "callback_data": "lap_mute"},
                {"text": "⏯️ Play/Pause", "callback_data": "lap_playpause"},
            ],
            [
                {"text": "📋 Clipboard", "callback_data": "lap_clipboard"},
                {"text": "⚡ Power Menu", "callback_data": "lap_power_menu"},
            ],
            [
                {"text": "📱 Running Apps", "callback_data": "lap_apps"},
                {"text": lock_btn, "callback_data": "lap_lock_toggle"},
            ],
            [
                {"text": "🔙 Back to Main Menu", "callback_data": "btn_status"},
            ],
        ]
    }


def get_coder_keyboard() -> dict:
    """Keypad for remote terminal and sandbox approvals with Best Option highlighted and Auto-Approve."""
    return {
        "inline_keyboard": [
            [
                {"text": "⭐ (Best Option) Approve & Run", "callback_data": "lap_key_enter"},
            ],
            [
                {"text": "⚡ Turn ON Auto-Approve", "callback_data": "lap_auto_on"},
                {"text": "🔄 Toggle Auto Mode", "callback_data": "lap_auto_toggle"},
            ],
            [
                {"text": "🟢 Always Allow ('y')", "callback_data": "lap_key_y"},
                {"text": "🔴 Deny / Skip ('n')", "callback_data": "lap_key_n"},
            ],
            [
                {"text": "1️⃣ Choice 1", "callback_data": "lap_key_1"},
                {"text": "2️⃣ Choice 2", "callback_data": "lap_key_2"},
                {"text": "3️⃣ Choice 3", "callback_data": "lap_key_3"},
            ],
            [
                {"text": "🛑 Cancel (Ctrl+C)", "callback_data": "lap_key_ctrlc"},
                {"text": "📸 Screen Peek", "callback_data": "lap_screenshot"},
            ],
            [
                {"text": "🔙 Back to Laptop Controls", "callback_data": "lap_controls"},
            ],
        ]
    }


def get_power_keyboard() -> dict:
    """Power management keypad."""
    return {
        "inline_keyboard": [
            [
                {"text": "🕶️ Ghost Mode (Screen OFF)", "callback_data": "lap_ghost"},
                {"text": "☀️ Screen ON", "callback_data": "lap_screen_on"},
            ],
            [
                {"text": "💤 Sleep Laptop", "callback_data": "lap_power_sleep"},
            ],
            [
                {"text": "🔄 Restart Laptop", "callback_data": "lap_power_reboot"},
            ],
            [
                {"text": "⛔ Shutdown Laptop", "callback_data": "lap_power_poweroff"},
            ],
            [
                {"text": "🔙 Back to Laptop Controls", "callback_data": "lap_controls"},
            ],
        ]
    }


def get_main_inline_keyboard(remote_active: Optional[bool] = None) -> dict:
    """Inline Keyboard with interactive buttons, including Master Remote Mode Switch."""
    global _is_remote_active
    active = _is_remote_active if remote_active is None else remote_active
    btn_text = "🔴 Self-Use Mode (Pause Remote)" if active else "🟢 Remote Mode (Activate Remote)"
    return {
        "inline_keyboard": [
            [
                {"text": btn_text, "callback_data": "lap_toggle_remote"},
            ],
            [
                {"text": "🎛️ Live Laptop Controls", "callback_data": "lap_controls"},
                {"text": "🌐 Offline Mobile Hub", "callback_data": "lap_offline_hub"},
            ],
            [
                {"text": "📸 Live Screenshot", "callback_data": "lap_screenshot"},
                {"text": "💻 Test Laptop", "callback_data": "btn_laptop"},
            ],
            [
                {"text": "☁️ Test Cloud Server", "callback_data": "btn_cloud"},
                {"text": "📊 Full Status", "callback_data": "btn_status"},
            ],
            [
                {"text": "📁 Workspace Files", "callback_data": "btn_files"},
                {"text": "⚡ Quick Diagnostics", "callback_data": "btn_test"},
            ],
            [
                {"text": "🧹 Clear Memory", "callback_data": "btn_reset"},
            ],
        ]
    }


def download_telegram_file(file_id: str) -> Optional[bytes]:
    """Download a file/photo/doc from Telegram Bot API using file_id."""
    try:
        url = f"{API_BASE}/getFile"
        resp = requests.get(url, params={"file_id": file_id}, timeout=15)
        res = resp.json()
        if res.get("ok"):
            file_path = res["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            down_resp = requests.get(file_url, timeout=35)
            if down_resp.status_code == 200:
                return down_resp.content
    except Exception as e:
        logger.error(f"Error downloading Telegram file {file_id}: {e}")
    return None


def schedule_reminder(chat_id: int, delay_seconds: int, reminder_text: str) -> None:
    """Schedule a reminder message to be sent asynchronously."""
    def send_later():
        tg_send_message(
            chat_id,
            f"⏰ *Reminder:*\n{reminder_text}",
            reply_markup=REPLY_KEYBOARD,
        )

    timer = threading.Timer(delay_seconds, send_later)
    timer.daemon = True
    timer.start()


# In-memory tracking for chat message cleanup & smooth navigation
_last_nav_msg: Dict[int, int] = {}
_recent_bot_msgs: Dict[int, List[int]] = {}
_user_active_keyboard: Dict[int, dict] = {}


def track_bot_msg(chat_id: int, msg_id: Optional[int]) -> None:
    """Keep history of bot messages in chat for auto-cleaning."""
    if not msg_id:
        return
    if chat_id not in _recent_bot_msgs:
        _recent_bot_msgs[chat_id] = []
    _recent_bot_msgs[chat_id].append(msg_id)
    if len(_recent_bot_msgs[chat_id]) > 35:
        _recent_bot_msgs[chat_id] = _recent_bot_msgs[chat_id][-35:]


def tg_delete_message(chat_id: int, message_id: Optional[int]) -> bool:
    """Delete a Telegram message to keep chat completely clean and clutter-free."""
    if not chat_id or not message_id:
        return False
    url = f"{API_BASE}/deleteMessage"
    try:
        resp = requests.post(
            url, json={"chat_id": chat_id, "message_id": message_id}, timeout=8
        )
        return resp.status_code == 200 and resp.json().get("ok", False)
    except Exception as e:
        logger.debug(f"Could not delete message {message_id}: {e}")
        return False


def tg_send_message(
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = "Markdown",
    reply_markup: Optional[dict] = None,
) -> Optional[int]:
    """Send text message to Telegram chat with optional inline/reply buttons."""
    url = f"{API_BASE}/sendMessage"

    if len(text) > 4000:
        if len(text) > 8000:
            tg_send_document(
                chat_id,
                text.encode("utf-8"),
                filename="output.txt",
                caption="📄 Output was long; sent as document.",
            )
            text = text[:800] + "\n\n...(Full output attached as document above)..."

    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
        if "keyboard" in reply_markup:
            _user_active_keyboard[chat_id] = reply_markup

    try:
        resp = requests.post(url, json=payload, timeout=20)
        res_json = resp.json()
        if res_json.get("ok"):
            msg_id = res_json.get("result", {}).get("message_id")
            if msg_id:
                try:
                    track_and_clean_messages(chat_id, bot_msg_id=msg_id)
                except Exception:
                    pass
            track_bot_msg(chat_id, msg_id)
            return msg_id
        else:
            payload.pop("parse_mode", None)
            resp2 = requests.post(url, json=payload, timeout=20)
            if resp2.json().get("ok"):
                msg_id = resp2.json().get("result", {}).get("message_id")
                if msg_id:
                    try:
                        track_and_clean_messages(chat_id, bot_msg_id=msg_id)
                    except Exception:
                        pass
                track_bot_msg(chat_id, msg_id)
                return msg_id
            logger.error(f"Failed to send message: {resp.text}")
    except Exception as e:
        logger.error(f"Error in tg_send_message: {e}")
    return None


def tg_edit_message(
    chat_id: int,
    message_id: int,
    new_text: str,
    reply_markup: Optional[dict] = None,
) -> bool:
    """Edit an existing Telegram message (used for live progress updates)."""
    url = f"{API_BASE}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": new_text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200 and resp.json().get("ok", False)
    except Exception as e:
        logger.debug(f"Could not edit message: {e}")
        return False


def tg_edit_reply_markup(
    chat_id: int,
    message_id: int,
    reply_markup: dict,
) -> bool:
    """Edit only the inline keyboard of an existing message in-place without touching text."""
    url = f"{API_BASE}/editMessageReplyMarkup"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": reply_markup,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200 and resp.json().get("ok", False)
    except Exception as e:
        logger.debug(f"Could not edit reply markup: {e}")
        return False


def send_or_replace_nav(chat_id: int, text: str, reply_markup: dict) -> Optional[int]:
    """
    Update or replace active navigation menu message, deleting the previous
    navigation card so the chat doesn't get flooded with duplicate menus.
    """
    old_msg_id = _last_nav_msg.get(chat_id)
    if old_msg_id:
        tg_delete_message(chat_id, old_msg_id)

    new_msg_id = tg_send_message(chat_id, text, reply_markup=reply_markup)
    if new_msg_id:
        _last_nav_msg[chat_id] = new_msg_id
    return new_msg_id


def tg_answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> None:
    """Acknowledge an inline keyboard callback query."""
    url = f"{API_BASE}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id, "show_alert": show_alert}
    if text:
        payload["text"] = text
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Error answering callback query: {e}")


def tg_send_chat_action(chat_id: int, action: str = "typing") -> None:
    """Send typing indicator."""
    url = f"{API_BASE}/sendChatAction"
    try:
        requests.post(url, json={"chat_id": chat_id, "action": action}, timeout=5)
    except Exception:
        pass


def tg_send_document(
    chat_id: int, file_bytes: bytes, filename: str, caption: str = ""
) -> None:
    """Send a file/document to the chat."""
    url = f"{API_BASE}/sendDocument"
    files = {"document": (filename, io.BytesIO(file_bytes))}
    data = {"chat_id": chat_id, "caption": caption}
    try:
        requests.post(url, data=data, files=files, timeout=30)
    except Exception as e:
        logger.error(f"Error sending document: {e}")


def sync_bot_commands() -> None:
    """Update Telegram bot command list visible in chat menu."""
    commands = [
        {"command": "self", "description": "🔴 Self-Use Mode (Pause / Resume Remote)"},
        {"command": "menu", "description": "📱 Interactive Control Panel & Buttons"},
        {"command": "laptop", "description": "💻 Laptop Controls Dashboard"},
        {"command": "offline", "description": "🌐 Offline Mobile Web Hub (Bina Net)"},
        {"command": "status", "description": "📊 Host Health & AI Model Status"},
        {"command": "files", "description": "📁 Workspace Files Browser"},
        {"command": "remind", "description": "⏰ Set a Timer / Reminder (e.g. 5m)"},
        {"command": "reset", "description": "🧹 Clear Chat Conversation History"},
        {"command": "help", "description": "💡 Quick Guide & Commands"},
    ]
    try:
        requests.post(f"{API_BASE}/setMyCommands", json={"commands": commands}, timeout=10)
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")


def get_status_text() -> str:
    sys_stat = system_status()
    cfg = get_runtime_config()
    facts = get_all_facts()
    laptop_status = "ONLINE 🟢 (Ready for local tasks)" if is_laptop_online() else "OFFLINE 🔴 (Laptop band hai)"
    return (
        "📊 *Hermes System Status:*\n\n"
        f"```\n{sys_stat}\n```\n"
        f"• **Owner:** @{cfg.get('owner_username', 'kissbilla2')} (`{cfg.get('owner_user_id')}`)\n"
        f"• **💻 Laptop Node:** {laptop_status}\n"
        f"• **☁️ Cloud Host:** Render Cloud (ONLINE 24/7 🟢)\n"
        f"• **AI Model:** Google Gemini (`gemini-flash-lite-latest`)\n"
        f"• **Saved Memory Facts:** {len(facts)}"
    )


def get_cloud_status_text() -> str:
    sys_stat = system_status()
    cfg = get_runtime_config()
    facts = get_all_facts()
    return (
        "☁️ *Hermes 24/7 Cloud Server Status:*\n\n"
        f"```\n{sys_stat}\n```\n"
        f"• **Cloud Platform:** Render Cloud Container (24/7 Live)\n"
        f"• **Owner:** @{cfg.get('owner_username', 'kissbilla2')} (`{cfg.get('owner_user_id')}`)\n"
        f"• **AI Engine:** Google Gemini Flash Lite\n"
        f"• **Saved Memory Facts:** {len(facts)}\n"
        "• **Cloud Services:** All systems operational 🟢"
    )


def get_laptop_status_text() -> str:
    online = is_laptop_online()
    status_emoji = "ONLINE 🟢" if online else "OFFLINE 🔴"
    if online:
        bat = laptop_battery()
        return (
            f"💻 *Physical Laptop Status ({status_emoji}):*\n\n"
            f"• **Connection:** Connected via Secure Bridge 🟢\n"
            f"• **OS:** Kali Linux (GNOME Wayland)\n"
            f"• **Battery:** {bat}\n"
            f"• **Webcam & Mic:** Ready\n"
            f"• **Antigravity Watcher:** Active & Monitoring\n"
            f"• **CCTV & Intruder Trap:** Standby"
        )
    else:
        return (
            f"💻 *Physical Laptop Status ({status_emoji}):*\n\n"
            "Laptop abhi offline hai ya bridge service stop hai.\n\n"
            "Chalu karne ke liye laptop par chalaein:\n"
            "`systemctl --user start hermes-laptop.service`\n"
            "ya `./start_laptop_node.sh`"
        )


def get_files_text() -> str:
    res = list_directory(".")
    return f"📁 *Workspace Directory:*\n```\n{res}\n```"


def get_quick_test_text() -> str:
    out = execute_bash("uname -r && uptime -p && python3 --version")
    return f"⚡ *Quick Host Diagnostic:*\n```\n{out}\n```\n✅ Host terminal responsive."


def get_vps_guide_text() -> str:
    return (
        "🌐 *24/7 Free Hosting Guide (Laptop band hone par bhi bot chalega):*\n\n"
        "1. **Render (Active & Live):**\n"
        "   - Bot 24/7 Render cloud par live hai.\n"
        "2. **Laptop Bridge:**\n"
        "   - Laptop par `./start_laptop_node.sh` chalu rakhein to Telegram se direct laptop bhi control hoga."
    )


def get_help_text() -> str:
    return (
        "🛠️ *Hermes AI Assistant Guide:*\n\n"
        "• **Laptop Control:** `laptop: run ls` ya `laptop par python script chalao`.\n"
        "• **Buttons:** Niche diye buttons se quick status, files, test chalaein.\n"
        "• **Photos/Screenshots:** Koi bhi photo ya error screenshot bhejein, AI analyze karega.\n"
        "• **Files/Docs:** Koi bhi Python script ya file bhejein, AI check ya run karega.\n"
        "• **Reminders:** `/remind 10m check server`\n\n"
        "Strictly locked to @kissbilla2."
    )


def start_health_server(port: int = 7860) -> None:
    """Run lightweight HTTP health-check and Laptop Bridge server."""
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed.query)

            if "remote_enabled" in query_params:
                val = query_params["remote_enabled"][0]
                update_dynamic_keyboards(val == "1")

            if "auto_approve" in query_params:
                val = query_params["auto_approve"][0]
                global _is_auto_approve_active
                _is_auto_approve_active = (val == "1")
                update_dynamic_keyboards()

            if parsed.path == "/api/laptop/poll":
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
            self.wfile.write(b"OK - Hermes Telegram Bot is running 24/7.")

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
                    self.send_header("Content-type", "application/json")
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
            return  # Suppress logging spam

    port = int(os.getenv("PORT", port))
    try:
        server = socketserver.TCPServer(("0.0.0.0", port), HealthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Health-check & Laptop Bridge HTTP server online on port {port}")
    except Exception as e:
        logger.warning(f"Could not bind server on port {port}: {e}")


class TelegramBotRunner:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is missing in .env!")
        self.agent = AgentEngine()
        self.offset = 0
        sync_bot_commands()
        start_health_server()

    def handle_command_or_button(
        self, chat_id: int, user_id: int, text: str
    ) -> bool:
        """Handle slash commands and persistent reply button clicks with nested menus and clean transitions."""
        global _is_remote_active
        clean = text.strip()
        clean_lower = clean.lower()
        cmd = clean.split()[0].lower() if clean else ""

        # ======================================================================
        # 1. Main Root Switcher (/start, /menu, "🔙 Main Menu")
        # ======================================================================
        if cmd in ("/start", "/menu") or clean in (
            "📱 Menu",
            "🔙 Main Menu",
            "🔙 Back to Main Menu",
        ):
            cfg = get_runtime_config()
            is_new_owner = False
            if cfg.get("owner_user_id") is None:
                set_owner(user_id)
                is_new_owner = True

            update_dynamic_keyboards()
            laptop_status = "ONLINE 🟢" if is_laptop_online() else "OFFLINE 🔴"
            remote_status = "🔴 Self-Use (PAUSED)" if not _is_remote_active else "🟢 Remote Control ACTIVE"
            auto_status = "🟢 ON" if _is_auto_approve_active else "🔴 OFF"

            welcome = (
                "👑 *Hermes Autonomous Agent Panel*\n\n"
                f"{'✅ Registered as Primary Owner.' if is_new_owner else '⚡ System Ready & Active.'}\n"
                f"• 💻 **Laptop Node:** {laptop_status}\n"
                f"• 🎮 **Control State:** {remote_status}\n"
                f"• ⚡ **Auto-Approve:** {auto_status}\n"
                "• ☁️ **Cloud Host:** ONLINE 24/7 🟢\n\n"
                "Sabhi main controls niche mobile keypad par available hain:"
            )
            _user_active_keyboard[chat_id] = ROOT_CHOICE_KEYBOARD
            send_or_replace_nav(
                chat_id,
                welcome,
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
            return True

        # Refresh Panel & Sync
        if clean in ("🔄 Refresh Panel", "/refresh", "/sync") or clean_lower in ("refresh", "sync", "refresh panel", "panel refresh"):
            update_dynamic_keyboards()
            laptop_status = "ONLINE 🟢" if is_laptop_online() else "OFFLINE 🔴"
            remote_status = "🔴 Self-Use (PAUSED)" if not _is_remote_active else "🟢 Remote Control ACTIVE"
            auto_status = "🟢 ON" if _is_auto_approve_active else "🔴 OFF"
            lock_status = "🔒 LOCKED" if _is_locked else "🔓 UNLOCKED"
            mute_status = "🔇 MUTED" if _is_muted else "🔊 UNMUTED"
            msg = (
                "🔄 *Hermes Bottom Panel Refreshed!*\n\n"
                f"• 💻 **Laptop Node:** {laptop_status}\n"
                f"• 🎮 **Control State:** {remote_status}\n"
                f"• ⚡ **Auto-Approve:** {auto_status}\n"
                f"• 🔒 **Screen Lock:** {lock_status}\n"
                f"• 🔊 **Sound State:** {mute_status}\n\n"
                "Niche diye buttons se direct command dein:"
            )
            _user_active_keyboard[chat_id] = ROOT_CHOICE_KEYBOARD
            send_or_replace_nav(chat_id, msg, reply_markup=ROOT_CHOICE_KEYBOARD)
            return True

        # ======================================================================
        # 2. Dual-Mode Switchers & Legacy Sub-menus (All Flattened to Master Keypad)
        # ======================================================================
        if clean in (
            "💻 More Tools ➡️",
            "💻 Laptop Dashboard ➡️",
            "💻 More Laptop Controls ➡️",
            "💻 Laptop Mode",
            "💻 Laptop Exec",
            "💻 Laptop",
            "🔙 Laptop Menu",
            "🔙 Back to Laptop",
            "/laptop",
            "🛡️ Spy & Security",
            "/spy",
            "/security",
            "🤖 Sandbox & AI",
            "🤖 AI & Terminal",
            "🤖 AI & Coding",
            "🤖 Sandbox",
            "/sandbox",
            "/coder",
            "🎵 Media & Sound",
            "🔊 Volume & Media",
            "/volume",
            "⚡ Power & Ghost Mode",
            "⚡ System & Power",
            "⚡ Power & Lock",
            "/power",
            "🌟 Extra Tools ➡️",
            "🌟 Next Section ➡️",
            "/next",
            "/more",
            "⬅️ Previous Section",
        ) or clean_lower in (
            "laptop", "laptop mode", "laptop exec", "laptop panel", "/laptop", "more tools",
            "send box", "sendbox", "sandbox", "sandbox & ai", "spy", "security",
            "power", "power mode", "ghost mode", "volume", "sound", "extra tools"
        ):
            update_dynamic_keyboards()
            laptop_status = "ONLINE 🟢 (Connected)" if is_laptop_online() else "OFFLINE 🔴 (Not connected)"
            text = (
                f"📱 *Hermes All-In-One Control Panel* ({laptop_status})\n\n"
                "Sabhi specific controls bahar screen ke niche persistent keypad par open hain.\n"
                "Koi category ya sub-menu nahi hai — seedhe niche se direct action lein:"
            )
            _user_active_keyboard[chat_id] = ROOT_CHOICE_KEYBOARD
            send_or_replace_nav(
                chat_id,
                text,
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
            return True

        if clean in (
            "☁️ Cloud Server",
            "☁️ Cloud Mode",
            "☁️ Cloud",
            "/cloud",
        ) or clean_lower in ("cloud", "clode", "cloud server", "cloud mode", "cloud bot", "/cloud"):
            text = (
                "☁️ *Cloud Server Panel (Render 24/7)*\n\n"
                "Bot Render Cloud container par 24/7 live hai.\n"
                "Laptop band hone par bhi bot yahan se active rehta hai.\n\n"
                "Sabhi actions niche master keypad par available hain:"
            )
            _user_active_keyboard[chat_id] = ROOT_CHOICE_KEYBOARD
            send_or_replace_nav(
                chat_id,
                text,
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
            return True

        # Category: Human Screen & Mouse GUI (Laptop)
        if clean in ("🖱️ Human Screen & Mouse", "🖱️ Human GUI", "/gui", "/mouse"):
            send_or_replace_nav(
                chat_id,
                "🖱️ *Human Screen & Mouse Controls:*\n"
                "Hermes screen par bilkul real human ki tarha mouse operate karta hai aur AI Vision se sab samajhta hai!\n\n"
                "• 🚀 `Open App (Human)`: `/openapp <name>` (e.g. Chrome, VS Code, Settings)\n"
                "• 👁️ `Screen Vision`: Screen par kya khula hai AI se dekhein\n"
                "• 🎯 `Click Element`: `/click <element>` (AI dhundh kar mouse se click karega)\n"
                "• ⌨️ `Human Typing`: `/htype <text>` (real human speed se type karega)\n"
                "• 📜 `Scroll Down`: Mouse wheel scroll",
                reply_markup=HUMAN_GUI_KEYBOARD,
            )
            return True

        # Category 6: Files & Diagnostics (Cloud)
        if clean in ("📁 Files & Tools", "/tools"):
            send_or_replace_nav(
                chat_id,
                "📁 *Files & Diagnostics Tools:*\nWorkspace files, test diagnostics aur chat cleaner niche se access karein:",
                reply_markup=CLOUD_DASHBOARD_KEYBOARD,
            )
            return True

        # ======================================================================
        # 3. Chat Clean-Up Command
        # ======================================================================
        if clean in ("🗑️ Clean Messages", "/clean", "/cleanchat") or clean_lower in ("clean", "cleanchat", "clean messages"):
            count = 0
            for mid in _recent_bot_msgs.get(chat_id, []):
                if tg_delete_message(chat_id, mid):
                    count += 1
            _recent_bot_msgs[chat_id] = []
            photo_clean_res = laptop_clean_photos()
            send_or_replace_nav(
                chat_id,
                f"🧹 *Chat & Media Cleaned Up!*\n\n"
                f"📋 *Short Summary:* {count} bot messages saf ho gaye aur {photo_clean_res.lower()}",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
            return True

        # ======================================================================
        # 4. Spy & Security Actions
        # ======================================================================
        if clean in ("📷 Selfie (Webcam)", "📷 Webcam", "/webcam") or clean_lower in ("photo", "selfie", "webcam", "camera", "webcam photo", "camera photo"):
            temp_id = tg_send_message(chat_id, "📷 Front camera photo capture ho rahi hai...")
            res = laptop_webcam()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                "📷 *Webcam Snapshot Completed!*\n\n"
                "📋 *Short Summary:* Front camera photo send ho gayi hai (purani images auto-clean ho gayi).",
                reply_markup=active_kb,
            )
            return True

        if clean in ("🎥 Video (10s)", "🎥 Video Clip (10s)", "/video", "/webcamvideo") or clean_lower in ("video", "video clip", "clip", "webcam video", "10s video"):
            temp_id = tg_send_message(chat_id, "🎥 10-second webcam video + audio recording chalu hai...")
            res = laptop_webcam_video()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                "🎥 *Webcam Video Completed!*\n\n"
                "📋 *Short Summary:* 10s video clip send ho gayi hai.",
                reply_markup=active_kb,
            )
            return True

        if clean in ("🎙️ Mic (10s)", "🎙️ Mic Record (10s)", "/mic", "/record") or clean_lower in ("mic", "record", "audio", "voice", "voice note", "mic record"):
            temp_id = tg_send_message(chat_id, "🎙️ 10-second laptop mic audio recording chalu hai...")
            res = laptop_mic(10)
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                "🎙️ *Audio Recording Completed!*\n\n"
                "📋 *Short Summary:* 10s voice note send ho gaya hai.",
                reply_markup=active_kb,
            )
            return True

        if clean in ("👁️ CCTV Mode", "👁️ CCTV Motion Alert", "/cctv") or clean_lower in ("cctv", "cctv mode", "cctv alert", "motion alert"):
            res = laptop_cctv_toggle()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("🚨 Siren Alarm", "/alarm", "/siren") or clean_lower in ("alarm", "siren"):
            res = laptop_alarm()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("⏹️ Stop Alarm", "/stopalarm") or clean_lower in ("stop alarm", "alarm stop", "stop siren"):
            res = laptop_stop_alarm()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("📍 Find Laptop", "📍 Find My Laptop", "/locate", "/find", "/location") or clean_lower in ("location", "locate", "find laptop", "find my laptop", "where is laptop"):
            temp_id = tg_send_message(chat_id, "📍 Fetching laptop live location...")
            res = laptop_location()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        # ======================================================================
        # 4a. Hermes Offline Mobile Hub (Zero Internet Control)
        # ======================================================================
        if clean in ("🌐 Offline Hub", "🌐 Offline Hub Link", "📱 Offline Hub QR", "/offline", "/hub", "/wifi_hub") or clean_lower in ("offline", "offline hub", "offline link", "bina net", "offline qr"):
            qr_res = laptop_offline_qr()
            url_res = laptop_offline_url()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                f"{url_res}\n\n📱 *PWA App Tip:* Chrome/Safari me kholkar menu se **'Add to Home Screen'** karein, ye phone me bilkul native app ki tarah save ho jayega!",
                reply_markup=active_kb,
            )
            return True

        if clean in ("📡 Start Hotspot", "/hotspot on", "/hotspot_on", "/hotspot") or clean_lower in ("start hotspot", "hotspot on", "chalu hotspot", "laptop hotspot"):
            temp_id = tg_send_message(chat_id, "📡 Laptop Wi-Fi Hotspot ('Hermes-Offline') chalu kiya ja raha hai...")
            res = laptop_hotspot_start()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("🛑 Stop Hotspot", "/hotspot off", "/hotspot_off") or clean_lower in ("stop hotspot", "hotspot off", "band hotspot"):
            res = laptop_hotspot_stop()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("/hotspot status",) or clean_lower in ("hotspot status",):
            res = laptop_hotspot_status()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        # ======================================================================
        # 4b. Master Remote Access Switch (Self-Use Mode vs Remote Mode)
        # ======================================================================
        # A) Explicit Turn ON Self-Use Mode (Remote OFF)
        is_turn_on_self = (
            clean in ("/self on", "/self_on", "/selfmode on", "/selfmode_on", "/selfuse on")
            or any(p in clean_lower for p in [
                "self on", "self mode on", "selfuse on", "self-use on", "self use on",
                "self use mode on", "self-use mode on", "turn on self", "enable self",
                "activate self", "self chalu", "self mode chalu", "self use chalu",
                "apna mode on", "apna use on", "apna mode chalu",
                "/remote off", "/remoteoff", "remote off", "turn off remote", "disable remote",
                "pause remote", "remote pause", "remote band", "remote stop"
            ])
        )

        # B) Explicit Turn OFF Self-Use Mode (Remote ON)
        is_turn_off_self = (
            clean in ("/self off", "/self_off", "/selfmode off", "/selfmode_off", "/selfuse off")
            or any(p in clean_lower for p in [
                "self off", "self mode off", "selfuse off", "self-use off", "self use off",
                "self use mode off", "self-use mode off", "turn off self", "disable self",
                "deactivate self", "self band", "self mode band", "self use band",
                "apna mode off", "apna use off", "apna mode band",
                "/remote on", "/remoteon", "remote on", "turn on remote", "enable remote",
                "resume remote", "remote resume", "remote chalu", "remote start"
            ])
        )

        # C) Toggle or General Self Mode / Remote Mode trigger
        is_toggle_self = (
            clean in ("🔴 Self-Use Mode", "🟢 Remote Mode", "🔴 Self Mode", "🟢 Remote Mode (Activate)", "🔴 Self-Use Mode (Pause)", "/remote", "/selfuse", "/selfmode", "/self", "/mode")
            or clean_lower in (
                "self", "/self", "/selfuse", "/selfmode", "/mode",
                "self mode", "selfmode", "self-mode",
                "self use", "selfuse", "self-use",
                "self use mode", "selfuse mode", "self-use mode",
                "apna mode", "apna use",
                "remote", "/remote", "remote mode", "remotemode", "toggle remote", "toggle self"
            )
            or ("self" in clean_lower and any(w in clean_lower for w in ["mode", "use", "toggle", "switch", "wala", "chalu", "band"]))
        )

        if is_turn_on_self:
            _is_remote_active = False
            update_dynamic_keyboards(False)
            res = laptop_remote_off()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if is_turn_off_self:
            _is_remote_active = True
            update_dynamic_keyboards(True)
            res = laptop_remote_on()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if is_toggle_self:
            res = laptop_remote_toggle()
            if "Self-Use Mode: ACTIVE" in res:
                _is_remote_active = False
            elif "Remote Mode: ACTIVE" in res:
                _is_remote_active = True
            else:
                _is_remote_active = not _is_remote_active
            update_dynamic_keyboards(_is_remote_active)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("/remote status", "/self status") or clean_lower in ("remote status", "self status", "self mode status"):
            res = laptop_remote_status()
            update_dynamic_keyboards()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        # ======================================================================
        # 5. AI & Sandbox Terminal Actions
        # ======================================================================
        if clean in ("⭐ Best Option", "/best", "/recommended") or clean_lower in ("best", "best option"):
            res = laptop_key_enter()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                "⭐ *Best Option Executed!*\n\n"
                "📋 *Short Summary:* Recommended option select karke Enter bhej diya gaya hai.",
                reply_markup=active_kb,
            )
            return True

        if clean in (
            "⚡ Auto Mode (Toggle)",
            "⚡ Auto Mode: OFF 🔴",
            "⚡ Auto Mode: ON 🟢",
            "⚡ Auto: ON 🟢",
            "⚡ Auto: OFF 🔴",
            "/auto",
            "/autotoggle",
            "/auto task",
        ) or clean_lower in ("auto", "auto mode", "auto approve", "autotoggle", "auto task"):
            res = laptop_auto_toggle()
            if "Auto Mode: ACTIVE" in res or "ENABLED" in res or "ON 🟢" in res:
                _is_auto_approve_active = True
            elif "Auto Mode: DEACTIVATED" in res or "DISABLED" in res or "OFF 🔴" in res:
                _is_auto_approve_active = False
            else:
                _is_auto_approve_active = not _is_auto_approve_active
            update_dynamic_keyboards()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                f"🔄 *Auto Mode Toggled!*\n\n📋 *Short Summary:* {res}",
                reply_markup=active_kb,
            )
            return True

        if clean in ("/auto on", "/autoon") or clean_lower in ("auto on", "autoon"):
            res = laptop_auto_on()
            _is_auto_approve_active = True
            update_dynamic_keyboards()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                "⚡ *Auto Mode Activated (Task Scope)*\n\n"
                "📋 *Short Summary:* Auto Mode is chat process ke complete hone tak chalu rahega, beech me bina roke automatic approve karega, aur process complete hone par final summary dega.",
                reply_markup=active_kb,
            )
            return True

        if clean in ("/auto always", "/auto permanent") or clean_lower in ("auto always", "auto permanent"):
            res = laptop_auto_always()
            _is_auto_approve_active = True
            update_dynamic_keyboards()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                "⚡ *Auto Mode Activated (Always ON)*\n\n"
                "📋 *Short Summary:* Auto Mode hamesha active rahega jab tak aap manually `/auto off` na karein.",
                reply_markup=active_kb,
            )
            return True

        if clean in ("/auto off", "/autooff") or clean_lower in ("auto off", "autooff"):
            res = laptop_auto_off()
            _is_auto_approve_active = False
            update_dynamic_keyboards()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                "🛑 *Auto-Approve Deactivated!*\n\n"
                "📋 *Short Summary:* Auto mode OFF ho gaya hai. Ab har approval aur question aapse poocha jayega.",
                reply_markup=active_kb,
            )
            return True

        if clean in ("/auto status", "/autostatus") or clean_lower in ("auto status",):
            res = laptop_auto_status()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                f"📊 *Auto-Approve Status:*\n\n📋 *Short Summary:* {res}",
                reply_markup=active_kb,
            )
            return True

        if clean in ("✅ Approve (Enter)", "/enter", "/approve") or clean_lower in ("approve", "enter", "ok"):
            res = laptop_key_enter()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("🟢 Send 'y'", "/yes", "/y") or clean_lower in ("y", "yes", "send y"):
            res = laptop_key_y()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("🔴 Send 'n'", "/no", "/n") or clean_lower in ("n", "no", "send n"):
            res = laptop_key_n()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("🛑 Ctrl+C", "/ctrlc", "/cancel") or clean_lower in ("ctrl+c", "ctrl c", "cancel"):
            res = laptop_key_ctrlc()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("📊 AI Status", "/aistatus") or clean_lower in ("ai status",):
            res = laptop_ai_status()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        # Number choices (1, 2, 3...)
        if (clean.isdigit() and len(clean) <= 2) or (clean.startswith(("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"))):
            num = int(clean) if clean.isdigit() else int(clean[0])
            res = laptop_key_num(num)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                f"🔢 *Option {num} Selected!*\n\n📋 *Short Summary:* {res}",
                reply_markup=active_kb,
            )
            return True

        if clean in ("⌨️ Type Text",) or cmd == "/type":
            type_text = clean[5:].strip() if cmd == "/type" else ""
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            if type_text:
                res = laptop_type(type_text)
                tg_send_message(chat_id, res, reply_markup=active_kb)
            else:
                tg_send_message(chat_id, "Usage: `/type text to type on active window`", reply_markup=active_kb)
            return True

        if clean in ("💻 Run Bash Cmd",) or cmd == "/cmd":
            bash_cmd = clean[4:].strip() if cmd == "/cmd" else ""
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            if bash_cmd:
                temp_id = tg_send_message(chat_id, f"💻 *Running on Laptop:*\n`{bash_cmd}`")
                res = execute_on_laptop(bash_cmd)
                tg_delete_message(chat_id, temp_id)
                tg_send_message(chat_id, f"💻 *Laptop Terminal Output:*\n```\n{res}\n```", reply_markup=active_kb)
            else:
                tg_send_message(chat_id, "Usage: `/cmd ls -la` ya `/cmd uname -a`", reply_markup=active_kb)
            return True

        # ======================================================================
        # 6. Media & Sound Actions
        # ======================================================================
        if clean == "🔉 Vol -" or clean_lower in ("vol-", "vol -", "volume down", "vol down", "volume kam"):
            res = laptop_vol_down()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean == "🔊 Vol +" or clean_lower in ("vol+", "vol +", "volume up", "vol up", "volume badhao"):
            res = laptop_vol_up()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("🔇 Mute", "🔊 Unmute") or clean_lower in ("mute", "unmute", "sound mute", "volume mute"):
            res = laptop_mute()
            if "MUTED" in res or "Mute: ACTIVE" in res or "Audio MUTED" in res:
                _is_muted = True
            elif "UNMUTED" in res or "Mute: OFF" in res or "Audio UNMUTED" in res:
                _is_muted = False
            else:
                _is_muted = not _is_muted
            update_dynamic_keyboards()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean == "⏯️ Play/Pause" or clean_lower in ("play/pause", "play pause", "pause"):
            res = laptop_playpause()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("⏹️ Stop Music", "/stop", "/stopmusic") or clean_lower in ("stop music", "stop audio", "stop song", "music stop", "/stop"):
            res = laptop_stop_music()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean_lower.startswith("play ") or clean_lower.startswith("gaana chalao ") or clean_lower.startswith("play music ") or cmd == "/play" or clean == "🎵 Play Music":
            if cmd == "/play":
                song = clean[5:].strip()
            elif clean_lower.startswith("play music "):
                song = clean[11:].strip()
            elif clean_lower.startswith("gaana chalao "):
                song = clean[13:].strip()
            elif clean_lower.startswith("play "):
                song = clean[5:].strip()
            else:
                song = ""
            if song:
                temp_id = tg_send_message(chat_id, f"🎵 Playing '{song}' on laptop...")
                res = laptop_play_music(song)
                if temp_id:
                    tg_delete_message(chat_id, temp_id)
                active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
                tg_send_message(chat_id, res, reply_markup=active_kb)
                return True
            else:
                active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
                tg_send_message(chat_id, "Usage: `/play arijit singh songs` ya `play barsaat`", reply_markup=active_kb)
                return True

        # ======================================================================
        # 7. System & Power Actions
        # ======================================================================
        if clean in ("📸 Quick Screen", "📸 Screenshot", "📸 Screen Peek", "/screenshot") or clean_lower in ("screenshot", "screen shot", "screen peek", "screen photo", "/screenshot"):
            temp_id = tg_send_message(chat_id, "📸 Laptop screen capture ho rahi hai...")
            res = laptop_screenshot()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                "📸 *Screenshot Completed!*\n\n"
                "📋 *Short Summary:* Nayi desktop screen photo bhej di gayi hai (purani images auto-delete ho gayi).",
                reply_markup=active_kb,
            )
            return True

        if clean in ("🔋 Battery", "/battery") or clean_lower in ("battery", "battery status", "charge", "charging", "/battery"):
            res = laptop_battery()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("🔒 Lock Screen", "🔓 Unlock Screen", "/lock", "/unlock") or clean_lower in ("lock", "lock screen", "lock laptop", "/lock", "unlock", "unlock screen"):
            res = laptop_lock_toggle()
            if "LOCKED" in res:
                _is_locked = True
            elif "UNLOCKED" in res:
                _is_locked = False
            else:
                _is_locked = not _is_locked
            update_dynamic_keyboards()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean == "💤 Sleep Laptop" or clean_lower in ("sleep", "sleep laptop"):
            res = laptop_power_sleep()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean == "🔄 Restart Laptop" or clean_lower in ("restart", "reboot", "restart laptop", "reboot laptop"):
            res = laptop_power_reboot()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean == "⛔ Shutdown Laptop" or clean_lower in ("shutdown", "poweroff", "shutdown laptop"):
            res = laptop_power_poweroff()
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean == "📋 Clipboard" or cmd in ("/clip", "/clipboard"):
            parts = clean.split(maxsplit=1)
            clip_val = parts[1] if len(parts) > 1 and parts[0] in ("/clip", "/clipboard") else ""
            res = laptop_clipboard(clip_val)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("📱 Running Apps", "/apps") or clean_lower in ("apps", "running apps", "processes", "top apps", "/apps"):
            temp_id = tg_send_message(chat_id, "📱 Fetching running apps...")
            res = laptop_apps()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        # ======================================================================
        # 8. Power, Screen & Next Section Actions
        # ======================================================================
        if clean in (
            "🕶️ Ghost Mode (Screen OFF)",
            "🕶️ Ghost Mode (Screen Off)",
            "🕶️ Ghost Mode",
            "/ghost",
        ) or clean_lower in ("ghost", "ghost mode", "screen off", "screenoff", "display off", "/ghost"):
            temp_id = tg_send_message(chat_id, "🕶️ Activating Ghost Mode...")
            res = laptop_ghost_mode()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in (
            "☀️ Screen ON",
            "☀️ Screen On",
            "☀️ Screen",
            "/screenon",
        ) or clean_lower in ("screen on", "screenon", "display on", "/screenon"):
            temp_id = tg_send_message(chat_id, "☀️ Display turn ON kar rahe hain...")
            res = laptop_screen_on()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(chat_id, res, reply_markup=active_kb)
            return True

        if clean in ("🌐 Open URL",) or cmd == "/open":
            parts = clean.split(maxsplit=1)
            if len(parts) > 1 and parts[0] == "/open":
                target_url = parts[1].strip()
                res = laptop_open_url(target_url)
                tg_send_message(chat_id, res, reply_markup=NEXT_SECTION_KEYBOARD)
            else:
                tg_send_message(chat_id, "Usage: `/open https://youtube.com` ya `/open google.com`", reply_markup=NEXT_SECTION_KEYBOARD)
            return True

        if clean in ("📶 Wi-Fi Status", "/wifi") or clean_lower in ("wifi", "wi-fi", "wifi status", "internet", "/wifi"):
            temp_id = tg_send_message(chat_id, "📶 Checking Wi-Fi...")
            res = laptop_wifi()
            tg_delete_message(chat_id, temp_id)
            tg_send_message(chat_id, res, reply_markup=NEXT_SECTION_KEYBOARD)
            return True

        if clean in ("💬 Screen Popup",) or cmd == "/popup":
            popup_val = clean[6:].strip() if cmd == "/popup" else ""
            if popup_val:
                res = laptop_popup("Telegram Notice", popup_val)
                tg_send_message(chat_id, res, reply_markup=NEXT_SECTION_KEYBOARD)
            else:
                tg_send_message(chat_id, "Usage: `/popup Hello from phone!`", reply_markup=NEXT_SECTION_KEYBOARD)
            return True

        if clean in ("🗣️ Speak Text",) or cmd == "/speak":
            speak_val = clean[6:].strip() if cmd == "/speak" else ""
            if speak_val:
                res = laptop_speak(speak_val)
                tg_send_message(chat_id, res, reply_markup=NEXT_SECTION_KEYBOARD)
            else:
                tg_send_message(chat_id, "Usage: `/speak Hello World`", reply_markup=NEXT_SECTION_KEYBOARD)
            return True

        # ======================================================================
        # 8b. Human Screen & Mouse GUI Actions
        # ======================================================================
        if clean in ("🚀 Open App (Human)",) or cmd == "/openapp":
            app_val = clean[8:].strip() if cmd == "/openapp" else ""
            if app_val:
                temp_id = tg_send_message(chat_id, f"🚀 *Opening '{app_val}' like a human...*")
                res = laptop_human_open_app(app_val)
                tg_delete_message(chat_id, temp_id)
                tg_send_message(chat_id, res, reply_markup=HUMAN_GUI_KEYBOARD)
            else:
                tg_send_message(
                    chat_id,
                    "Usage: `/openapp Chrome` ya `/openapp VS Code` ya `/openapp Telegram`\n(Ya seedhe bot se bolein: *'Chrome open karo screen par'*).",
                    reply_markup=HUMAN_GUI_KEYBOARD,
                )
            return True

        if clean in ("👁️ Screen Vision", "👁️ Screen Vision Analysis") or cmd == "/vision":
            temp_id = tg_send_message(chat_id, "👁️ *Screen analyze ho rahi hai...* (Gemini Multimodal Vision)")
            res = laptop_screen_inspect("Describe what is currently visible on screen in detail")
            tg_delete_message(chat_id, temp_id)
            tg_send_message(chat_id, res, reply_markup=HUMAN_GUI_KEYBOARD)
            return True

        if clean in ("🎯 Click Element",) or cmd == "/click":
            target_val = clean[6:].strip() if cmd == "/click" else ""
            if target_val:
                temp_id = tg_send_message(chat_id, f"🎯 *Searching & clicking '{target_val}' with mouse...*")
                res = laptop_screen_vision_click(target_val)
                tg_delete_message(chat_id, temp_id)
                tg_send_message(chat_id, res, reply_markup=HUMAN_GUI_KEYBOARD)
            else:
                tg_send_message(
                    chat_id,
                    "Usage: `/click search bar` ya `/click play button`\n(Ya seedhe chat me bolein: *'Play button par click karo'*).",
                    reply_markup=HUMAN_GUI_KEYBOARD,
                )
            return True

        if clean in ("⌨️ Human Typing",) or cmd == "/htype":
            type_val = clean[6:].strip() if cmd == "/htype" else ""
            if type_val:
                res = laptop_human_type(type_val, press_enter=False)
                tg_send_message(chat_id, res, reply_markup=HUMAN_GUI_KEYBOARD)
            else:
                tg_send_message(
                    chat_id,
                    "Usage: `/htype text to type with human speed`",
                    reply_markup=HUMAN_GUI_KEYBOARD,
                )
            return True

        if clean in ("📜 Scroll Down",) or cmd == "/scroll":
            res = laptop_human_scroll("down", 5)
            tg_send_message(chat_id, res, reply_markup=HUMAN_GUI_KEYBOARD)
            return True

        # ======================================================================
        # 9. Files & Diagnostic Tools Actions
        # ======================================================================
        # Cloud Status
        if clean in ("📊 Cloud Status",) or clean_lower in ("cloud status", "render status"):
            tg_send_message(
                chat_id,
                get_cloud_status_text(),
                reply_markup=CLOUD_DASHBOARD_KEYBOARD,
            )
            return True

        # Laptop Status
        if clean in ("📊 Laptop Status",) or clean_lower in ("laptop status",):
            tg_send_message(
                chat_id,
                get_laptop_status_text(),
                reply_markup=LAPTOP_DASHBOARD_KEYBOARD,
            )
            return True

        # Cloud Files / Workspace Files
        if clean in ("📁 Cloud Files", "📁 Workspace Files", "📁 Files") or cmd == "/files":
            tg_send_message(chat_id, get_files_text(), reply_markup=CLOUD_DASHBOARD_KEYBOARD)
            return True

        # Cloud Quick Test
        if clean in ("⚡ Cloud Quick Test", "⚡ Quick Test") or cmd == "/test":
            tg_send_message(chat_id, get_quick_test_text(), reply_markup=CLOUD_DASHBOARD_KEYBOARD)
            return True

        # Reset AI Memory
        if clean in ("🧹 Reset AI Memory", "🧹 Reset Memory", "🧹 Reset") or cmd == "/reset":
            session_id = f"tg_{chat_id}"
            clear_history(session_id)
            tg_send_message(
                chat_id,
                "🧹 Context clear ho gaya! Naya conversation shuru hai.",
                reply_markup=CLOUD_DASHBOARD_KEYBOARD,
            )
            return True

        if clean in ("🌐 24/7 Hosting Guide", "🌐 24/7 Hosting") or cmd == "/vps":
            tg_send_message(chat_id, get_vps_guide_text(), reply_markup=CLOUD_DASHBOARD_KEYBOARD)
            return True

        if clean in ("💡 Help Guide", "💡 Help") or cmd == "/help" or clean_lower in ("help", "guide"):
            tg_send_message(chat_id, get_help_text(), reply_markup=CLOUD_DASHBOARD_KEYBOARD)
            return True

        # Overall Status
        if cmd == "/status" or clean in ("📊 Quick Status", "📊 Status", "📊 Full Status") or clean_lower in ("status", "quick status", "system status", "health"):
            tg_send_message(
                chat_id,
                get_status_text(),
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
            return True

        # Remind
        if cmd == "/remind":
            parts = clean.split(maxsplit=2)
            if len(parts) >= 3:
                time_str, reminder_msg = parts[1].lower(), parts[2]
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
                    schedule_reminder(chat_id, seconds, reminder_msg)
                    tg_send_message(
                        chat_id,
                        f"⏰ Reminder set! Mai aapko `{time_str}` baad yaad dilaunga:\n_{reminder_msg}_",
                        reply_markup=ROOT_CHOICE_KEYBOARD,
                    )
                    return True
            tg_send_message(
                chat_id,
                "Usage: `/remind 10m check server` ya `/remind 30s check logs`",
            )
            return True

        # Remember
        if cmd == "/remember":
            parts = clean.split(maxsplit=1)
            if len(parts) > 1:
                fact = parts[1]
                save_fact(f"user_pref_{int(time.time())}", fact)
                tg_send_message(chat_id, f"🧠 Remembered: _{fact}_")
            else:
                tg_send_message(chat_id, "Usage: `/remember your preference`")
            return True

        return False

    def process_callback_query(self, cq: dict) -> None:
        """Process inline keyboard button taps."""
        cq_id = cq.get("id")
        from_user = cq.get("from", {})
        user_id = from_user.get("id")
        username = from_user.get("username", "")
        message = cq.get("message", {})
        cq_msg_id = message.get("message_id")
        chat_id = message.get("chat", {}).get("id")
        data = cq.get("data", "")
        global _is_remote_active, _is_locked, _is_muted, _is_auto_approve_active, _is_cctv_active

        if not is_user_allowed(user_id, username=username):
            logger.warning(f"Unauthorized callback query from {user_id} (@{username})")
            tg_answer_callback_query(
                cq_id, "⛔ Access Denied: Locked to @kissbilla2.", show_alert=True
            )
            return

        tg_answer_callback_query(cq_id)
        active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)

        if data == "lap_screenshot":
            temp_id = tg_send_message(chat_id, "📸 Laptop screen capture ho rahi hai...")
            res = laptop_screenshot()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            tg_send_message(
                chat_id,
                "📸 *Screenshot Completed!*\n\n"
                "📋 *Short Summary:* Nayi desktop screen photo bhej di gayi hai (purani images chat se auto-delete ho gayi).",
                reply_markup=active_kb,
            )
        elif data == "lap_webcam":
            temp_id = tg_send_message(chat_id, "📷 Front camera photo capture ho rahi hai...")
            res = laptop_webcam()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            tg_send_message(
                chat_id,
                "📷 *Webcam Snapshot Completed!*\n\n"
                "📋 *Short Summary:* Front camera snapshot bhej diya gaya hai (purani images chat se auto-delete ho gayi).",
                reply_markup=active_kb,
            )
        elif data == "lap_battery":
            res = laptop_battery()
            tg_send_message(
                chat_id,
                f"🔋 *Battery Status Completed!*\n\n📋 *Short Summary:*\n{res}",
                reply_markup=active_kb,
            )
        elif data == "lap_vol_up":
            res = laptop_vol_up()
            tg_send_message(
                chat_id,
                f"🔊 *Volume Up Completed!*\n\n📋 *Short Summary:* {res}",
                reply_markup=active_kb,
            )
        elif data == "lap_vol_down":
            res = laptop_vol_down()
            tg_send_message(
                chat_id,
                f"🔉 *Volume Down Completed!*\n\n📋 *Short Summary:* {res}",
                reply_markup=active_kb,
            )
        elif data == "lap_mute":
            res = laptop_mute()
            if "MUTED" in res:
                _is_muted = True
            elif "UNMUTED" in res:
                _is_muted = False
            else:
                _is_muted = not _is_muted
            update_dynamic_keyboards()
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            tg_send_message(
                chat_id,
                f"🔇 *Mute Toggle Completed!*\n\n📋 *Short Summary:* {res}",
                reply_markup=active_kb,
            )
        elif data == "lap_playpause":
            res = laptop_playpause()
            tg_send_message(
                chat_id,
                f"⏯️ *Play/Pause Completed!*\n\n📋 *Short Summary:* {res}",
                reply_markup=active_kb,
            )
        elif data == "lap_apps":
            res = laptop_apps()
            tg_send_message(
                chat_id,
                f"📱 *Running Apps Completed!*\n\n📋 *Short Summary:*\n{res}",
                reply_markup=active_kb,
            )
        elif data in ("lap_lock", "lap_lock_toggle"):
            res = laptop_lock_toggle()
            if "LOCKED" in res:
                _is_locked = True
            elif "UNLOCKED" in res:
                _is_locked = False
            else:
                _is_locked = not _is_locked
            update_dynamic_keyboards()
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            tg_send_message(
                chat_id,
                f"🔒 *Screen Lock Toggle:*\n\n{res}",
                reply_markup=active_kb,
            )
        elif data == "lap_wifi":
            res = laptop_wifi()
            tg_send_message(
                chat_id,
                f"📶 *Wi-Fi Status Completed!*\n\n📋 *Short Summary:*\n{res}",
                reply_markup=active_kb,
            )
        elif data == "lap_controls":
            tg_send_message(
                chat_id,
                "🎛️ *Laptop Live Control Panel:*\nNiche persistent buttons se direct laptop control karein:",
                reply_markup=active_kb,
            )
        elif data == "lap_offline_hub":
            qr_res = laptop_offline_qr()
            url_res = laptop_offline_url()
            tg_send_message(
                chat_id,
                f"{url_res}\n\n📱 *PWA App Tip:* Chrome/Safari me kholkar menu se **'Add to Home Screen'** karein, ye phone me bilkul native app ki tarah save ho jayega!",
                reply_markup=active_kb,
            )
        elif data == "lap_toggle_remote":
            res = laptop_remote_toggle()
            if "Self-Use Mode: ACTIVE" in res:
                _is_remote_active = False
            elif "Remote Mode: ACTIVE" in res:
                _is_remote_active = True
            else:
                _is_remote_active = not _is_remote_active
            update_dynamic_keyboards(_is_remote_active)
            if cq_msg_id:
                tg_edit_reply_markup(chat_id, cq_msg_id, get_laptop_control_keyboard())
            active_kb = _user_active_keyboard.get(chat_id, ROOT_CHOICE_KEYBOARD)
            tg_send_message(
                chat_id,
                res,
                reply_markup=active_kb,
            )
        elif data == "lap_coder_menu":
            tg_send_message(
                chat_id,
                "🤖 *Terminal & Sandbox Approval Keypad:*\nApproval button dabayein ya screen peek karein:",
                reply_markup=get_coder_keyboard(),
            )
        elif data == "lap_auto_on":
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            res = laptop_auto_on()
            _is_auto_approve_active = True
            tg_send_message(
                chat_id,
                "⚡ *Auto Mode Activated!*\n\n"
                "📋 *Short Summary:* Auto Mode chalu kar diya gaya hai. Ye is poori process ke complete hone tak active rahega aur process end hone par final summary dega.",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
        elif data == "lap_auto_off":
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            res = laptop_auto_off()
            _is_auto_approve_active = False
            tg_send_message(
                chat_id,
                "🛑 *Auto-Approve Deactivated!*\n\n"
                "📋 *Short Summary:* Auto Mode OFF ho gaya hai. Ab har approval aapse poocha jayega.",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
        elif data == "lap_auto_toggle":
            res = laptop_auto_toggle()
            if "ON 🟢" in res:
                _is_auto_approve_active = True
            elif "OFF 🔴" in res:
                _is_auto_approve_active = False
            else:
                _is_auto_approve_active = not _is_auto_approve_active
            if cq_msg_id:
                tg_edit_reply_markup(chat_id, cq_msg_id, get_laptop_control_keyboard())
            tg_send_message(
                chat_id,
                f"🔄 *Auto Mode Toggled!*\n\n📋 *Short Summary:* {res}",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
        elif data == "lap_key_enter":
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            res = laptop_key_enter()
            tg_send_message(
                chat_id,
                "✅ *Approval Completed!*\n\n"
                "📋 *Short Summary:* Best option (Approve/Enter) execute kar diya gaya hai. Sandbox prompt saf ho gaya.",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
        elif data == "lap_key_y":
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            res = laptop_key_y()
            tg_send_message(
                chat_id,
                "🟢 *Always Allow Executed!*\n\n"
                "📋 *Short Summary:* 'y' key send kar di gayi hai. Action permanently approve ho gaya.",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
        elif data == "lap_key_n":
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            res = laptop_key_n()
            tg_send_message(
                chat_id,
                "🔴 *Action Denied / Skipped!*\n\n"
                "📋 *Short Summary:* 'n' key send karke action reject kar diya gaya hai.",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
        elif data == "lap_key_ctrlc":
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            res = laptop_key_ctrlc()
            tg_send_message(
                chat_id,
                "🛑 *Process Cancelled!*\n\n"
                "📋 *Short Summary:* Ctrl+C send karke current task abort kar diya gaya hai.",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
        elif data.startswith("lap_key_") and data[len("lap_key_"):].isdigit():
            num = data[len("lap_key_"):]
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            res = laptop_key_num(int(num))
            tg_send_message(
                chat_id,
                f"🔢 *Choice {num} Selected!*\n\n"
                f"📋 *Short Summary:* Option {num} select karke Enter bhej diya gaya hai.",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
        elif data.startswith("lap_opt_") and data[len("lap_opt_"):].isdigit():
            opt_num = data[len("lap_opt_"):]
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            res = laptop_key_num(int(opt_num))
            tg_send_message(
                chat_id,
                f"⭐ *Best Option Selected!* (Choice {opt_num})\n\n"
                f"📋 *Short Summary:* Antigravity question ka choice {opt_num} select ho gaya hai.",
                reply_markup=ROOT_CHOICE_KEYBOARD,
            )
        elif data == "lap_ai_status":
            res = laptop_ai_status()
            tg_send_message(chat_id, res, reply_markup=get_coder_keyboard())
        elif data == "lap_mic":
            temp_id = tg_send_message(chat_id, "🎙️ 10-second laptop mic audio recording chalu hai...")
            res = laptop_mic(10)
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            tg_send_message(
                chat_id,
                "🎙️ *Audio Recording Completed!*\n\n"
                "📋 *Short Summary:* 10s voice note send ho gaya hai.",
                reply_markup=active_kb,
            )
        elif data == "lap_stop_music":
            res = laptop_stop_music()
            tg_send_message(
                chat_id,
                f"⏹️ *Music Stopped!*\n\n📋 *Short Summary:* {res}",
                reply_markup=active_kb,
            )
        elif data == "lap_clipboard":
            res = laptop_clipboard()
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_power_menu":
            tg_send_message(
                chat_id,
                "⚡ *Laptop Power Management:*\nAction select karein:",
                reply_markup=POWER_REPLY_KEYBOARD,
            )
        elif data == "lap_ghost":
            res = laptop_ghost_mode()
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_screen_on":
            res = laptop_screen_on()
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_power_sleep":
            res = laptop_power_sleep()
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_power_reboot":
            res = laptop_power_reboot()
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_power_poweroff":
            res = laptop_power_poweroff()
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_video":
            temp_id = tg_send_message(chat_id, "🎥 10-second webcam video + audio recording chalu hai...")
            res = laptop_webcam_video()
            if temp_id:
                tg_delete_message(chat_id, temp_id)
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_cctv":
            res = laptop_cctv_toggle()
            if "ACTIVATED" in res:
                _is_cctv_active = True
            elif "DEACTIVATED" in res:
                _is_cctv_active = False
            else:
                _is_cctv_active = not _is_cctv_active
            update_dynamic_keyboards()
            if cq_msg_id:
                tg_delete_message(chat_id, cq_msg_id)
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_alarm":
            res = laptop_alarm()
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_stop_alarm":
            res = laptop_stop_alarm()
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "lap_location":
            res = laptop_location()
            tg_send_message(chat_id, res, reply_markup=active_kb)
        elif data == "btn_laptop":
            if is_laptop_online():
                res = execute_on_laptop("uname -a && uptime -p && free -h")
                msg = f"💻 *Physical Laptop (Online 🟢):*\n```\n{res}\n```\n✅ Laptop execution verified!"
            else:
                cloud_res = execute_bash("uname -a && uptime -p && free -h")
                msg = (
                    "💻 *Laptop Status:* OFFLINE 🔴 (Laptop band hai)\n\n"
                    "🔄 *Auto-Fallback to ☁️ Cloud Server:*\n"
                    f"```\n{cloud_res}\n```\n"
                    "✅ Fallback to 24/7 Cloud Server successful!"
                )
            tg_send_message(chat_id, msg, reply_markup=active_kb)
        elif data == "btn_cloud":
            res = execute_bash("uname -a && uptime -p && free -h")
            msg = f"☁️ *24/7 Render Cloud Server (Online 🟢):*\n```\n{res}\n```\n✅ Cloud Server execution verified!"
            tg_send_message(chat_id, msg, reply_markup=active_kb)
        elif data == "btn_status":
            tg_send_message(chat_id, get_status_text(), reply_markup=active_kb)
        elif data == "btn_files":
            tg_send_message(chat_id, get_files_text(), reply_markup=active_kb)
        elif data == "btn_test":
            tg_send_message(chat_id, get_quick_test_text(), reply_markup=active_kb)
        elif data == "btn_reset":
            clear_history(f"tg_{chat_id}")
            tg_send_message(
                chat_id,
                "🧹 Context clear ho gaya!",
                reply_markup=active_kb,
            )
        elif data == "btn_vps":
            tg_send_message(chat_id, get_vps_guide_text(), reply_markup=active_kb)
        elif data == "btn_help":
            tg_send_message(chat_id, get_help_text(), reply_markup=active_kb)

    def process_message(self, message: dict) -> None:
        """Process incoming Telegram message (text, photo, or document)."""
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        from_user = message.get("from", {})
        user_id = from_user.get("id")
        username = from_user.get("username", "")
        text = message.get("text", "").strip()

        if not chat_id or not user_id:
            return

        # Security check: verify authorization
        if not is_user_allowed(user_id, username=username):
            logger.warning(
                f"Unauthorized message attempt from user ID: {user_id} (@{username})"
            )
            tg_send_message(
                chat_id,
                "⛔ *Access Denied*\nThis Hermes Agent is private and strictly locked to @kissbilla2.",
            )
            return

        session_id = f"tg_{chat_id}"
        last_update_time = [time.time()]

        def progress_update(status_text: str):
            tg_send_chat_action(chat_id, "typing")
            now = time.time()
            if status_msg_id and (now - last_update_time[0] >= 1.5):
                last_update_time[0] = now
                tg_edit_message(chat_id, status_msg_id, f"⚙️ {status_text}")

        # 1. Handle Photo / Screenshot Upload
        if "photo" in message:
            photo_list = message["photo"]
            best_photo = photo_list[-1]
            file_id = best_photo["file_id"]
            caption = message.get("caption", "Is screenshot ya image ko analyze karein aur batein isme kya hai.")

            tg_send_chat_action(chat_id, "typing")
            status_msg_id = tg_send_message(chat_id, "🔍 *Hermes:* Photo download & analyze ho rahi hai...")

            img_bytes = download_telegram_file(file_id)
            if not img_bytes:
                tg_send_message(chat_id, "❌ Error: Photo download nahi ho payi.")
                return

            try:
                result = self.agent.run_task(
                    session_id=session_id,
                    user_message=caption,
                    image_bytes=img_bytes,
                    image_mime="image/jpeg",
                    progress_callback=progress_update,
                )
                if status_msg_id:
                    tg_delete_message(chat_id, status_msg_id)
                tg_send_message(chat_id, result, reply_markup=MAIN_DASHBOARD_KEYBOARD)
            except Exception as e:
                logger.error(f"Error analyzing image: {e}")
                if status_msg_id:
                    tg_delete_message(chat_id, status_msg_id)
                tg_send_message(chat_id, f"❌ Error: {str(e)}", reply_markup=MAIN_DASHBOARD_KEYBOARD)
            return

        # 2. Handle Document / Code File Upload
        if "document" in message:
            doc = message["document"]
            file_id = doc["file_id"]
            file_name = doc.get("file_name", f"file_{int(time.time())}")
            caption = message.get("caption", f"User ne file bheji hai: {file_name}. Analyze ya save karein.")

            tg_send_chat_action(chat_id, "typing")
            status_msg_id = tg_send_message(chat_id, f"📥 *Hermes:* `{file_name}` download ho rahi hai...")

            doc_bytes = download_telegram_file(file_id)
            if not doc_bytes:
                if status_msg_id:
                    tg_delete_message(chat_id, status_msg_id)
                tg_send_message(chat_id, "❌ Error: Document download nahi ho payi.", reply_markup=MAIN_DASHBOARD_KEYBOARD)
                return

            # Save to workspace uploads
            dest_path = UPLOADS_DIR / file_name
            with open(dest_path, "wb") as f:
                f.write(doc_bytes)

            file_prompt = f"User ne file '{file_name}' upload ki hai (saved at {dest_path}). Caption: {caption}"
            # If text/code file, include preview
            try:
                text_content = doc_bytes.decode("utf-8")
                if len(text_content) < 5000:
                    file_prompt += f"\nFile content:\n```\n{text_content}\n```"
            except Exception:
                pass

            try:
                result = self.agent.run_task(
                    session_id=session_id,
                    user_message=file_prompt,
                    progress_callback=progress_update,
                )
                if status_msg_id:
                    tg_delete_message(chat_id, status_msg_id)
                tg_send_message(chat_id, result, reply_markup=MAIN_DASHBOARD_KEYBOARD)
            except Exception as e:
                logger.error(f"Error analyzing document: {e}")
                if status_msg_id:
                    tg_delete_message(chat_id, status_msg_id)
                tg_send_message(chat_id, f"❌ Error: {str(e)}", reply_markup=MAIN_DASHBOARD_KEYBOARD)
            return

        # 3. Handle Regular Text Message
        if not text:
            return

        # Handle slash commands or reply button texts
        if self.handle_command_or_button(chat_id, user_id, text):
            return

        # Regular task prompt -> Run Agent
        tg_send_chat_action(chat_id, "typing")
        status_msg_id = tg_send_message(
            chat_id, "⏳ *Hermes:* Analyzing task...", parse_mode="Markdown"
        )

        try:
            result = self.agent.run_task(
                session_id=session_id,
                user_message=text,
                progress_callback=progress_update,
            )
            if status_msg_id:
                tg_delete_message(chat_id, status_msg_id)
            tg_send_message(
                chat_id,
                result,
                reply_markup=MAIN_DASHBOARD_KEYBOARD,
            )
        except Exception as e:
            logger.error(f"Error executing agent task: {e}")
            if status_msg_id:
                tg_delete_message(chat_id, status_msg_id)
            tg_send_message(chat_id, f"❌ Error: {str(e)}", reply_markup=MAIN_DASHBOARD_KEYBOARD)

    def start_polling(self) -> None:
        """Run long polling loop handling messages and callback queries."""
        logger.info("Hermes Telegram Bot is starting long polling...")
        print("=" * 60)
        print("🤖 Hermes Autonomous Telegram Agent is RUNNING")
        print(f"📁 Workspace: {WORKSPACE_DIR}")
        print("Waiting for Telegram messages, photos, files, and callbacks...")
        print("=" * 60)

        error_delay = 1
        while True:
            try:
                url = f"{API_BASE}/getUpdates"
                params = {"offset": self.offset, "timeout": 20}
                resp = requests.get(url, params=params, timeout=30)

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
                    logger.warning(f"Telegram polling HTTP {resp.status_code}")
                    time.sleep(error_delay)
                    error_delay = min(error_delay * 2, 30)

            except requests.exceptions.RequestException as e:
                logger.error(f"Network error in polling loop: {e}")
                time.sleep(error_delay)
                error_delay = min(error_delay * 2, 30)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(2)


if __name__ == "__main__":
    runner = TelegramBotRunner()
    runner.start_polling()
