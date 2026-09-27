"""
Hermes Local Laptop Runner Node
Runs in background on user's physical laptop.
Allows the 24/7 Render Cloud Telegram Bot to execute bash commands, capture live
screenshots, webcam snapshots, check battery, control volume/media, simulate keystrokes
for Sandbox/Terminal approvals, monitor Antigravity AI tasks, record audio, and manage power.
"""

import glob
import json
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Optional
import requests

logging.basicConfig(
    format="%(asctime)s - [LaptopNode] - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("LaptopNode")

from human_gui import (
    human_open_app,
    human_mouse_click,
    human_mouse_move,
    human_mouse_scroll,
    human_type_text,
    inspect_screen_vision,
    analyze_screen_and_click,
    capture_desktop_image,
)

CLOUD_URL = os.getenv("HERMES_CLOUD_URL", "https://hermes-bot-kqv8.onrender.com").rstrip("/")
SECRET = os.getenv("LAPTOP_BRIDGE_SECRET", "hermes_secret_8616271645")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8954487031:AAEv9-RzsecVcnJyVfd3pfEOYYfiBGh9Fzg")
OWNER_CHAT_ID = 8616271645
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_x11_env() -> dict:
    """Construct environment with active DISPLAY, WAYLAND_DISPLAY, and dynamic Mutter Xwayland auth."""
    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    env["WAYLAND_DISPLAY"] = "wayland-0"
    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    mutter_auths = glob.glob("/run/user/1000/.mutter-Xwaylandauth*")
    if mutter_auths:
        env["XAUTHORITY"] = mutter_auths[0]
    elif os.path.exists("/home/mrx/.Xauthority"):
        env["XAUTHORITY"] = "/home/mrx/.Xauthority"
    return env


camera_lock = threading.Lock()
cctv_pause_event = threading.Event()


def acquire_camera_lock(timeout: float = 10.0) -> bool:
    """Pause CCTV loop and acquire exclusive webcam access."""
    cctv_pause_event.set()
    return camera_lock.acquire(timeout=timeout)


def release_camera_lock() -> None:
    """Release exclusive webcam access and resume CCTV loop."""
    try:
        camera_lock.release()
    except RuntimeError:
        pass
    cctv_pause_event.clear()



def send_tg_msg(text: str, reply_markup: Optional[dict] = None) -> bool:
    """Send text message directly to owner on Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": OWNER_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(url, json=payload, timeout=20)
        return resp.status_code == 200 and resp.json().get("ok")
    except Exception as e:
        logger.error(f"Error sending text to Telegram: {e}")
        return False


def send_tg_photo(file_path: str, caption: str, reply_markup: Optional[dict] = None) -> bool:
    """Send photo directly to the owner on Telegram."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {"chat_id": OWNER_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                data=data,
                files={"photo": f},
                timeout=25,
            )
            return resp.status_code == 200 and resp.json().get("ok")
    except Exception as e:
        logger.error(f"Error sending photo to Telegram: {e}")
        return False


def send_tg_voice(file_path: str, caption: str) -> bool:
    """Send audio/voice note directly to the owner on Telegram."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVoice"
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": OWNER_CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
                files={"voice": f},
                timeout=30,
            )
            return resp.status_code == 200 and resp.json().get("ok")
    except Exception as e:
        logger.error(f"Error sending voice note to Telegram: {e}")
        return False


def send_tg_video(file_path: str, caption: str, reply_markup: Optional[dict] = None) -> bool:
    """Send MP4 video clip directly to the owner on Telegram."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    data = {"chat_id": OWNER_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                data=data,
                files={"video": f},
                timeout=40,
            )
            return resp.status_code == 200 and resp.json().get("ok")
    except Exception as e:
        logger.error(f"Error sending video to Telegram: {e}")
        return False


def get_latest_transcript_path() -> Optional[str]:
    """Find the most recently modified Antigravity transcript file."""
    paths = glob.glob("/home/mrx/.gemini/antigravity/brain/*/.system_generated/logs/transcript.jsonl")
    if not paths:
        return None
    return max(paths, key=os.path.getmtime)


def get_antigravity_status() -> str:
    """Read recent transcript logs and summarize current AI task status."""
    path = get_latest_transcript_path()
    if not path or not os.path.exists(path):
        return "🤖 *Antigravity AI Status:*\nTranscript log file abhi nahi mila."

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f if l.strip()]

        if not lines:
            return "🤖 *Antigravity AI Status:*\nSession log empty hai."

        total_steps = len(lines)
        last_obj = json.loads(lines[-1])
        source = last_obj.get("source", "UNKNOWN")
        step_type = last_obj.get("type", "UNKNOWN")
        status = last_obj.get("status", "UNKNOWN")
        tool_calls = last_obj.get("tool_calls", [])

        recent_tool = None
        for l in reversed(lines[-10:]):
            try:
                d = json.loads(l)
                if d.get("tool_calls"):
                    recent_tool = d["tool_calls"][0].get("name")
                    break
            except Exception:
                pass

        summary = f"🤖 *Antigravity AI Live Status:*\n"
        summary += f"• **Total Steps:** `{total_steps}`\n"
        summary += f"• **Last Activity:** Source `{source}` | Type `{step_type}`\n"
        summary += f"• **Status:** `{status}`\n"
        if recent_tool:
            summary += f"• **Recent Tool:** `{recent_tool}`\n"

        if step_type == "PLANNER_RESPONSE" and not tool_calls:
            summary += "\n✅ **Task Complete:** Agent has finished answering. Waiting for user input."
        elif "sandbox" in lines[-1].lower() or "bypasssandbox" in lines[-1].lower():
            summary += "\n⚠️ **Approval Required:** Sandbox permission or prompt waiting."
        else:
            summary += "\n⚡ **Active:** Agent is working or executing tools."

        return summary
    except Exception as e:
        return f"🤖 Error reading Antigravity status: {e}"


def execute_action(cmd: str) -> str:
    """Handle special live control actions or general shell commands."""
    clean = cmd.strip()

    # 1. Live Desktop Screenshot
    if clean == "__ACTION_SCREENSHOT__":
        img_path = "/tmp/hermes_screenshot.png"
        captured = capture_desktop_image(img_path)
        if captured and os.path.exists(captured) and os.path.getsize(captured) > 5000:
            if send_tg_photo(captured, "📸 *Laptop Live Desktop Screenshot*"):
                return "✅ Live Desktop screenshot captured & sent to chat!"
        return "❌ Screenshot capture failed: Display session inactive ya screen locked."

    # 2. Live Front Camera Snapshot
    if clean == "__ACTION_WEBCAM__":
        cam_path = "/tmp/hermes_webcam.jpg"
        acquired = acquire_camera_lock(timeout=6.0)
        try:
            time.sleep(0.3)
            os.system(f"ffmpeg -y -f v4l2 -i /dev/video0 -vframes 1 {cam_path} 2>/dev/null")
        finally:
            if acquired:
                release_camera_lock()
        if send_tg_photo(cam_path, "📷 *Laptop Live Front Camera Snapshot*"):
            return "✅ Live Webcam snapshot captured & sent to chat!"
        return "❌ Webcam snapshot failed (camera busy or not accessible)."

    # 3. Live Battery Status
    if clean == "__ACTION_BATTERY__":
        try:
            out = subprocess.check_output(
                "upower -i $(upower -e | grep 'BAT') 2>/dev/null | grep -E 'state|percentage|time to'",
                shell=True,
                text=True,
            ).strip()
            if out:
                return f"🔋 *Live Laptop Battery:*\n```\n{out}\n```"
        except Exception:
            pass
        return "🔋 Battery information unavailable."

    # 4. Volume Up
    if clean == "__ACTION_VOL_UP__":
        os.system("pactl set-sink-volume @DEFAULT_SINK@ +10% 2>/dev/null")
        return "🔊 Volume badha diya (+10%)"

    # 5. Volume Down
    if clean == "__ACTION_VOL_DOWN__":
        os.system("pactl set-sink-volume @DEFAULT_SINK@ -10% 2>/dev/null")
        return "🔉 Volume kam kar diya (-10%)"

    # 6. Mute Toggle
    if clean == "__ACTION_MUTE__":
        os.system("pactl set-sink-mute @DEFAULT_SINK@ toggle 2>/dev/null")
        return "🔇 Mute toggle kar diya."

    # 7. Media Play/Pause
    if clean == "__ACTION_PLAYPAUSE__":
        os.system("playerctl play-pause 2>/dev/null")
        return "⏯️ Media Play/Pause command sent."

    # 8. Lock Laptop Screen
    if clean == "__ACTION_LOCK__":
        os.system("xdg-screensaver lock 2>/dev/null || loginctl lock-session 2>/dev/null")
        return "🔒 Laptop screen lock kar di gayi!"

    # 9. Wi-Fi Status
    if clean == "__ACTION_WIFI__":
        try:
            out = subprocess.check_output(
                "nmcli -t -f active,ssid,signal dev wifi 2>/dev/null | grep '^yes'",
                shell=True,
                text=True,
            ).strip()
            ip_out = subprocess.check_output("hostname -I 2>/dev/null", shell=True, text=True).strip()
            return f"📶 *Wi-Fi & Network:*\n• Connection: `{out}`\n• Local IP: `{ip_out}`"
        except Exception as e:
            return f"📶 Wi-Fi status: {e}"

    # 10. Top Running Apps
    if clean == "__ACTION_APPS__":
        try:
            out = subprocess.check_output(
                "ps -eo comm,%cpu,%mem --sort=-%cpu | head -n 9",
                shell=True,
                text=True,
            ).strip()
            return f"📱 *Top Running Apps (by CPU):*\n```\n{out}\n```"
        except Exception as e:
            return f"Error reading apps: {e}"

    # 11. Antigravity & Sandbox Keystroke Simulation
    if clean == "__ACTION_KEY_ENTER__":
        env = get_x11_env()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], env=env)
        time.sleep(0.5)
        confirm_path = "/tmp/hermes_key_confirm.png"
        capture_desktop_image(confirm_path)
        if os.path.exists(confirm_path) and os.path.getsize(confirm_path) > 0:
            send_tg_photo(confirm_path, "⏎ *Approve (Enter) Sent!* Current screen state:")
        return "⏎ Enter key sent to laptop!"

    if clean == "__ACTION_KEY_Y__":
        env = get_x11_env()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "y", "Return"], env=env)
        time.sleep(0.5)
        confirm_path = "/tmp/hermes_key_confirm.png"
        capture_desktop_image(confirm_path)
        if os.path.exists(confirm_path) and os.path.getsize(confirm_path) > 0:
            send_tg_photo(confirm_path, "🟢 *Send 'y' Sent!* Current screen state:")
        return "🟢 'y' + Enter sent to laptop!"

    if clean == "__ACTION_KEY_N__":
        env = get_x11_env()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "n", "Return"], env=env)
        time.sleep(0.5)
        confirm_path = "/tmp/hermes_key_confirm.png"
        capture_desktop_image(confirm_path)
        if os.path.exists(confirm_path) and os.path.getsize(confirm_path) > 0:
            send_tg_photo(confirm_path, "🔴 *Send 'n' Sent!* Current screen state:")
        return "🔴 'n' + Enter sent to laptop!"

    if clean == "__ACTION_KEY_CTRLC__":
        env = get_x11_env()
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+c"], env=env)
        time.sleep(0.5)
        confirm_path = "/tmp/hermes_key_confirm.png"
        capture_desktop_image(confirm_path)
        if os.path.exists(confirm_path) and os.path.getsize(confirm_path) > 0:
            send_tg_photo(confirm_path, "🛑 *Ctrl+C Sent!* Current screen state:")
        return "🛑 Ctrl+C sent to laptop!"

    if clean.startswith("__ACTION_TYPE__"):
        text_to_type = clean[len("__ACTION_TYPE__"):].strip()
        env = get_x11_env()
        subprocess.run(["xdotool", "type", "--delay", "20", text_to_type], env=env)
        return f"⌨️ Typed text on active window: `{text_to_type}`"

    # 12. Antigravity AI Status
    if clean == "__ACTION_AI_STATUS__":
        return get_antigravity_status()

    # 13. Audio / Mic Recording
    if clean.startswith("__ACTION_MIC__"):
        sec = 10
        try:
            sec_str = clean[len("__ACTION_MIC__"):].strip()
            if sec_str.isdigit():
                sec = int(sec_str)
        except Exception:
            sec = 10
        ogg_path = "/tmp/hermes_mic.ogg"
        # Direct PulseAudio/PipeWire capture with Opus encoding
        os.system(f"ffmpeg -y -f pulse -i default -t {sec} -c:a libopus -b:a 32k {ogg_path} 2>/dev/null")
        if send_tg_voice(ogg_path, f"🎙️ *{sec}s Laptop Room Audio Recording*"):
            return f"✅ Recorded {sec}s audio and sent as voice note!"
        return "❌ Mic recording failed (check microphone device)."

    # 14. Music Playback / Stop
    if clean == "__ACTION_STOP_MUSIC__":
        os.system("killall mpv 2>/dev/null")
        return "⏹️ Music playback stopped."

    if clean.startswith("__ACTION_PLAY_MUSIC__"):
        query = clean[len("__ACTION_PLAY_MUSIC__"):].strip()
        os.system("killall mpv 2>/dev/null")
        os.system(f'nohup mpv --no-video "ytdl://ytsearch1:{query}" >/dev/null 2>&1 &')
        return f"🎵 Playing '{query}' in background via mpv!"

    # 15. Clipboard Sync
    if clean.startswith("__ACTION_CLIPBOARD__"):
        clip_text = clean[len("__ACTION_CLIPBOARD__"):].strip()
        env = get_x11_env()
        if clip_text:
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, env=env)
            p.communicate(input=clip_text.encode("utf-8"))
            return f"📋 Copied to laptop clipboard: `{clip_text}`"
        else:
            try:
                out = subprocess.check_output(["xclip", "-o", "-selection", "clipboard"], env=env, text=True).strip()
                return f"📋 *Laptop Clipboard Content:*\n```\n{out or '(Empty)'}\n```"
            except Exception:
                return "📋 Clipboard is empty or inaccessible."

    # 16. Text-to-Speech (TTS)
    if clean.startswith("__ACTION_SPEAK__"):
        speak_text = clean[len("__ACTION_SPEAK__"):].strip().replace('"', '\\"')
        os.system(f'spd-say "{speak_text}" 2>/dev/null || espeak "{speak_text}" 2>/dev/null')
        return f"🗣️ Spoken on laptop: \"{speak_text}\""

    # 17. Popup Notification
    if clean.startswith("__ACTION_POPUP__"):
        raw = clean[len("__ACTION_POPUP__"):].strip()
        parts = raw.split("|||", 1)
        title = parts[0] if len(parts) > 1 else "Telegram Notice"
        body = parts[1] if len(parts) > 1 else raw
        env = get_x11_env()
        subprocess.run(["notify-send", title, body], env=env)
        return f"📢 Notification sent to laptop screen: *{title}*"

    # 18. Power Management
    if clean == "__ACTION_POWER_SLEEP__":
        os.system("systemctl suspend 2>/dev/null")
        return "💤 Laptop sleeping..."

    if clean == "__ACTION_POWER_REBOOT__":
        os.system("sudo reboot 2>/dev/null || systemctl reboot 2>/dev/null")
        return "🔄 Laptop rebooting..."

    if clean == "__ACTION_POWER_SHUTDOWN__":
        os.system("sudo poweroff 2>/dev/null || systemctl poweroff 2>/dev/null")
        return "⛔ Laptop powering off..."

    # 19. 10s Webcam Video Recording with Audio
    if clean == "__ACTION_WEBCAM_VIDEO__":
        clip_path = "/tmp/hermes_webcam_clip.mp4"
        acquired = acquire_camera_lock(timeout=8.0)
        try:
            time.sleep(0.4)
            # Try video + mic audio first
            ret = os.system(
                f"ffmpeg -y -f v4l2 -i /dev/video0 -f pulse -i default -t 10 -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac {clip_path} 2>/dev/null"
            )
            if ret != 0 or not os.path.exists(clip_path) or os.path.getsize(clip_path) == 0:
                # Fallback to video only
                os.system(
                    f"ffmpeg -y -f v4l2 -i /dev/video0 -t 10 -c:v libx264 -preset ultrafast -pix_fmt yuv420p {clip_path} 2>/dev/null"
                )
        finally:
            if acquired:
                release_camera_lock()

        if send_tg_video(clip_path, "🎥 *10-Second Live Webcam Video Clip*"):
            return "✅ 10s Webcam video clip captured & sent to chat!"
        return "❌ Video capture failed (webcam busy or not accessible)."

    # 20. CCTV Motion Mode Toggle
    if clean == "__ACTION_CCTV_TOGGLE__":
        global CCTV_ENABLED
        CCTV_ENABLED = not CCTV_ENABLED
        state_str = "ACTIVATED 🟢 (Motion monitoring chalu)" if CCTV_ENABLED else "DEACTIVATED 🔴 (CCTV band)"
        return f"👁️ *CCTV Motion Watcher:* {state_str}"

    # 21. Loud Alarm Siren
    if clean == "__ACTION_ALARM__":
        os.system("pactl set-sink-volume @DEFAULT_SINK@ 100% 2>/dev/null")
        os.system("pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null")
        siren_file = os.path.join(WORKSPACE_DIR, "siren.wav")
        if not os.path.exists(siren_file):
            siren_file = "/tmp/siren.wav"
        os.system(f"killall mpv 2>/dev/null")
        os.system(f'nohup mpv --volume=100 --loop "{siren_file}" >/dev/null 2>&1 &')
        return "🚨 *LOUD ALARM ACTIVATED!* 🚨\nLaptop volume 100% karke siren baj raha hai!\nBand karne ke liye `⏹️ Stop Alarm` dabayein."

    if clean == "__ACTION_STOP_ALARM__":
        os.system("killall mpv 2>/dev/null")
        return "⏹️ Alarm siren stopped."

    # 22. Find My Laptop (Geo-Location)
    if clean == "__ACTION_LOCATION__":
        try:
            r = requests.get("https://ipinfo.io/json", timeout=6).json()
            ip = r.get("ip", "Unknown")
            city = r.get("city", "Unknown")
            region = r.get("region", "Unknown")
            country = r.get("country", "IN")
            loc = r.get("loc", "")
            org = r.get("org", "")
            map_link = f"https://maps.google.com/?q={loc}" if loc else "N/A"
            return (
                "📍 *Find My Laptop - Live Location:*\n\n"
                f"• **Public IP:** `{ip}`\n"
                f"• **City/Region:** {city}, {region} ({country})\n"
                f"• **ISP/Network:** `{org}`\n"
                f"• **Coordinates:** `{loc}`\n\n"
                f"🗺️ [Google Maps par Location Dekhein]({map_link})"
            )
        except Exception as e:
            return f"📍 Location lookup error: {e}"

    # 23. Ghost Mode (Stealth Screen Off) & Screen ON
    if clean == "__ACTION_GHOST_MODE__":
        # Native GNOME Mutter DisplayConfig DPMS off (Wayland)
        subprocess.run([
            "busctl", "--user", "set-property",
            "org.gnome.Mutter.DisplayConfig",
            "/org/gnome/Mutter/DisplayConfig",
            "org.gnome.Mutter.DisplayConfig",
            "PowerSaveMode", "i", "3"
        ], capture_output=True)
        env = get_x11_env()
        subprocess.run(["xset", "dpms", "force", "off"], env=env, stderr=subprocess.DEVNULL)
        return (
            "🕶️ *Ghost Mode ACTIVATED!* 🕶️\n\n"
            "• Laptop screen turn OFF (blank) ho gayi hai.\n"
            "• Sabhi background downloads, Antigravity AI aur terminal active hain!\n\n"
            "💡 Wapas screen ON karne ke liye: `☀️ Screen ON` button dabayein ya mouse hilayein."
        )

    if clean == "__ACTION_SCREEN_ON__":
        # Native GNOME Mutter DisplayConfig DPMS on (Wayland)
        subprocess.run([
            "busctl", "--user", "set-property",
            "org.gnome.Mutter.DisplayConfig",
            "/org/gnome/Mutter/DisplayConfig",
            "org.gnome.Mutter.DisplayConfig",
            "PowerSaveMode", "i", "0"
        ], capture_output=True)
        env = get_x11_env()
        subprocess.run(["xset", "dpms", "force", "on"], env=env, stderr=subprocess.DEVNULL)
        return "☀️ *Laptop Display is ON!* Screen wapas active ho gayi hai."

    # 24. Remote URL Launcher
    if clean.startswith("__ACTION_OPEN_URL__"):
        url = clean[len("__ACTION_OPEN_URL__"):].strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        env = get_x11_env()
        subprocess.Popen(["xdg-open", url], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"🌐 *Opened in Laptop Browser:*\n`{url}`"

    # 25. Human-Like App Opening
    if clean.startswith("__ACTION_HUMAN_OPEN_APP__"):
        app_name = clean[len("__ACTION_HUMAN_OPEN_APP__"):].strip()
        res = human_open_app(app_name)
        if os.path.exists("/tmp/hermes_app_opened.png"):
            send_tg_photo("/tmp/hermes_app_opened.png", f"🖥️ *Opened '{app_name}' like a human!*")
        return res

    # 26. Human-Like Mouse Click
    if clean.startswith("__ACTION_HUMAN_CLICK__"):
        payload = clean[len("__ACTION_HUMAN_CLICK__"):].strip()
        parts = payload.split("|")
        x = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else None
        y = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        btn = parts[2] if len(parts) > 2 else "left"
        clicks = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
        res = human_mouse_click(x, y, button=btn, clicks=clicks)
        img_path = "/tmp/hermes_mouse_click.png"
        capture_desktop_image(img_path)
        if os.path.exists(img_path):
            send_tg_photo(img_path, f"🖱️ {res}")
        return res

    # 27. Human-Like Mouse Move
    if clean.startswith("__ACTION_HUMAN_MOVE__"):
        payload = clean[len("__ACTION_HUMAN_MOVE__"):].strip()
        parts = payload.split("|")
        x = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 500
        y = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 500
        human_mouse_move(x, y)
        return f"🖱️ Mouse cursor smoothly glided to ({x}, {y})!"

    # 28. Human-Like Typing
    if clean.startswith("__ACTION_HUMAN_TYPE__"):
        payload = clean[len("__ACTION_HUMAN_TYPE__"):].strip()
        parts = payload.split("|||", 1)
        text_str = parts[0]
        press_enter = (parts[1].lower() == "true") if len(parts) > 1 else False
        return human_type_text(text_str, press_enter=press_enter)

    # 29. Human-Like Mouse Scroll
    if clean.startswith("__ACTION_HUMAN_SCROLL__"):
        payload = clean[len("__ACTION_HUMAN_SCROLL__"):].strip()
        parts = payload.split("|")
        direction = parts[0] if len(parts) > 0 else "down"
        amount = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
        return human_mouse_scroll(direction=direction, amount=amount)

    # 30. Visual Screen Inspection (AI Vision)
    if clean.startswith("__ACTION_SCREEN_INSPECT__"):
        query = clean[len("__ACTION_SCREEN_INSPECT__"):].strip()
        if not query:
            query = "Describe what is currently visible on screen"
        res = inspect_screen_vision(query)
        if os.path.exists("/tmp/hermes_screenshot.png"):
            send_tg_photo("/tmp/hermes_screenshot.png", "👁️ *Screen Vision Analysis:*")
        return res

    # 31. Visual Screen Interact (Find Element & Click)
    if clean.startswith("__ACTION_SCREEN_VISION_CLICK__"):
        payload = clean[len("__ACTION_SCREEN_VISION_CLICK__"):].strip()
        parts = payload.split("|||", 1)
        target = parts[0]
        instr = parts[1] if len(parts) > 1 else ""
        res = analyze_screen_and_click(target, instruction=instr)
        if os.path.exists("/tmp/hermes_clicked_state.png"):
            send_tg_photo("/tmp/hermes_clicked_state.png", f"🎯 *Clicked '{target}' like a human!*")
        return res

    # General Shell Command
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=WORKSPACE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        output_parts = []
        if proc.stdout.strip():
            output_parts.append(proc.stdout.strip())
        if proc.stderr.strip():
            output_parts.append(f"STDERR:\n{proc.stderr.strip()}")
        out_str = "\n".join(output_parts)
        return out_str if out_str else "(Command finished with empty output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (60s)."
    except Exception as e:
        return f"Error executing local command: {e}"


def antigravity_watcher_thread():
    """Background watcher for Antigravity AI tasks and Sandbox prompt detection."""
    logger.info("Antigravity Watcher thread active.")
    last_file = None
    last_line_count = 0
    last_alert_time = 0.0

    init_path = get_latest_transcript_path()
    if init_path and os.path.exists(init_path):
        try:
            with open(init_path, "r", encoding="utf-8", errors="ignore") as f:
                last_line_count = sum(1 for _ in f)
            last_file = init_path
            logger.info(f"Antigravity watcher initialized at line {last_line_count} of {last_file}")
        except Exception:
            pass

    sandbox_keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve (Enter)", "callback_data": "lap_key_enter"},
                {"text": "🟢 Send 'y'", "callback_data": "lap_key_y"},
            ],
            [
                {"text": "🔴 Send 'n'", "callback_data": "lap_key_n"},
                {"text": "🛑 Ctrl+C", "callback_data": "lap_key_ctrlc"},
            ],
            [
                {"text": "📸 Screen Peek", "callback_data": "lap_screenshot"},
                {"text": "🤖 AI Status", "callback_data": "lap_ai_status"},
            ],
        ]
    }

    done_keyboard = {
        "inline_keyboard": [
            [
                {"text": "📸 Screen Peek", "callback_data": "lap_screenshot"},
                {"text": "🤖 AI Status", "callback_data": "lap_ai_status"},
            ],
            [
                {"text": "🎛️ Laptop Controls", "callback_data": "lap_controls"},
            ],
        ]
    }

    while True:
        try:
            time.sleep(3)
            current_path = get_latest_transcript_path()
            if not current_path or not os.path.exists(current_path):
                continue

            if current_path != last_file:
                last_file = current_path
                with open(current_path, "r", encoding="utf-8", errors="ignore") as f:
                    last_line_count = sum(1 for _ in f)
                continue

            with open(current_path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()

            if len(all_lines) > last_line_count:
                new_lines = all_lines[last_line_count:]
                last_line_count = len(all_lines)

                now = time.time()
                for line in new_lines:
                    line_lower = line.lower()

                    if ("bypasssandbox" in line_lower or "sandbox" in line_lower) and (now - last_alert_time > 15):
                        last_alert_time = now
                        img_path = "/tmp/hermes_prompt_screen.png"
                        capture_desktop_image(img_path)
                        alert_msg = (
                            "⚠️ *Antigravity Alert: Sandbox / Approval Required!*\n\n"
                            "Terminal ya tool sandbox confirmation mang raha hai.\n"
                            "Niche diye buttons se direct approve karein:"
                        )
                        if os.path.exists(img_path) and os.path.getsize(img_path) > 0:
                            send_tg_photo(img_path, alert_msg, reply_markup=sandbox_keyboard)
                        else:
                            send_tg_msg(alert_msg, reply_markup=sandbox_keyboard)
                        break

                    try:
                        d = json.loads(line)
                        if d.get("source") == "MODEL" and d.get("type") == "PLANNER_RESPONSE":
                            tool_calls = d.get("tool_calls", [])
                            content = d.get("content")
                            if content and not tool_calls and (now - last_alert_time > 15):
                                last_alert_time = now
                                done_msg = (
                                    "✅ *Antigravity: Code Task Completed!*\n\n"
                                    f"Summary:\n_{str(content)[:250]}..._\n\n"
                                    "Laptop screen dekhne ya controls use karne ke liye buttons dabayein:"
                                )
                                send_tg_msg(done_msg, reply_markup=done_keyboard)
                                break
                    except Exception:
                        pass

        except Exception as e:
            logger.debug(f"Watcher error: {e}")
            time.sleep(3)


CCTV_ENABLED = False


def intruder_watcher_thread() -> None:
    """Background listener for failed password attempts via journalctl."""
    logger.info("Intruder Trap (Chor Pakdo) watcher active.")
    last_intruder_time = 0.0

    intruder_keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚨 Sound Alarm", "callback_data": "lap_alarm"},
                {"text": "🔒 Lock Screen", "callback_data": "lap_lock"},
            ],
            [
                {"text": "🎥 Record 10s Video", "callback_data": "lap_video"},
                {"text": "📍 Find Location", "callback_data": "lap_location"},
            ],
        ]
    }

    try:
        proc = subprocess.Popen(
            ["journalctl", "-f", "-n", "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            if "authentication failure" in line.lower() or "auth failure" in line.lower():
                now = time.time()
                if now - last_intruder_time > 10:
                    last_intruder_time = now
                    logger.warning("🚨 Intruder authentication failure detected!")
                    img_path = "/tmp/hermes_intruder.jpg"
                    acquired = acquire_camera_lock(timeout=4.0)
                    try:
                        time.sleep(0.3)
                        os.system(f"ffmpeg -y -f v4l2 -i /dev/video0 -vframes 1 {img_path} 2>/dev/null")
                    finally:
                        if acquired:
                            release_camera_lock()
                    time_str = time.strftime("%Y-%m-%d %H:%M:%S")
                    caption = (
                        "🚨 *INTRUDER ALERT! (Chor Pakdo)* 🚨\n\n"
                        "Laptop par kisi ne **galat password** dala hai!\n"
                        f"⏰ *Time:* `{time_str}`\n"
                        "📍 *Activity:* Lock Screen / Login Failure\n\n"
                        "Action lene ke liye buttons dabayein:"
                    )
                    if os.path.exists(img_path):
                        send_tg_photo(img_path, caption, reply_markup=intruder_keyboard)
                    else:
                        send_tg_msg(caption, reply_markup=intruder_keyboard)
    except Exception as e:
        logger.error(f"Intruder watcher exception: {e}")


def cctv_watcher_thread() -> None:
    """Background motion detector using OpenCV webcam differencing."""
    global CCTV_ENABLED
    logger.info("CCTV Motion Watcher thread ready.")
    try:
        import cv2
    except ImportError:
        logger.warning("OpenCV (cv2) not available for CCTV watcher.")
        return

    last_motion_alert = 0.0

    while True:
        try:
            if not CCTV_ENABLED:
                time.sleep(2)
                continue

            if cctv_pause_event.is_set():
                time.sleep(1)
                continue

            if not camera_lock.acquire(blocking=False):
                time.sleep(1)
                continue

            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                camera_lock.release()
                time.sleep(3)
                continue

            # Warmup frame to avoid sensor auto-exposure difference
            cap.read()
            ret, frame1 = cap.read()
            time.sleep(0.4)
            ret, frame2 = cap.read()
            cap.release()
            camera_lock.release()

            if not ret or frame1 is None or frame2 is None:
                time.sleep(1.5)
                continue

            diff = cv2.absdiff(frame1, frame2)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (21, 21), 0)
            _, thresh = cv2.threshold(blur, 25, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            motion = False
            for contour in contours:
                if cv2.contourArea(contour) > 4000:
                    motion = True
                    break

            if motion and (time.time() - last_motion_alert > 15):
                last_motion_alert = time.time()
                motion_path = "/tmp/hermes_cctv_motion.jpg"
                cv2.imwrite(motion_path, frame2)
                time_str = time.strftime("%H:%M:%S")
                send_tg_photo(
                    motion_path,
                    f"👁️ *CCTV ALERT! Motion Detected in Room!* 🏃\nRoom me movement detect hua hai!\n⏰ *Time:* `{time_str}`"
                )

            time.sleep(1.5)
        except Exception as e:
            logger.debug(f"CCTV watcher loop error: {e}")
            try:
                camera_lock.release()
            except RuntimeError:
                pass
            time.sleep(2)


def charger_watcher_thread() -> None:
    """Watches for charger connect and disconnect events."""
    logger.info("Charger watcher thread active.")
    last_state = None
    while True:
        try:
            time.sleep(5)
            out = subprocess.check_output(
                "upower -i $(upower -e | grep 'BAT') 2>/dev/null | grep -E 'state|percentage'",
                shell=True,
                text=True,
            ).strip()
            state = None
            pct = ""
            for line in out.splitlines():
                if "state:" in line:
                    state = line.split(":", 1)[1].strip()
                elif "percentage:" in line:
                    pct = line.split(":", 1)[1].strip()

            if state and last_state and state != last_state:
                if state == "discharging" and last_state == "charging":
                    send_tg_msg(f"⚠️ *CHARGER DISCONNECTED!* 🔌\nLaptop ka charger nikal diya gaya hai!\n🔋 Battery: `{pct}`")
                elif state == "charging" and last_state == "discharging":
                    send_tg_msg(f"⚡ *CHARGER CONNECTED!* 🔋\nLaptop charging chalu ho gayi hai.\n🔋 Battery: `{pct}`")
            if state:
                last_state = state
        except Exception:
            time.sleep(6)


def heartbeat_thread() -> None:
    """Continuously pings cloud heartbeat endpoint so laptop is never marked offline during long tasks."""
    while True:
        try:
            requests.get(
                f"{CLOUD_URL}/api/laptop/heartbeat",
                params={"secret": SECRET},
                timeout=6,
            )
        except Exception:
            pass
        time.sleep(5)


def start_node() -> None:
    logger.info("=" * 60)
    logger.info("💻 Hermes Laptop Live Control Node Started")
    logger.info(f"Target Cloud Gateway: {CLOUD_URL}")
    logger.info(f"Local Workspace: {WORKSPACE_DIR}")
    logger.info("Listening for remote commands & live viewing tasks...")
    logger.info("=" * 60)

    # Start Background Watcher & Heartbeat Threads
    threading.Thread(target=heartbeat_thread, daemon=True).start()
    threading.Thread(target=antigravity_watcher_thread, daemon=True).start()
    threading.Thread(target=intruder_watcher_thread, daemon=True).start()
    threading.Thread(target=cctv_watcher_thread, daemon=True).start()
    threading.Thread(target=charger_watcher_thread, daemon=True).start()

    consecutive_errors = 0

    last_heartbeat_log = 0.0

    while True:
        try:
            poll_url = f"{CLOUD_URL}/api/laptop/poll"
            resp = requests.get(
                poll_url,
                params={"secret": SECRET},
                timeout=25,
            )

            if resp.status_code == 200:
                consecutive_errors = 0
                data = resp.json()
                task = data.get("task")

                if task:
                    task_id = task.get("task_id")
                    cmd = task.get("command", "").strip()
                    logger.info(f"⚡ Received task [{task_id}]: {cmd[:80]}")

                    result_output = execute_action(cmd)

                    # Send result back to cloud
                    res_url = f"{CLOUD_URL}/api/laptop/result"
                    requests.post(
                        res_url,
                        json={"secret": SECRET, "task_id": task_id, "output": result_output},
                        timeout=15,
                    )
                    logger.info(f"✅ Completed task [{task_id}]")
                else:
                    if time.time() - last_heartbeat_log > 45:
                        last_heartbeat_log = time.time()
                        logger.info("🟢 Heartbeat active: Polling Render cloud successfully.")
                    time.sleep(1.5)
            else:
                consecutive_errors += 1
                time.sleep(2)

        except requests.exceptions.RequestException:
            consecutive_errors += 1
            delay = min(consecutive_errors * 2, 8)
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    start_node()

