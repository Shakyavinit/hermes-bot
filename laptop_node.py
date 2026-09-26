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

CLOUD_URL = os.getenv("HERMES_CLOUD_URL", "https://hermes-bot-kqv8.onrender.com").rstrip("/")
SECRET = os.getenv("LAPTOP_BRIDGE_SECRET", "hermes_secret_8616271645")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8954487031:AAEv9-RzsecVcnJyVfd3pfEOYYfiBGh9Fzg")
OWNER_CHAT_ID = 8616271645
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))


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
        os.system(f"DISPLAY=:0 scrot -z {img_path} 2>/dev/null")
        if send_tg_photo(img_path, "📸 *Laptop Live Desktop Screenshot*"):
            return "✅ Live Desktop screenshot captured & sent to chat!"
        return "❌ Screenshot capture failed (check display session)."

    # 2. Live Front Camera Snapshot
    if clean == "__ACTION_WEBCAM__":
        cam_path = "/tmp/hermes_webcam.jpg"
        os.system(f"ffmpeg -y -f v4l2 -i /dev/video0 -vframes 1 {cam_path} 2>/dev/null")
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

    # 11. Antigravity & Terminal Keystroke Simulation
    if clean == "__ACTION_KEY_ENTER__":
        os.system("DISPLAY=:0 xdotool key Return 2>/dev/null")
        return "⏎ Enter key sent to laptop!"

    if clean == "__ACTION_KEY_Y__":
        os.system("DISPLAY=:0 xdotool key y Return 2>/dev/null")
        return "🟢 'y' + Enter sent to laptop!"

    if clean == "__ACTION_KEY_N__":
        os.system("DISPLAY=:0 xdotool key n Return 2>/dev/null")
        return "🔴 'n' + Enter sent to laptop!"

    if clean == "__ACTION_KEY_CTRLC__":
        os.system("DISPLAY=:0 xdotool key ctrl+c 2>/dev/null")
        return "🛑 Ctrl+C sent to laptop!"

    if clean.startswith("__ACTION_TYPE__"):
        text_to_type = clean[len("__ACTION_TYPE__"):].strip()
        escaped = text_to_type.replace('"', '\\"')
        os.system(f'DISPLAY=:0 xdotool type --delay 20 "{escaped}" 2>/dev/null')
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
        wav_path = "/tmp/hermes_mic.wav"
        ogg_path = "/tmp/hermes_mic.ogg"
        os.system(f"arecord -d {sec} -f cd {wav_path} 2>/dev/null")
        os.system(f"ffmpeg -y -i {wav_path} -c:a libopus {ogg_path} 2>/dev/null")
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
        if clip_text:
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, env={**os.environ, "DISPLAY": ":0"})
            p.communicate(input=clip_text.encode("utf-8"))
            return f"📋 Copied to laptop clipboard: `{clip_text}`"
        else:
            try:
                out = subprocess.check_output("DISPLAY=:0 xclip -o -selection clipboard 2>/dev/null", shell=True, text=True).strip()
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
        title = parts[0].replace('"', '\\"') if len(parts) > 1 else "Telegram Notice"
        body = (parts[1] if len(parts) > 1 else raw).replace('"', '\\"')
        os.system(f'DISPLAY=:0 notify-send "{title}" "{body}" 2>/dev/null')
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
                        os.system(f"DISPLAY=:0 scrot -z {img_path} 2>/dev/null")
                        alert_msg = (
                            "⚠️ *Antigravity Alert: Sandbox / Approval Required!*\n\n"
                            "Terminal ya tool sandbox confirmation mang raha hai.\n"
                            "Niche diye buttons se direct approve karein:"
                        )
                        if os.path.exists(img_path):
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


def start_node() -> None:
    logger.info("=" * 60)
    logger.info("💻 Hermes Laptop Live Control Node Started")
    logger.info(f"Target Cloud Gateway: {CLOUD_URL}")
    logger.info(f"Local Workspace: {WORKSPACE_DIR}")
    logger.info("Listening for remote commands & live viewing tasks...")
    logger.info("=" * 60)

    # Start Antigravity AI Watcher Thread
    watcher = threading.Thread(target=antigravity_watcher_thread, daemon=True)
    watcher.start()

    consecutive_errors = 0

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

