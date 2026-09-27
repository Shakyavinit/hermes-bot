"""
Hermes Agent Tools Module
Provides comprehensive executable tools for the autonomous Gemini agent:
- execute_bash (auto-targets physical laptop when online, cloud if offline)
- execute_on_laptop
- execute_cloud_bash
- capture_laptop_screenshot
- capture_laptop_webcam
- capture_laptop_video
- record_laptop_mic
- toggle_laptop_cctv
- trigger_laptop_alarm
- stop_laptop_alarm
- find_laptop_location
- ghost_mode_screen_off
- screen_on
- get_laptop_battery
- control_laptop_volume
- control_laptop_media
- lock_laptop_screen
- get_laptop_wifi
- get_laptop_apps
- open_url_on_laptop
- play_music_on_laptop
- stop_music_on_laptop
- speak_on_laptop
- send_laptop_key
- read_file
- write_file
- list_directory
- system_status
- fetch_url
"""

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List
import requests

from config import WORKSPACE_DIR
from bridge import (
    dispatch_to_laptop,
    is_laptop_online,
    laptop_ai_status,
    laptop_alarm,
    laptop_apps,
    laptop_battery,
    laptop_cctv_toggle,
    laptop_clipboard,
    laptop_ghost_mode,
    laptop_key_ctrlc,
    laptop_key_enter,
    laptop_key_n,
    laptop_key_y,
    laptop_location,
    laptop_lock,
    laptop_mic,
    laptop_mute,
    laptop_open_url,
    laptop_play_music,
    laptop_playpause,
    laptop_popup,
    laptop_power_poweroff,
    laptop_power_reboot,
    laptop_power_sleep,
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
)


def _execute_cloud_bash(command: str, timeout: int = 60) -> str:
    """Execute a bash command locally in the workspace directory (cloud host)."""
    if not command.strip():
        return "Error: Empty command provided."

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(WORKSPACE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        code = proc.returncode

        res = []
        if stdout:
            res.append(f"STDOUT:\n{stdout}")
        if stderr:
            res.append(f"STDERR:\n{stderr}")
        res.append(f"Exit Code: {code}")

        out_str = "\n".join(res)
        if len(out_str) > 8000:
            out_str = out_str[:4000] + "\n...[Output truncated]...\n" + out_str[-4000:]
        return out_str if out_str else "(Command finished with empty output)"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"


def execute_bash(command: str, timeout: int = 60) -> str:
    """
    Execute any bash shell command.
    Automatically routes to physical laptop if connected; falls back to cloud server if laptop is offline.
    """
    return smart_execute(command, prefer_laptop=True)


def execute_on_laptop(command: str) -> str:
    """Execute a bash command strictly on the user's physical laptop."""
    if not is_laptop_online():
        return "⚠️ Laptop is currently OFFLINE (laptop band hai ya laptop_node disconnect hai)."
    return dispatch_to_laptop(command)


def execute_cloud_bash(command: str, timeout: int = 60) -> str:
    """Execute a bash command strictly on the 24/7 Render cloud container."""
    return _execute_cloud_bash(command, timeout)


def smart_execute(command: str, prefer_laptop: bool = True) -> str:
    """Execute command: runs on physical laptop if connected, otherwise automatically executes on cloud server."""
    if prefer_laptop and is_laptop_online():
        res = dispatch_to_laptop(command)
        return f"💻 *Physical Laptop:*\n{res}"
    else:
        res = _execute_cloud_bash(command)
        if prefer_laptop and not is_laptop_online():
            return f"ℹ️ *(Laptop offline tha, ☁️ Cloud Server par run kiya)*\n\n{res}"
        return f"☁️ *Cloud Server:*\n{res}"


# Physical Laptop Remote Controls
def capture_laptop_screenshot() -> str:
    """Capture a live screenshot of the user's laptop desktop and send it to Telegram."""
    return laptop_screenshot()


def capture_laptop_webcam() -> str:
    """Capture a live front camera photo from the user's laptop and send it to Telegram."""
    return laptop_webcam()


def capture_laptop_video() -> str:
    """Record a 10-second live webcam video clip with audio from laptop and send to Telegram."""
    return laptop_webcam_video()


def record_laptop_mic(seconds: int = 10) -> str:
    """Record audio from laptop room microphone and send as a voice note to Telegram."""
    return laptop_mic(seconds)


def toggle_laptop_cctv() -> str:
    """Toggle CCTV motion monitoring alert on laptop webcam."""
    return laptop_cctv_toggle()


def trigger_laptop_alarm() -> str:
    """Sound a loud 100% volume siren alarm on the laptop."""
    return laptop_alarm()


def stop_laptop_alarm() -> str:
    """Stop the siren alarm on the laptop."""
    return laptop_stop_alarm()


def find_laptop_location() -> str:
    """Get live physical location, public IP, city, and Google Maps pin of laptop."""
    return laptop_location()


def ghost_mode_screen_off() -> str:
    """Turn OFF the laptop display stealthily while keeping background processes/downloads running."""
    return laptop_ghost_mode()


def screen_on() -> str:
    """Turn the laptop screen back ON."""
    return laptop_screen_on()


def get_laptop_battery() -> str:
    """Get live battery percentage, charging state, and remaining runtime of laptop."""
    return laptop_battery()


def control_laptop_volume(action: str) -> str:
    """Control laptop speaker volume: 'up', 'down', or 'mute'."""
    act = action.lower()
    if act in ("up", "increase", "+"):
        return laptop_vol_up()
    elif act in ("down", "decrease", "-"):
        return laptop_vol_down()
    else:
        return laptop_mute()


def control_laptop_media(action: str = "play_pause") -> str:
    """Play or pause active media/music player on laptop."""
    return laptop_playpause()


def lock_laptop_screen() -> str:
    """Instantly lock the physical laptop display."""
    return laptop_lock()


def get_laptop_wifi() -> str:
    """Get connected Wi-Fi network name, signal strength, and local IP."""
    return laptop_wifi()


def get_laptop_apps() -> str:
    """List the top running applications and processes on the laptop."""
    return laptop_apps()


def open_url_on_laptop(url: str) -> str:
    """Open a website URL in the default browser on the laptop."""
    return laptop_open_url(url)


def play_music_on_laptop(query: str) -> str:
    """Search and play a song or music on laptop speakers via mpv/YouTube."""
    return laptop_play_music(query)


def stop_music_on_laptop() -> str:
    """Stop any music or audio currently playing on the laptop."""
    return laptop_stop_music()


def speak_on_laptop(text: str) -> str:
    """Speak text out loud on laptop speakers using text-to-speech."""
    return laptop_speak(text)


def send_laptop_key(key: str) -> str:
    """Simulate keypress on active laptop window: 'enter' (approve), 'y', 'n', or 'ctrl+c'."""
    k = key.lower().strip()
    if "enter" in k or "approve" in k:
        return laptop_key_enter()
    elif k in ("y", "yes"):
        return laptop_key_y()
    elif k in ("n", "no"):
        return laptop_key_n()
    elif "ctrl" in k or "cancel" in k:
        return laptop_key_ctrlc()
    return laptop_key_enter()


# File System & Standard Diagnostic Tools
def resolve_path(filepath: str) -> Path:
    """Resolve file path relative to workspace directory."""
    p = Path(filepath)
    if not p.is_absolute():
        p = WORKSPACE_DIR / p
    return p.resolve()


def read_file(filepath: str, max_chars: int = 8000) -> str:
    """Read the contents of a text file."""
    p = resolve_path(filepath)
    if not p.exists():
        return f"Error: File '{filepath}' does not exist."
    if p.is_dir():
        return f"Error: '{filepath}' is a directory, not a file."

    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n...[Truncated, total {len(content)} chars]..."
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(filepath: str, content: str) -> str:
    """Write or overwrite a file with given content."""
    p = resolve_path(filepath)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to '{filepath}'."
    except Exception as e:
        return f"Error writing file: {str(e)}"


def list_directory(dirpath: str = ".") -> str:
    """List contents of a directory."""
    p = resolve_path(dirpath)
    if not p.exists():
        return f"Error: Directory '{dirpath}' does not exist."
    if not p.is_dir():
        return f"Error: '{dirpath}' is a file, not a directory."

    try:
        entries = []
        for item in sorted(p.iterdir()):
            prefix = "[DIR] " if item.is_dir() else "[FILE]"
            size = ""
            if item.is_file():
                size = f" ({item.stat().st_size} bytes)"
            entries.append(f"{prefix} {item.name}{size}")
        return "\n".join(entries) if entries else "(Empty directory)"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def system_status() -> str:
    """Get system health, memory, disk, and OS information."""
    try:
        uname = platform.uname()
        disk = shutil.disk_usage(str(WORKSPACE_DIR))
        total_gb = disk.total / (1024**3)
        free_gb = disk.free / (1024**3)
        used_gb = disk.used / (1024**3)

        info = [
            f"OS: {uname.system} {uname.release} ({uname.machine})",
            f"Hostname: {uname.node}",
            f"Disk: {used_gb:.1f} GB used / {total_gb:.1f} GB total ({free_gb:.1f} GB free)",
            f"Workspace: {WORKSPACE_DIR}",
            f"Python: {platform.python_version()}",
            f"Current Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        ]
        return "\n".join(info)
    except Exception as e:
        return f"Error checking system status: {str(e)}"


def fetch_url(url: str, timeout: int = 15) -> str:
    """Fetch content of a webpage or API endpoint."""
    if not url.startswith("http://") and not url.startswith("https://"):
        return "Error: URL must start with http:// or https://"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        text = resp.text
        if len(text) > 6000:
            text = text[:6000] + f"\n...[Truncated, total {len(text)} chars]..."
        return f"Status: {resp.status_code}\nContent:\n{text}"
    except Exception as e:
        return f"Error fetching URL: {str(e)}"


def query_public_api(service: str, query: str = "") -> str:
    """Query zero-auth public APIs for real-time external data (crypto, weather, IP, wiki, dictionary)."""
    s = service.strip().lower()
    q = query.strip()
    try:
        if any(k in s for k in ("crypto", "coin", "bitcoin", "btc", "eth")):
            target = q.lower() if q else "bitcoin,ethereum,solana"
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={target}&vs_currencies=inr,usd"
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and r.json():
                return f"🪙 Live Crypto Prices:\n" + json.dumps(r.json(), indent=2)
            # Binance fallback
            sym = f"{q.upper()}USDT" if q else "BTCUSDT"
            r_b = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}", timeout=10)
            return f"🪙 Live Price:\n" + json.dumps(r_b.json(), indent=2)

        elif any(k in s for k in ("weather", "mausam", "temp", "temperature")):
            city = q if q else "Delhi"
            r = requests.get(f"https://wttr.in/{city}?format=%C+%t+%w+%h", timeout=10)
            if r.status_code == 200:
                return f"🌤️ Live Weather in {city.capitalize()}: {r.text.strip()}"
            return f"Weather data for {city} currently unavailable."

        elif any(k in s for k in ("ip", "geo", "location", "isp")):
            url = f"http://ip-api.com/json/{q}" if q else "http://ip-api.com/json/"
            r = requests.get(url, timeout=10)
            data = r.json()
            return (
                f"📍 IP Geolocation:\n"
                f"• IP: {data.get('query')}\n"
                f"• City: {data.get('city')}, {data.get('regionName')}\n"
                f"• Country: {data.get('country')}\n"
                f"• ISP: {data.get('isp')}\n"
                f"• Timezone: {data.get('timezone')}"
            )

        elif any(k in s for k in ("wiki", "wikipedia", "encyclopedia", "search", "info")):
            url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={q}&limit=3&namespace=0&format=json"
            r = requests.get(url, headers={"User-Agent": "HermesBot/1.0"}, timeout=10)
            data = r.json()
            results = [f"• {title}: {link}" for title, link in zip(data[1], data[3])]
            return "📚 Wikipedia Real-time Knowledge:\n" + ("\n".join(results) if results else f"No Wikipedia entries found for '{q}'.")

        elif any(k in s for k in ("dict", "dictionary", "meaning", "define")):
            r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{q}", timeout=10)
            if r.status_code == 200:
                d = r.json()[0]
                meanings = d.get("meanings", [{}])[0].get("definitions", [{}])[0].get("definition", "")
                return f"📖 Definition of '{q}': {meanings}"
            return f"No definition found for '{q}'."

        else:
            return f"Service '{service}' not recognized. Supported services: 'crypto', 'weather', 'ip', 'wikipedia', 'dictionary'."
    except Exception as e:
        return f"Error querying public API ({service}): {str(e)}"


def call_api(url: str, method: str = "GET", headers_json: str = "{}", body_json: str = "{}") -> str:
    """Execute any external HTTP/REST API request (GET, POST, PUT, DELETE) dynamically."""
    if not url.startswith("http://") and not url.startswith("https://"):
        return "Error: URL must begin with http:// or https://"
    try:
        method = method.upper().strip()
        headers = json.loads(headers_json) if headers_json and headers_json.strip() else {}
        body = json.loads(body_json) if body_json and body_json.strip() else None

        if "User-Agent" not in headers:
            headers["User-Agent"] = "HermesAutonomousAgent/1.0"

        if method == "GET":
            resp = requests.get(url, headers=headers, params=body, timeout=20)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=body, timeout=20)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, json=body, timeout=20)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, json=body, timeout=20)
        else:
            return f"Error: Unsupported HTTP method '{method}'."

        res_text = resp.text
        if len(res_text) > 4000:
            res_text = res_text[:4000] + f"\n...[Truncated, {len(resp.text)} bytes total]..."
        return f"HTTP {resp.status_code} ({resp.reason})\nResponse:\n{res_text}"
    except Exception as e:
        return f"API execution failed: {str(e)}"


# Tool Registry & Schemas
TOOLS_MAP: Dict[str, Callable] = {
    "execute_bash": execute_bash,
    "execute_on_laptop": execute_on_laptop,
    "execute_cloud_bash": execute_cloud_bash,
    "smart_execute": smart_execute,
    "capture_laptop_screenshot": capture_laptop_screenshot,
    "capture_laptop_webcam": capture_laptop_webcam,
    "capture_laptop_video": capture_laptop_video,
    "record_laptop_mic": record_laptop_mic,
    "toggle_laptop_cctv": toggle_laptop_cctv,
    "trigger_laptop_alarm": trigger_laptop_alarm,
    "stop_laptop_alarm": stop_laptop_alarm,
    "find_laptop_location": find_laptop_location,
    "ghost_mode_screen_off": ghost_mode_screen_off,
    "screen_on": screen_on,
    "get_laptop_battery": get_laptop_battery,
    "control_laptop_volume": control_laptop_volume,
    "control_laptop_media": control_laptop_media,
    "lock_laptop_screen": lock_laptop_screen,
    "get_laptop_wifi": get_laptop_wifi,
    "get_laptop_apps": get_laptop_apps,
    "open_url_on_laptop": open_url_on_laptop,
    "play_music_on_laptop": play_music_on_laptop,
    "stop_music_on_laptop": stop_music_on_laptop,
    "speak_on_laptop": speak_on_laptop,
    "send_laptop_key": send_laptop_key,
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "system_status": system_status,
    "fetch_url": fetch_url,
    "query_public_api": query_public_api,
    "call_api": call_api,
}

GEMINI_FUNCTION_DECLARATIONS = [
    {
        "name": "execute_bash",
        "description": "Execute any Linux bash shell command (e.g. system info, files, processes, network, scripts). Automatically runs directly on user's physical laptop when online, or cloud server if laptop is offline.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command line string to run.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "execute_on_laptop",
        "description": "Execute a bash shell command strictly on the user's physical laptop.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command line to run on user's physical laptop.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "execute_cloud_bash",
        "description": "Execute a bash shell command strictly inside the 24/7 cloud server container.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run on cloud server.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "smart_execute",
        "description": "Execute shell command on physical laptop if online, with automatic fallback to cloud server.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "capture_laptop_screenshot",
        "description": "Capture a live high-resolution screenshot of the physical laptop desktop and send it as a photo to Telegram.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "capture_laptop_webcam",
        "description": "Capture a live front camera/webcam snapshot from the physical laptop and send it as a photo to Telegram.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "capture_laptop_video",
        "description": "Record a 10-second live webcam video clip with audio from the user's laptop and send it to Telegram.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "record_laptop_mic",
        "description": "Record audio from the laptop room microphone and send it as a voice note to Telegram.",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "description": "Duration in seconds to record (default 10).",
                }
            },
        },
    },
    {
        "name": "toggle_laptop_cctv",
        "description": "Turn ON or OFF CCTV motion alert mode on the physical laptop webcam.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "trigger_laptop_alarm",
        "description": "Sound a loud siren alarm on the physical laptop at 100% volume.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "stop_laptop_alarm",
        "description": "Stop the siren alarm on the laptop.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "find_laptop_location",
        "description": "Get the physical laptop's live location, public IP, city, ISP, and Google Maps pin.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "ghost_mode_screen_off",
        "description": "Turn OFF the laptop screen (blank display) stealthily while keeping background processes, downloads, AI, and scripts active.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "screen_on",
        "description": "Turn the physical laptop screen back ON.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_laptop_battery",
        "description": "Check live laptop battery level, charging state, and estimated runtime.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "control_laptop_volume",
        "description": "Adjust laptop speaker volume ('up', 'down') or toggle mute ('mute').",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["up", "down", "mute"],
                    "description": "Volume action to perform.",
                }
            },
            "required": ["action"],
        },
    },
    {
        "name": "control_laptop_media",
        "description": "Play or pause current music/video playback on the physical laptop.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Media action (default 'play_pause').",
                }
            },
        },
    },
    {
        "name": "lock_laptop_screen",
        "description": "Immediately lock the screen of the physical laptop.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_laptop_wifi",
        "description": "Get current connected Wi-Fi SSID, signal quality, and local network IP on laptop.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_laptop_apps",
        "description": "Get a list of currently running applications and processes on the laptop.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "open_url_on_laptop",
        "description": "Open a website URL in the default browser on the physical laptop (e.g. YouTube, Google, GitHub).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The website URL to open.",
                }
            },
            "required": ["url"],
        },
    },
    {
        "name": "play_music_on_laptop",
        "description": "Search and play a song or music in the background on laptop speakers via mpv/YouTube.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Song name or YouTube search query.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "stop_music_on_laptop",
        "description": "Stop any background music or audio playback on the laptop.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "speak_on_laptop",
        "description": "Speak text out loud on the laptop speakers using text-to-speech.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to speak out loud.",
                }
            },
            "required": ["text"],
        },
    },
    {
        "name": "send_laptop_key",
        "description": "Send simulated keystrokes to active laptop window: 'enter' (approve prompt), 'y', 'n', or 'ctrl+c'.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "enum": ["enter", "y", "n", "ctrl+c"],
                    "description": "The key to send.",
                }
            },
            "required": ["key"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a local file in workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "Relative or absolute path of the file to read.",
                }
            },
            "required": ["filepath"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with given text content.",
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "Path where the file should be saved.",
                },
                "content": {
                    "type": "string",
                    "description": "Full content to write into the file.",
                },
            },
            "required": ["filepath", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and subdirectories in a directory path.",
        "parameters": {
            "type": "object",
            "properties": {
                "dirpath": {
                    "type": "string",
                    "description": "Directory path (default is '.' for current workspace).",
                }
            },
        },
    },
    {
        "name": "system_status",
        "description": "Get current OS, disk usage, memory, and environment information.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "fetch_url",
        "description": "Fetch live web page or API response via HTTP GET.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full HTTP/HTTPS URL to fetch.",
                }
            },
            "required": ["url"],
        },
    },
    {
        "name": "query_public_api",
        "description": "Query zero-key, completely free public APIs for real-time live data: 'crypto' (Bitcoin, Ethereum, Solana prices in INR/USD), 'weather' (live weather for any city e.g. 'Delhi', 'Mumbai'), 'ip' (IP address, ISP, city, location), 'wikipedia' (encyclopedia knowledge & summaries), 'dictionary' (word definitions).",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "The public service to query: 'crypto', 'weather', 'ip', 'wikipedia', or 'dictionary'.",
                },
                "query": {
                    "type": "string",
                    "description": "Specific query e.g. 'bitcoin', 'Delhi', 'Elon Musk', 'quantum computing'.",
                },
            },
            "required": ["service"],
        },
    },
    {
        "name": "call_api",
        "description": "Execute any generic REST API request (GET, POST, PUT, DELETE) to any external URL with optional JSON headers and payload.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The API endpoint URL to call.",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP method: GET, POST, PUT, or DELETE. Default is GET.",
                },
                "headers_json": {
                    "type": "string",
                    "description": "Optional JSON string of HTTP headers, e.g. '{\"Authorization\": \"Bearer ...\"}'.",
                },
                "body_json": {
                    "type": "string",
                    "description": "Optional JSON string of request body or params.",
                },
            },
            "required": ["url"],
        },
    },
]

TOOL_DEFINITIONS = [
    {"type": "function", "function": decl} for decl in GEMINI_FUNCTION_DECLARATIONS
]


def dispatch_tool_call(tool_name: str, arguments: dict) -> str:
    """Dispatch and execute tool by name with arguments."""
    func = TOOLS_MAP.get(tool_name)
    if not func:
        return f"Error: Tool '{tool_name}' not found."
    try:
        return str(func(**arguments))
    except Exception as e:
        return f"Error calling tool '{tool_name}': {str(e)}"
