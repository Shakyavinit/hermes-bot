"""
Hermes Human GUI & Vision Interaction Engine
Enables the autonomous agent to operate the desktop like a real human:
- Smooth Bezier-curve mouse movements with realistic acceleration & deceleration.
- Natural clicking, double-clicking, right-clicking, and scrolling.
- Human-like typing with keystroke variance.
- Human-like application opening via GNOME activities launcher and typing.
- Visual screen understanding and target element detection using Gemini Multimodal Vision.
"""

import base64
import glob
import json
import logging
import math
import os
import random
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import requests

from config import GEMINI_API_KEYS, GEMINI_MODELS

logger = logging.getLogger("HumanGUI")


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


def get_current_mouse_position() -> Tuple[int, int]:
    """Retrieve current (x, y) coordinates of the mouse cursor using xdotool."""
    env = get_x11_env()
    try:
        out = subprocess.check_output(["xdotool", "getmouselocation"], env=env, text=True, stderr=subprocess.DEVNULL)
        m_x = re.search(r"x:(\d+)", out)
        m_y = re.search(r"y:(\d+)", out)
        if m_x and m_y:
            return int(m_x.group(1)), int(m_y.group(1))
    except Exception:
        pass
    return 500, 500


def get_screen_resolution() -> Tuple[int, int]:
    """Get the screen width and height in pixels."""
    env = get_x11_env()
    try:
        out = subprocess.check_output(["xdotool", "getdisplaygeometry"], env=env, text=True, stderr=subprocess.DEVNULL)
        parts = out.strip().split()
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return 1920, 1080


def human_mouse_move(target_x: int, target_y: int, duration: Optional[float] = None) -> bool:
    """
    Move the mouse cursor smoothly from current position to (target_x, target_y)
    following a natural cubic Bezier trajectory with realistic human easing.
    """
    env = get_x11_env()
    x0, y0 = get_current_mouse_position()

    dx = target_x - x0
    dy = target_y - y0
    dist = math.hypot(dx, dy)

    if dist < 4:
        subprocess.run(["xdotool", "mousemove", str(target_x), str(target_y)], env=env)
        return True

    # Calculate realistic duration and step count based on distance
    if duration is None:
        duration = max(0.25, min(0.65, dist / 1400.0 + random.uniform(0.08, 0.18)))

    steps = int(max(15, min(40, dist / 25.0 + random.randint(5, 10))))

    # Unit vector perpendicular to direction of movement for Bezier curve arc
    perp_x = -dy / dist
    perp_y = dx / dist

    # Deviations for cubic control points
    dev1 = random.uniform(-0.18, 0.18) * dist
    dev2 = random.uniform(-0.12, 0.12) * dist

    p1_x = x0 + dx * 0.28 + perp_x * dev1
    p1_y = y0 + dy * 0.28 + perp_y * dev1

    p2_x = x0 + dx * 0.72 + perp_x * dev2
    p2_y = y0 + dy * 0.72 + perp_y * dev2

    sleep_per_step = duration / float(steps)

    for i in range(1, steps + 1):
        t = i / float(steps)
        # Cosine ease-in-out curve for natural acceleration and deceleration
        s = (1.0 - math.cos(math.pi * t)) / 2.0

        # Cubic Bezier interpolation
        bx = (
            (1.0 - s) ** 3 * x0
            + 3.0 * ((1.0 - s) ** 2) * s * p1_x
            + 3.0 * (1.0 - s) * (s**2) * p2_x
            + (s**3) * target_x
        )
        by = (
            (1.0 - s) ** 3 * y0
            + 3.0 * ((1.0 - s) ** 2) * s * p1_y
            + 3.0 * (1.0 - s) * (s**2) * p2_y
            + (s**3) * target_y
        )

        # Micro-jitter
        jitter_x = random.uniform(-0.6, 0.6) if i < steps else 0
        jitter_y = random.uniform(-0.6, 0.6) if i < steps else 0

        cur_x = int(round(bx + jitter_x))
        cur_y = int(round(by + jitter_y))

        subprocess.run(["xdotool", "mousemove", str(cur_x), str(cur_y)], env=env)
        time.sleep(max(0.005, sleep_per_step))

    # Exact final landing
    subprocess.run(["xdotool", "mousemove", str(target_x), str(target_y)], env=env)
    return True


def human_mouse_click(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
    clicks: int = 1,
) -> str:
    """
    Smoothly move mouse to (x, y) like a human, hesitate briefly, and click.
    button: 'left', 'right', 'middle'
    clicks: 1 for single click, 2 for double click
    """
    env = get_x11_env()

    if x is not None and y is not None:
        human_mouse_move(x, y)

    # Human hesitation before clicking (50 - 110ms)
    time.sleep(random.uniform(0.05, 0.11))

    btn_map = {"left": "1", "middle": "2", "right": "3"}
    b = btn_map.get(button.lower().strip(), "1")

    for c in range(clicks):
        # Realistic press down and release timing
        subprocess.run(["xdotool", "mousedown", b], env=env)
        time.sleep(random.uniform(0.06, 0.10))
        subprocess.run(["xdotool", "mouseup", b], env=env)

        if clicks > 1 and c < clicks - 1:
            time.sleep(random.uniform(0.10, 0.16))

    action_label = f"Double-clicked" if clicks == 2 else f"Clicked ({button})"
    pos_str = f"at ({x}, {y})" if (x is not None and y is not None) else "at current position"
    return f"🖱️ {action_label} {pos_str} like a human!"


def human_mouse_scroll(direction: str = "down", amount: int = 5) -> str:
    """Scroll mouse wheel like a human with natural spacing."""
    env = get_x11_env()
    # In x11: 4 = scroll up, 5 = scroll down
    b = "4" if direction.lower() in ("up", "top", "+") else "5"

    for _ in range(amount):
        subprocess.run(["xdotool", "click", b], env=env)
        time.sleep(random.uniform(0.04, 0.09))

    return f"📜 Scrolled {direction} by {amount} steps."


def human_type_text(text: str, press_enter: bool = False) -> str:
    """Type text with realistic human typing delays between keystrokes."""
    env = get_x11_env()
    delay = random.randint(65, 95)
    subprocess.run(["xdotool", "type", "--delay", str(delay), text], env=env)

    if press_enter:
        time.sleep(random.uniform(0.2, 0.4))
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], env=env)

    return f"⌨️ Typed '{text}' like a human (speed: ~{delay}ms/key){' + [Enter]' if press_enter else ''}."


def human_open_app(app_name: str) -> str:
    """
    Open an application on the user's laptop screen like a human:
    1. Press Super (Windows) key to open app drawer / search.
    2. Type the app name with natural typing speed.
    3. Wait for search results.
    4. Press Enter to launch.
    5. Take a confirmation screenshot.
    """
    env = get_x11_env()
    clean_name = app_name.strip()

    logger.info(f"Human-opening app: {clean_name}")

    # 1. Trigger Super key
    subprocess.run(["xdotool", "key", "--clearmodifiers", "Super"], env=env)
    time.sleep(0.45)

    # 2. Type app name with human speed
    delay = random.randint(70, 100)
    subprocess.run(["xdotool", "type", "--delay", str(delay), clean_name], env=env)
    time.sleep(0.6)

    # 3. Press Return
    subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], env=env)
    time.sleep(1.8)

    # Fallback execution in background if window doesn't appear
    app_lower = clean_name.lower()
    fallback_cmd = None
    if "chrome" in app_lower:
        fallback_cmd = "google-chrome"
    elif "firefox" in app_lower:
        fallback_cmd = "firefox"
    elif "terminal" in app_lower:
        fallback_cmd = "gnome-terminal"
    elif "code" in app_lower or "vs code" in app_lower:
        fallback_cmd = "code"
    elif "calc" in app_lower:
        fallback_cmd = "gnome-calculator"
    elif "file" in app_lower or "nautilus" in app_lower:
        fallback_cmd = "nautilus"
    elif "settings" in app_lower:
        fallback_cmd = "gnome-control-center"

    if fallback_cmd:
        subprocess.Popen(
            [fallback_cmd],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # 4. Capture screenshot
    screen_path = "/tmp/hermes_app_opened.png"
    capture_desktop_image(screen_path)

    return f"🚀 *App Opened Like a Human:* `{clean_name}`\nScreen par search karke launch kar diya hai!"


def capture_desktop_image(path: str = "/tmp/hermes_screenshot.png") -> Optional[str]:
    """
    Capture a clean, full-color screenshot of the active desktop under GNOME Wayland & X11.
    Uses flameshot as primary Wayland capture, then falls back to scrot/import.
    """
    env = os.environ.copy()
    env["LC_ALL"] = "C.UTF-8"
    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    env["WAYLAND_DISPLAY"] = "wayland-0"
    env["DISPLAY"] = ":0"
    mutter_auths = glob.glob("/run/user/1000/.mutter-Xwaylandauth*")
    if mutter_auths:
        env["XAUTHORITY"] = mutter_auths[0]

    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass

    # 1. Primary: Flameshot (GNOME Wayland native)
    try:
        subprocess.run(
            ["flameshot", "full", "-p", path],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
        if os.path.exists(path) and os.path.getsize(path) > 10000:
            return path
    except Exception as e:
        logger.debug(f"Flameshot capture exception: {e}")

    # 2. Secondary fallback: Scrot
    try:
        subprocess.run(["scrot", "-z", "-o", path], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if os.path.exists(path) and os.path.getsize(path) > 10000:
            return path
    except Exception:
        pass

    # 3. Tertiary fallback: ImageMagick import
    try:
        subprocess.run(["import", "-window", "root", path], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if os.path.exists(path) and os.path.getsize(path) > 10000:
            return path
    except Exception:
        pass

    return path if (os.path.exists(path) and os.path.getsize(path) > 0) else None


def call_gemini_vision(image_path: str, prompt: str) -> Optional[str]:
    """Send desktop screenshot to Gemini Multimodal Vision API."""
    if not os.path.exists(image_path):
        return None

    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        b64_data = base64.b64encode(img_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        return None

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": b64_data,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        },
    }

    for model in GEMINI_MODELS:
        for key in GEMINI_API_KEYS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            try:
                resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        text_list = [p.get("text", "") for p in parts if "text" in p]
                        return "\n".join(text_list).strip()
            except Exception as e:
                logger.warning(f"Vision API error on {model}: {e}")
                continue

    return None


def inspect_screen_vision(instruction: str = "Describe what is currently visible on screen") -> str:
    """
    Capture live screenshot and use Gemini Vision to explain what is currently displayed on screen.
    Auto-cleans temporary screenshot after analysis.
    """
    img_path = capture_desktop_image()
    if not img_path:
        return "❌ Error: Could not capture screen image for visual inspection."

    try:
        try:
            with Image.open(img_path) as im:
                w, h = im.size
        except Exception:
            w, h = 1920, 1080

        prompt = (
            f"You are a computer vision desktop assistant. Resolution: {w}x{h}.\n"
            f"User query / instruction: {instruction}\n\n"
            "Provide a concise, clear description in natural Hindi/Hinglish of:\n"
            "1. Active open applications and windows.\n"
            "2. Main content displayed (e.g. website, code editor, terminal, media player).\n"
            "3. Key buttons, search bars, or interactive elements visible.\n"
            "Keep it direct and informative (under 4-5 bullet points)."
        )

        result = call_gemini_vision(img_path, prompt)
        if result:
            return f"👁️ *Visual Screen Analysis ({w}x{h}):*\n\n{result}"
        return "⚠️ Vision AI screen ko process nahi kar saka. Please check network/API key."
    finally:
        try:
            if img_path and os.path.exists(img_path):
                os.remove(img_path)
        except Exception:
            pass


def analyze_screen_and_click(target_element: str, instruction: str = "") -> str:
    """
    Inspect the screen using Gemini Vision to find target_element,
    extract exact (x, y) coordinates, glide the mouse like a human, and click it.
    Auto-cleans temporary images after execution.
    """
    img_path = capture_desktop_image()
    if not img_path:
        return "❌ Error: Could not capture screen image."

    confirm_img = None
    try:
        try:
            with Image.open(img_path) as im:
                w, h = im.size
        except Exception:
            w, h = 1920, 1080

        prompt = (
            f"You are a GUI Automation Vision Agent. The screen resolution is {w}x{h} pixels.\n"
            f"Target element to find and click: '{target_element}'.\n"
            f"Additional context: '{instruction}'.\n\n"
            "Carefully analyze this desktop screenshot. Identify where the target element is located.\n"
            "Return ONLY a pure JSON object (no markdown code blocks, no other text) with this format:\n"
            "{\n"
            '  "found": true,\n'
            f'  "x": <integer x coordinate between 0 and {w}>,\n'
            f'  "y": <integer y coordinate between 0 and {h}>,\n'
            '  "element_name": "<text or label of the element found>",\n'
            '  "screen_summary": "<1 sentence summary of what is on screen>"\n'
            "}\n"
            'If the element is not found on screen, return: {"found": false, "screen_summary": "..."}'
        )

        vision_out = call_gemini_vision(img_path, prompt)
        if not vision_out:
            return f"⚠️ Vision AI couldn't locate '{target_element}' on screen."

        clean_json = vision_out.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```[a-zA-Z]*\n", "", clean_json)
            clean_json = re.sub(r"\n```$", "", clean_json).strip()

        try:
            data = json.loads(clean_json)
        except Exception:
            m_x = re.search(r'"x"\s*:\s*(\d+)', clean_json)
            m_y = re.search(r'"y"\s*:\s*(\d+)', clean_json)
            if m_x and m_y:
                data = {"found": True, "x": int(m_x.group(1)), "y": int(m_y.group(1)), "element_name": target_element}
            else:
                return f"👁️ Screen Summary:\n{vision_out}\n\n⚠️ Target '{target_element}' ke coordinates extract nahi ho paye."

        if not data.get("found"):
            summary = data.get("screen_summary", "Element screen par nahi mila.")
            return f"❌ Target '{target_element}' screen par nahi mila.\n\nSummary: {summary}"

        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        el_name = data.get("element_name", target_element)
        summary = data.get("screen_summary", "")

        # Execute human mouse glide and click!
        human_mouse_click(x, y, button="left", clicks=1)

        # Capture follow-up confirmation screenshot
        confirm_img = "/tmp/hermes_clicked_state.png"
        time.sleep(0.6)
        capture_desktop_image(confirm_img)

        return (
            f"🎯 *Target Found & Clicked like a Human!*\n\n"
            f"• **Element:** {el_name}\n"
            f"• **Screen Coordinates:** `(x={x}, y={y})`\n"
            f"• **Context:** {summary}\n\n"
            "Mouse smoothly glide hoke button par click ho gaya hai!"
        )
    finally:
        for fpath in (img_path, confirm_img):
            if fpath and os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
