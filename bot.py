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
    laptop_apps,
    laptop_battery,
    laptop_lock,
    laptop_mute,
    laptop_playpause,
    laptop_screenshot,
    laptop_vol_down,
    laptop_vol_up,
    laptop_webcam,
    laptop_wifi,
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

# Persistent Bottom Reply Keyboard (Quick Access Buttons)
REPLY_KEYBOARD = {
    "keyboard": [
        [{"text": "📸 Screenshot"}, {"text": "📷 Webcam"}],
        [{"text": "🔋 Battery"}, {"text": "🎛️ Laptop Control"}],
        [{"text": "💻 Laptop Exec"}, {"text": "☁️ Cloud Server"}],
        [{"text": "📊 Status"}, {"text": "📱 Menu"}],
    ],
    "resize_keyboard": True,
    "is_persistent": True,
}


def get_laptop_control_keyboard() -> dict:
    """Full remote control keypad for physical laptop."""
    return {
        "inline_keyboard": [
            [
                {"text": "📸 Live Screenshot", "callback_data": "lap_screenshot"},
                {"text": "📷 Front Webcam", "callback_data": "lap_webcam"},
            ],
            [
                {"text": "🔋 Battery Status", "callback_data": "lap_battery"},
                {"text": "📶 Wi-Fi Status", "callback_data": "lap_wifi"},
            ],
            [
                {"text": "🔉 Vol -", "callback_data": "lap_vol_down"},
                {"text": "🔊 Vol +", "callback_data": "lap_vol_up"},
                {"text": "🔇 Mute", "callback_data": "lap_mute"},
                {"text": "⏯️ Play/Pause", "callback_data": "lap_playpause"},
            ],
            [
                {"text": "📱 Running Apps", "callback_data": "lap_apps"},
                {"text": "🔒 Lock Screen", "callback_data": "lap_lock"},
            ],
            [
                {"text": "🔙 Back to Main Menu", "callback_data": "btn_status"},
            ],
        ]
    }


def get_main_inline_keyboard() -> dict:
    """Inline Keyboard with interactive buttons."""
    return {
        "inline_keyboard": [
            [
                {"text": "🎛️ Live Laptop Controls", "callback_data": "lap_controls"},
                {"text": "📸 Live Screenshot", "callback_data": "lap_screenshot"},
            ],
            [
                {"text": "💻 Test Laptop", "callback_data": "btn_laptop"},
                {"text": "☁️ Test Cloud Server", "callback_data": "btn_cloud"},
            ],
            [
                {"text": "📊 Full Status", "callback_data": "btn_status"},
                {"text": "📁 Workspace Files", "callback_data": "btn_files"},
            ],
            [
                {"text": "⚡ Quick Diagnostics", "callback_data": "btn_test"},
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

    try:
        resp = requests.post(url, json=payload, timeout=20)
        res_json = resp.json()
        if res_json.get("ok"):
            return res_json.get("result", {}).get("message_id")
        else:
            payload.pop("parse_mode", None)
            resp2 = requests.post(url, json=payload, timeout=20)
            if resp2.json().get("ok"):
                return resp2.json().get("result", {}).get("message_id")
            logger.error(f"Failed to send message: {resp.text}")
    except Exception as e:
        logger.error(f"Error in tg_send_message: {e}")
    return None


def tg_edit_message(
    chat_id: int,
    message_id: int,
    new_text: str,
    reply_markup: Optional[dict] = None,
) -> None:
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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.debug(f"Could not edit message: {e}")


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
        {"command": "menu", "description": "📱 Interactive Control Panel & Buttons"},
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
        f"• **AI Model:** Google Gemini (`gemini-flash-lite-latest`)\n"
        f"• **Multimodal:** Vision / Screenshots & Document processing enabled\n"
        f"• **Saved Memory Facts:** {len(facts)}"
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
            if parsed.path == "/api/laptop/poll":
                record_heartbeat()
                task = get_pending_task()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "task": task}).encode("utf-8"))
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
        """Handle slash commands and persistent reply button clicks."""
        clean = text.strip()
        cmd = clean.split()[0].lower() if clean else ""

        # Start / Menu
        if cmd in ("/start", "/menu") or clean == "📱 Menu":
            cfg = get_runtime_config()
            is_new_owner = False
            if cfg.get("owner_user_id") is None:
                set_owner(user_id)
                is_new_owner = True

            welcome = (
                "👑 *Hermes Autonomous Agent Panel*\n\n"
                f"{'✅ Registered as Primary Owner.' if is_new_owner else '⚡ System Ready & Active.'}\n"
                "Buttons use karein, photo/document bhejein, ya koi bhi task type karein:"
            )
            tg_send_message(
                chat_id,
                welcome,
                reply_markup=get_main_inline_keyboard(),
            )
            tg_send_message(
                chat_id,
                "👇 Quick actions bar ready:",
                reply_markup=REPLY_KEYBOARD,
            )
            return True

        # Screenshot
        if clean in ("📸 Screenshot", "/screenshot"):
            tg_send_message(chat_id, "📸 Laptop screen capture ho rahi hai...")
            res = laptop_screenshot()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
            return True

        # Webcam
        if clean in ("📷 Webcam", "/webcam"):
            tg_send_message(chat_id, "📷 Webcam photo capture ho rahi hai...")
            res = laptop_webcam()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
            return True

        # Battery
        if clean in ("🔋 Battery", "/battery"):
            res = laptop_battery()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
            return True

        # Laptop Control Panel
        if clean in ("🎛️ Laptop Control", "/controls"):
            tg_send_message(
                chat_id,
                "🎛️ *Laptop Live Remote Control Panel:*\nNiche diye buttons se volume, screen, battery, aur apps control karein:",
                reply_markup=get_laptop_control_keyboard(),
            )
            return True

        # Laptop Exec
        if clean in ("💻 Laptop Exec", "/laptop"):
            status = "ONLINE 🟢 (Connected)" if is_laptop_online() else "OFFLINE 🔴 (Laptop band hai)"
            msg = (
                f"💻 *Laptop Execution Mode*\n• **Status:** {status}\n\n"
                "Task bhejein, laptop online hone par **laptop par run hoga**.\n"
                "Agar laptop band hua to **automatic ☁️ Cloud Server par fallback hoga**!"
            )
            tg_send_message(chat_id, msg, reply_markup=get_main_inline_keyboard())
            return True

        # Cloud Server
        if clean in ("☁️ Cloud Server", "/server", "/cloud"):
            msg = (
                "☁️ *24/7 Cloud Server Mode*\n• **Status:** ONLINE 🟢 (Render)\n\n"
                "Task bhejein, seedhe 24/7 Cloud Server par run hoga."
            )
            tg_send_message(chat_id, msg, reply_markup=get_main_inline_keyboard())
            return True

        # Status
        if cmd == "/status" or clean in ("📊 Status", "📊 Full Status"):
            tg_send_message(
                chat_id,
                get_status_text(),
                reply_markup=get_main_inline_keyboard(),
            )
            return True

        # Files
        if cmd == "/files" or clean == "📁 Files":
            tg_send_message(
                chat_id,
                get_files_text(),
                reply_markup=get_main_inline_keyboard(),
            )
            return True

        # Quick Test
        if cmd == "/test" or clean == "⚡ Quick Test":
            tg_send_message(
                chat_id,
                get_quick_test_text(),
                reply_markup=get_main_inline_keyboard(),
            )
            return True

        # Reset Memory
        if cmd == "/reset" or clean == "🧹 Reset":
            session_id = f"tg_{chat_id}"
            clear_history(session_id)
            tg_send_message(
                chat_id,
                "🧹 Context clear ho gaya! Naya conversation shuru hai.",
                reply_markup=get_main_inline_keyboard(),
            )
            return True

        # 24/7 Hosting Guide
        if cmd == "/vps" or clean == "🌐 24/7 Hosting":
            tg_send_message(
                chat_id,
                get_vps_guide_text(),
                reply_markup=get_main_inline_keyboard(),
            )
            return True

        # Help
        if cmd == "/help" or clean == "💡 Help":
            tg_send_message(
                chat_id,
                get_help_text(),
                reply_markup=get_main_inline_keyboard(),
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
                        reply_markup=REPLY_KEYBOARD,
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
        chat_id = message.get("chat", {}).get("id")
        data = cq.get("data", "")

        if not is_user_allowed(user_id, username=username):
            logger.warning(f"Unauthorized callback query from {user_id} (@{username})")
            tg_answer_callback_query(
                cq_id, "⛔ Access Denied: Locked to @kissbilla2.", show_alert=True
            )
            return

        tg_answer_callback_query(cq_id)

        if data == "lap_screenshot":
            tg_send_message(chat_id, "📸 Laptop screen capture ho rahi hai...")
            res = laptop_screenshot()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_webcam":
            tg_send_message(chat_id, "📷 Front camera photo capture ho rahi hai...")
            res = laptop_webcam()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_battery":
            res = laptop_battery()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_vol_up":
            res = laptop_vol_up()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_vol_down":
            res = laptop_vol_down()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_mute":
            res = laptop_mute()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_playpause":
            res = laptop_playpause()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_apps":
            res = laptop_apps()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_lock":
            res = laptop_lock()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_wifi":
            res = laptop_wifi()
            tg_send_message(chat_id, res, reply_markup=get_laptop_control_keyboard())
        elif data == "lap_controls":
            tg_send_message(
                chat_id,
                "🎛️ *Laptop Live Control Panel:*\nButtons se direct laptop control karein:",
                reply_markup=get_laptop_control_keyboard(),
            )
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
            tg_send_message(chat_id, msg, reply_markup=get_main_inline_keyboard())
        elif data == "btn_cloud":
            res = execute_bash("uname -a && uptime -p && free -h")
            msg = f"☁️ *24/7 Render Cloud Server (Online 🟢):*\n```\n{res}\n```\n✅ Cloud Server execution verified!"
            tg_send_message(chat_id, msg, reply_markup=get_main_inline_keyboard())
        elif data == "btn_status":
            tg_send_message(chat_id, get_status_text(), reply_markup=get_main_inline_keyboard())
        elif data == "btn_files":
            tg_send_message(chat_id, get_files_text(), reply_markup=get_main_inline_keyboard())
        elif data == "btn_test":
            tg_send_message(chat_id, get_quick_test_text(), reply_markup=get_main_inline_keyboard())
        elif data == "btn_reset":
            clear_history(f"tg_{chat_id}")
            tg_send_message(
                chat_id,
                "🧹 Context clear ho gaya!",
                reply_markup=get_main_inline_keyboard(),
            )
        elif data == "btn_vps":
            tg_send_message(chat_id, get_vps_guide_text(), reply_markup=get_main_inline_keyboard())
        elif data == "btn_help":
            tg_send_message(chat_id, get_help_text(), reply_markup=get_main_inline_keyboard())

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
                tg_send_message(chat_id, result, reply_markup=REPLY_KEYBOARD)
            except Exception as e:
                logger.error(f"Error analyzing image: {e}")
                tg_send_message(chat_id, f"❌ Error: {str(e)}")
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
                tg_send_message(chat_id, "❌ Error: Document download nahi ho payi.")
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
                tg_send_message(chat_id, result, reply_markup=REPLY_KEYBOARD)
            except Exception as e:
                logger.error(f"Error analyzing document: {e}")
                tg_send_message(chat_id, f"❌ Error: {str(e)}")
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
            tg_send_message(
                chat_id,
                result,
                reply_markup=REPLY_KEYBOARD,
            )
        except Exception as e:
            logger.error(f"Error executing agent task: {e}")
            tg_send_message(chat_id, f"❌ Error: {str(e)}")

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
