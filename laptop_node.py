"""
Hermes Local Laptop Runner Node
Runs in background on user's physical laptop.
Allows the 24/7 Render Cloud Telegram Bot to execute bash commands, capture live
screenshots, webcam snapshots, check battery, control volume/media, and monitor hardware.
"""

import json
import logging
import os
import subprocess
import sys
import time
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


def send_tg_photo(file_path: str, caption: str) -> bool:
    """Send photo directly to the owner on Telegram."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": OWNER_CHAT_ID, "caption": caption},
                files={"photo": f},
                timeout=25,
            )
            return resp.status_code == 200 and resp.json().get("ok")
    except Exception as e:
        logger.error(f"Error sending photo to Telegram: {e}")
        return False


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


def start_node() -> None:
    logger.info("=" * 60)
    logger.info("💻 Hermes Laptop Live Control Node Started")
    logger.info(f"Target Cloud Gateway: {CLOUD_URL}")
    logger.info(f"Local Workspace: {WORKSPACE_DIR}")
    logger.info("Listening for remote commands & live viewing tasks...")
    logger.info("=" * 60)

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
