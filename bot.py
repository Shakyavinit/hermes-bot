"""
Hermes Telegram Bot Gateway - COMPLETE EDITION
Fully organized with nested menu system, all requested features integrated.
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
    laptop_stop_music, laptop_type, laptop_vol_down, laptop_vol_up, laptop_webcam,
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
from tools import execute_bash, execute_on_laptop, list_directory, smart_execute, system_status

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
_user_menu_state: Dict[int, str] = {}  # Track which menu user is on
_user_pending_input: Dict[int, str] = {}  # Track expected input (e.g., "typing_text", "url", etc.)
_notes_storage: Dict[int, List[str]] = {}  # Local notes

# ==============================================================================
# NESTED KEYBOARD SYSTEM - Well Organized & Categorized
# ==============================================================================

def kb(rows: List[List[str]], resize: bool = True, persistent: bool = True) -> dict:
    """Helper to build reply keyboard."""
    return {
        "keyboard": [[{"text": t} for t in row] for row in rows],
        "resize_keyboard": resize,
        "is_persistent": persistent,
    }


def get_main_menu_kb() -> dict:
    """🏠 MAIN MENU - Root of all categories."""
    return kb([
        ["📸 Camera & Media", "🎙️ Audio & Voice"],
        ["🖥️ System Info", "⚡ Power & Screen"],
        ["🔊 Volume & Sound", "🎵 Media Control"],
        ["🖱️ Mouse & Keyboard", "🌐 Browser & Apps"],
        ["🚨 Security & Spy", "🤖 AI & Automation"],
        ["📋 Clipboard & Notes", "📶 Network & Offline"],
        ["🔧 Terminal & Files", "⏰ Reminders & Memory"],
        ["🎛️ Quick Toggles", "❓ Help & Status"],
    ])


def get_camera_media_kb() -> dict:
    """📸 CAMERA & MEDIA MENU"""
    return kb([
        ["📸 Screenshot", "📷 Front Camera Photo"],
        ["🎥 5s Webcam Video", "🎥 10s Webcam Video"],
        ["🖼️ AI Photo Analysis", "🧹 Clean Photos"],
        ["🏠 Main Menu"],
    ])


def get_audio_voice_kb() -> dict:
    """🎙️ AUDIO & VOICE MENU"""
    return kb([
        ["🎙️ Record Mic 10s", "🎙️ Record Mic 30s"],
        ["🗣️ Text-to-Speech", "📝 Voice Transcribe"],
        ["🏠 Main Menu"],
    ])


def get_system_info_kb() -> dict:
    """🖥️ SYSTEM INFO MENU"""
    return kb([
        ["🔋 Battery Status", "⚡ Charging Alert"],
        ["💻 CPU & RAM Usage", "💾 Disk Space"],
        ["🌡️ CPU Temperature", "📶 WiFi Name"],
        ["🌍 Public IP", "🏠 Local IP"],
        ["📍 Laptop Location", "📊 Full System Status"],
        ["🏠 Main Menu"],
    ])


def get_power_screen_kb() -> dict:
    """⚡ POWER & SCREEN MENU"""
    global _is_locked, _is_ghost_mode
    lock_btn = "🔓 Unlock Screen" if _is_locked else "🔒 Lock Screen"
    ghost_btn = "☀️ Display ON" if _is_ghost_mode else "🕶️ Display OFF (Ghost)"
    return kb([
        [lock_btn, ghost_btn],
        ["💤 Sleep Laptop", "🔄 Reboot Laptop"],
        ["⛔ Shutdown Laptop"],
        ["🏠 Main Menu"],
    ])


def get_volume_sound_kb() -> dict:
    """🔊 VOLUME & SOUND MENU"""
    global _is_muted
    mute_btn = "🔊 Unmute" if _is_muted else "🔇 Mute"
    return kb([
        ["🔉 Volume Down", "🔊 Volume Up"],
        [mute_btn, "🎚️ Set Volume %"],
        ["🏠 Main Menu"],
    ])


def get_media_control_kb() -> dict:
    """🎵 MEDIA CONTROL MENU"""
    return kb([
        ["⏯️ Play/Pause", "⏹️ Stop Music"],
        ["⏭️ Next Track", "⏮️ Previous Track"],
        ["🎵 Play Song (Search)"],
        ["🏠 Main Menu"],
    ])


def get_mouse_keyboard_kb() -> dict:
    """🖱️ MOUSE & KEYBOARD MENU"""
    return kb([
        ["🖱️ Left Click", "🖱️ Right Click"],
        ["⬆️ Scroll Up", "⬇️ Scroll Down"],
        ["👁️ AI Vision Click", "🎯 Click Element"],
        ["⌨️ Type Text", "⌨️ Human Type"],
        ["↩️ Press Enter", "🛑 Press Ctrl+C"],
        ["⎋ Press Esc", "␣ Press Space"],
        ["⇥ Press Tab", "❌ Press Alt+F4"],
        ["🏠 Main Menu"],
    ])


def get_browser_apps_kb() -> dict:
    """🌐 BROWSER & APPS MENU"""
    return kb([
        ["🌐 Open URL", "🌐 Open Chrome"],
        ["💻 Open VS Code", "⌨️ Open Terminal"],
        ["🎵 Open Spotify", "🚀 Open Any App"],
        ["📱 Running Apps"],
        ["🏠 Main Menu"],
    ])


def get_security_spy_kb() -> dict:
    """🚨 SECURITY & SPY MENU"""
    global _is_cctv_active
    cctv_btn = "🛑 Stop CCTV" if _is_cctv_active else "👁️ Start CCTV Motion"
    return kb([
        ["🚨 Siren Alarm", "⏹️ Stop Alarm"],
        [cctv_btn, "📍 Find Laptop"],
        ["📷 Silent Snap", "🎥 Silent Video"],
        ["🏠 Main Menu"],
    ])


def get_ai_automation_kb() -> dict:
    """🤖 AI & AUTOMATION MENU"""
    global _is_auto_approve_active, _is_remote_active
    auto_btn = "⚡ Auto-Approve: ON 🟢" if _is_auto_approve_active else "⚡ Auto-Approve: OFF 🔴"
    self_btn = "🟢 Remote Mode" if not _is_remote_active else "🔴 Self-Use Mode"
    return kb([
        [self_btn, auto_btn],
        ["♾️ Auto Always ON", "🎯 Auto Task Only"],
        ["🛑 Auto OFF", "📊 AI Status"],
        ["✅ Approve (Enter)", "🟢 Send 'y'"],
        ["🔴 Send 'n'", "🛑 Cancel Ctrl+C"],
        ["1️⃣", "2️⃣", "3️⃣"],
        ["🏠 Main Menu"],
    ])


def get_clipboard_notes_kb() -> dict:
    """📋 CLIPBOARD & NOTES MENU"""
    return kb([
        ["📋 Read Clipboard", "✏️ Write Clipboard"],
        ["📝 Save Note", "📖 Recall Notes"],
        ["🏠 Main Menu"],
    ])


def get_network_offline_kb() -> dict:
    """📶 NETWORK & OFFLINE MENU"""
    global _is_hotspot_active
    hotspot_btn = "🛑 Stop Hotspot" if _is_hotspot_active else "📡 Start Hotspot"
    return kb([
        ["📶 WiFi Status", "🌍 Check Internet"],
        [hotspot_btn, "📊 Hotspot Status"],
        ["🌐 Offline Hub URL", "📱 Offline Hub QR"],
        ["🏠 Main Menu"],
    ])


def get_terminal_files_kb() -> dict:
    """🔧 TERMINAL & FILES MENU"""
    return kb([
        ["💻 Run Bash Command", "📁 List Files"],
        ["⬇️ Download File", "⬆️ Upload File Info"],
        ["🏠 Main Menu"],
    ])


def get_reminders_memory_kb() -> dict:
    """⏰ REMINDERS & MEMORY MENU"""
    return kb([
        ["⏰ Set Reminder", "🧠 Save to Memory"],
        ["📖 Show Memory", "🧹 Reset History"],
        ["🏠 Main Menu"],
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
        ["🎨 Toggle Custom Keypad"],
        ["🏠 Main Menu"],
    ])


def get_help_status_kb() -> dict:
    """❓ HELP & STATUS MENU"""
    return kb([
        ["📊 Full Status", "💻 Laptop Status"],
        ["☁️ Cloud Status", "💡 Help Guide"],
        ["🌐 24/7 Hosting Info"],
        ["🏠 Main Menu"],
    ])


# ==============================================================================
# MENU ROUTER - Maps menu names to keyboards
# ==============================================================================
MENU_MAP = {
    "main": get_main_menu_kb,
    "camera": get_camera_media_kb,
    "audio": get_audio_voice_kb,
    "system": get_system_info_kb,
    "power": get_power_screen_kb,
    "volume": get_volume_sound_kb,
    "media": get_media_control_kb,
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


def get_kb_for(menu: str) -> dict:
    """Get keyboard for a menu name."""
    return MENU_MAP.get(menu, get_main_menu_kb)()


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
    if reply_markup:
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


def tg_send_chat_action(chat_id: int, action: str = "typing") -> None:
    try:
        requests.post(f"{API_BASE}/sendChatAction", json={"chat_id": chat_id, "action": action}, timeout=5)
    except Exception:
        pass


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
        {"command": "start", "description": "🏠 Open Main Menu"},
        {"command": "menu", "description": "📱 Show Menu Panel"},
        {"command": "status", "description": "📊 System Status"},
        {"command": "screenshot", "description": "📸 Take Screenshot"},
        {"command": "webcam", "description": "📷 Webcam Photo"},
        {"command": "battery", "description": "🔋 Battery Level"},
        {"command": "self", "description": "🔴 Toggle Self-Use Mode"},
        {"command": "auto", "description": "⚡ Toggle Auto-Approve"},
        {"command": "remind", "description": "⏰ Set Reminder"},
        {"command": "reset", "description": "🧹 Clear History"},
        {"command": "help", "description": "💡 Show Help"},
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
    return (
        "📊 *Hermes System Status:*\n\n"
        f"```\n{sys_stat}\n```\n"
        f"• **Owner:** @{cfg.get('owner_username', 'kissbilla2')}\n"
        f"• **💻 Laptop:** {laptop_status}\n"
        f"• **☁️ Cloud:** ONLINE 24/7 🟢\n"
        f"• **AI:** Gemini Flash Lite\n"
        f"• **Memory Facts:** {len(facts)}\n"
        f"• **Remote Mode:** {'🟢 ON' if _is_remote_active else '🔴 OFF'}\n"
        f"• **Auto-Approve:** {'🟢 ON' if _is_auto_approve_active else '🔴 OFF'}"
    )


def get_help_text() -> str:
    return (
        "🛠️ *Hermes Bot - Complete Guide*\n\n"
        "*📱 Menu Navigation:*\n"
        "Har menu me niche `🏠 Main Menu` button hai wapas jaane ke liye.\n\n"
        "*🎯 Direct Commands:*\n"
        "• `/screenshot` - Screen photo\n"
        "• `/webcam` - Camera photo\n"
        "• `/battery` - Battery status\n"
        "• `/remind 10m task` - Timer\n"
        "• `/self` - Toggle self-use\n"
        "• `/auto` - Toggle auto-approve\n\n"
        "*🖼️ Media Uploads:*\n"
        "• Photo bhejein → AI analyze karega\n"
        "• Voice note → Auto transcribe\n"
        "• File upload → Save to workspace\n\n"
        "*🤖 Natural Language:*\n"
        "Chat me kuch bhi bolein - AI samjhega!\n"
        "Example: 'chrome khol', 'volume badha', 'screenshot le'\n\n"
        "🔒 Locked to @kissbilla2"
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
        server = socketserver.TCPServer(("0.0.0.0", port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info(f"Health server on port {port}")
    except Exception as e:
        logger.warning(f"Server bind failed: {e}")


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

    def send_result(self, chat_id: int, title: str, result: str, menu: str = None) -> None:
        """Send result with the appropriate menu keyboard."""
        current_menu = menu or _user_menu_state.get(chat_id, "main")
        text = f"{title}\n\n{result}" if result else title
        tg_send_message(chat_id, text, reply_markup=get_kb_for(current_menu))

    def switch_menu(self, chat_id: int, menu_name: str, title: str = None) -> None:
        """Switch to a submenu."""
        _user_menu_state[chat_id] = menu_name
        menu_titles = {
            "main": "🏠 *Main Menu* - Sabhi categories:",
            "camera": "📸 *Camera & Media* - Photo/Video controls:",
            "audio": "🎙️ *Audio & Voice* - Mic aur sound:",
            "system": "🖥️ *System Info* - Laptop ki details:",
            "power": "⚡ *Power & Screen* - Power management:",
            "volume": "🔊 *Volume & Sound* - Sound controls:",
            "media": "🎵 *Media Control* - Music aur video:",
            "mouse": "🖱️ *Mouse & Keyboard* - Input controls:",
            "browser": "🌐 *Browser & Apps* - App launcher:",
            "security": "🚨 *Security & Spy* - Surveillance:",
            "ai": "🤖 *AI & Automation* - Sandbox controls:",
            "clipboard": "📋 *Clipboard & Notes* - Text management:",
            "network": "📶 *Network & Offline* - WiFi/Hotspot:",
            "terminal": "🔧 *Terminal & Files* - Bash commands:",
            "reminders": "⏰ *Reminders & Memory* - Notes/Alerts:",
            "toggles": "🎛️ *Quick Toggles* - Fast switches:",
            "help": "❓ *Help & Status* - Info aur guide:",
        }
        text = title or menu_titles.get(menu_name, "📱 Menu:")
        tg_send_message(chat_id, text, reply_markup=get_kb_for(menu_name))

    def handle_button_or_command(self, chat_id: int, user_id: int, text: str) -> bool:
        """Main button/command router - clean and organized."""
        global _is_remote_active, _is_locked, _is_muted, _is_auto_approve_active
        global _is_cctv_active, _is_hotspot_active, _is_ghost_mode

        clean = text.strip()
        cmd = clean.split()[0].lower() if clean else ""
        low = clean.lower()

        # ==================== HANDLE PENDING INPUT ====================
        if chat_id in _user_pending_input:
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

        # ==================== ROOT COMMANDS ====================
        if cmd in ("/start", "/menu") or clean in ("🏠 Main Menu", "📱 Menu"):
            cfg = get_runtime_config()
            if cfg.get("owner_user_id") is None:
                set_owner(user_id)
            self.switch_menu(chat_id, "main",
                "👑 *Hermes Autonomous Agent*\n\n"
                f"💻 Laptop: {'🟢 ONLINE' if is_laptop_online() else '🔴 OFFLINE'}\n"
                f"🎮 Remote: {'🟢 ACTIVE' if _is_remote_active else '🔴 PAUSED'}\n"
                f"⚡ Auto: {'🟢 ON' if _is_auto_approve_active else '🔴 OFF'}\n\n"
                "Category select karein:"
            )
            return True

        # ==================== CATEGORY SWITCHES ====================
        category_map = {
            "📸 Camera & Media": "camera",
            "🎙️ Audio & Voice": "audio",
            "🖥️ System Info": "system",
            "⚡ Power & Screen": "power",
            "🔊 Volume & Sound": "volume",
            "🎵 Media Control": "media",
            "🖱️ Mouse & Keyboard": "mouse",
            "🌐 Browser & Apps": "browser",
            "🚨 Security & Spy": "security",
            "🤖 AI & Automation": "ai",
            "📋 Clipboard & Notes": "clipboard",
            "📶 Network & Offline": "network",
            "🔧 Terminal & Files": "terminal",
            "⏰ Reminders & Memory": "reminders",
            "🎛️ Quick Toggles": "toggles",
            "❓ Help & Status": "help",
        }
        if clean in category_map:
            self.switch_menu(chat_id, category_map[clean])
            return True

        # ==================== CAMERA & MEDIA ====================
        if clean == "📸 Screenshot" or cmd == "/screenshot" or low in ("screenshot", "screen shot"):
            temp = tg_send_message(chat_id, "📸 Capturing screen...")
            res = laptop_screenshot()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "📸 *Screenshot Sent!*", "Screen photo bhej di gayi hai.")
            return True

        if clean == "📷 Front Camera Photo" or cmd == "/webcam" or low in ("selfie", "webcam", "camera photo"):
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
        if clean == "🎙️ Record Mic 10s" or cmd == "/mic" or low in ("mic", "record audio"):
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
        if clean == "🔋 Battery Status" or cmd == "/battery" or low in ("battery", "charge"):
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

        if clean == "📍 Laptop Location" or cmd == "/locate" or low in ("location", "find laptop"):
            temp = tg_send_message(chat_id, "📍 Fetching location...")
            res = laptop_location()
            tg_delete_message(chat_id, temp)
            self.send_result(chat_id, "📍 *Location:*", res)
            return True

        if clean == "📊 Full System Status" or cmd == "/status" or low == "status":
            self.send_result(chat_id, "", get_status_text())
            return True

        # ==================== POWER & SCREEN ====================
        if clean in ("🔒 Lock Screen", "🔓 Unlock Screen") or cmd in ("/lock", "/unlock") or low in ("lock", "unlock"):
            res = laptop_lock_toggle()
            _is_locked = not _is_locked if "LOCKED" not in res.upper() and "UNLOCKED" not in res.upper() else ("LOCKED" in res.upper() and "UNLOCKED" not in res.upper())
            self.switch_menu(chat_id, _user_menu_state.get(chat_id, "power"),
                f"🔒 *Lock Toggled:*\n\n{res}")
            return True

        if clean in ("🕶️ Display OFF (Ghost)", "☀️ Display ON") or low in ("ghost", "display off", "screen off"):
            if _is_ghost_mode:
                res = laptop_screen_on()
                _is_ghost_mode = False
            else:
                res = laptop_ghost_mode()
                _is_ghost_mode = True
            self.switch_menu(chat_id, _user_menu_state.get(chat_id, "power"),
                f"🕶️ *Display Toggled:*\n\n{res}")
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
        if clean == "🔉 Volume Down" or low in ("vol down", "volume down"):
            res = laptop_vol_down()
            self.send_result(chat_id, "🔉 *Volume Down:*", res)
            return True

        if clean == "🔊 Volume Up" or low in ("vol up", "volume up"):
            res = laptop_vol_up()
            self.send_result(chat_id, "🔊 *Volume Up:*", res)
            return True

        if clean in ("🔇 Mute", "🔊 Unmute") or low in ("mute", "unmute"):
            res = laptop_mute()
            _is_muted = not _is_muted
            self.switch_menu(chat_id, _user_menu_state.get(chat_id, "volume"),
                f"🔇 *Mute Toggled:*\n\n{res}")
            return True

        if clean == "🎚️ Set Volume %":
            _user_pending_input[chat_id] = "volume_percent"
            self.send_result(chat_id, "🎚️ *Set Volume:*", "Volume percentage bhejein (e.g., 50):")
            return True

        # ==================== MEDIA CONTROL ====================
        if clean == "⏯️ Play/Pause" or low in ("play/pause", "pause"):
            res = laptop_playpause()
            self.send_result(chat_id, "⏯️ *Media:*", res)
            return True

        if clean == "⏹️ Stop Music" or low in ("stop music", "stop"):
            res = laptop_stop_music()
            self.send_result(chat_id, "⏹️ *Music Stopped:*", res)
            return True

        if clean == "⏭️ Next Track":
            res = execute_on_laptop("playerctl next 2>/dev/null || xdotool key XF86AudioNext")
            self.send_result(chat_id, "⏭️ *Next Track:*", res)
            return True

        if clean == "⏮️ Previous Track":
            res = execute_on_laptop("playerctl previous 2>/dev/null || xdotool key XF86AudioPrev")
            self.send_result(chat_id, "⏮️ *Previous Track:*", res)
            return True

        if clean == "🎵 Play Song (Search)":
            _user_pending_input[chat_id] = "play_song"
            self.send_result(chat_id, "🎵 *Play Song:*", "Song name bhejein:")
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

        if clean == "📱 Running Apps" or cmd == "/apps":
            res = laptop_apps()
            self.send_result(chat_id, "📱 *Running Apps:*", res)
            return True

        # ==================== SECURITY & SPY ====================
        if clean == "🚨 Siren Alarm" or low in ("alarm", "siren"):
            res = laptop_alarm()
            self.send_result(chat_id, "🚨 *Alarm ON:*", res)
            return True

        if clean == "⏹️ Stop Alarm" or low in ("stop alarm", "stop siren"):
            res = laptop_stop_alarm()
            self.send_result(chat_id, "⏹️ *Alarm Stopped:*", res)
            return True

        if clean in ("👁️ Start CCTV Motion", "🛑 Stop CCTV") or low == "cctv":
            res = laptop_cctv_toggle()
            _is_cctv_active = not _is_cctv_active
            self.switch_menu(chat_id, "security", f"👁️ *CCTV Toggled:*\n\n{res}")
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
            current = _user_menu_state.get(chat_id, "ai")
            self.switch_menu(chat_id, current, f"🎮 *Mode Toggled:*\n\n{res}")
            return True

        if clean in ("⚡ Auto-Approve: ON 🟢", "⚡ Auto-Approve: OFF 🔴", "⚡ Auto: ON 🟢", "⚡ Auto: OFF 🔴") or cmd == "/auto":
            res = laptop_auto_toggle()
            _is_auto_approve_active = not _is_auto_approve_active
            current = _user_menu_state.get(chat_id, "ai")
            self.switch_menu(chat_id, current, f"⚡ *Auto Toggled:*\n\n{res}")
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
        if clean == "💻 Laptop Status":
            online = is_laptop_online()
            status = f"💻 *Laptop:* {'🟢 ONLINE' if online else '🔴 OFFLINE'}"
            if online:
                status += f"\n🔋 {laptop_battery()}"
            self.send_result(chat_id, status, "")
            return True

        if clean == "☁️ Cloud Status":
            res = system_status()
            self.send_result(chat_id, "☁️ *Cloud Server:*", f"```\n{res}\n```\n✅ 24/7 Live on Render")
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
        """Handle inline button callbacks (kept minimal for legacy)."""
        cq_id = cq.get("id")
        try:
            requests.post(f"{API_BASE}/answerCallbackQuery",
                json={"callback_query_id": cq_id}, timeout=5)
        except Exception:
            pass

    def process_message(self, message: dict) -> None:
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        from_user = message.get("from", {})
        user_id = from_user.get("id")
        username = from_user.get("username", "")
        text = message.get("text", "").strip()

        if not chat_id or not user_id:
            return

        if not is_user_allowed(user_id, username=username):
            logger.warning(f"Unauthorized: {user_id} (@{username})")
            tg_send_message(chat_id, "⛔ Access Denied - Locked to @kissbilla2")
            return

        session_id = f"tg_{chat_id}"

        # PHOTO handling
        if "photo" in message:
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
                tg_send_message(chat_id, result, reply_markup=get_kb_for(current))
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
                    tg_send_message(chat_id, result, reply_markup=get_kb_for(current))
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
                tg_send_message(chat_id, result, reply_markup=get_kb_for(current))
            except Exception as e:
                tg_delete_message(chat_id, status_id)
                tg_send_message(chat_id, f"❌ Error: {e}")
            return

        if not text:
            return

        # Handle buttons/commands
        if self.handle_button_or_command(chat_id, user_id, text):
            return

        # Fallback: Natural language → AI Agent
        tg_send_chat_action(chat_id, "typing")
        status_id = tg_send_message(chat_id, "⏳ *Hermes:* Processing...")
        try:
            result = self.agent.run_task(session_id=session_id, user_message=text)
            tg_delete_message(chat_id, status_id)
            current = _user_menu_state.get(chat_id, "main")
            tg_send_message(chat_id, result, reply_markup=get_kb_for(current))
        except Exception as e:
            logger.error(f"Agent error: {e}")
            tg_delete_message(chat_id, status_id)
            tg_send_message(chat_id, f"❌ Error: {e}", reply_markup=get_main_menu_kb())

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
