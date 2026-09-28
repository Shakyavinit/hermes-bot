"""
Hermes Offline Mobile Hub
100% Offline, Zero-Internet Local Web Application & REST API
Enables complete laptop control, Antigravity approvals, and live stealth screenshots
from any mobile phone connected via Mobile Hotspot, Laptop Hotspot, or Local LAN.
"""

import io
import json
import logging
import os
import subprocess
import time
from typing import Any, Dict, Optional

from flask import Flask, Response, jsonify, request, send_file
import qrcode

logger = logging.getLogger("OfflineHub")

app = Flask(__name__)

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

# Import laptop node functions if available
try:
    from laptop_node import (
        capture_desktop_image,
        execute_action,
        get_auto_approve_info,
        get_auto_approve_state,
        is_remote_access_enabled,
        is_screen_locked,
        set_auto_approve_state,
        toggle_auto_approve_state,
        toggle_remote_access,
    )
except ImportError:
    # Fallbacks for standalone testing
    def capture_desktop_image(path: str = "/tmp/hermes_screenshot.png") -> Optional[str]:
        os.system(f"flameshot full -r > {path} 2>/dev/null")
        return path if os.path.exists(path) else None

    def execute_action(cmd: str) -> str:
        return f"Simulated: {cmd}"

    def is_screen_locked() -> bool:
        return False

    def is_remote_access_enabled() -> bool:
        return True

    def get_auto_approve_state() -> bool:
        return False

    def toggle_auto_approve_state(scope: str = "task") -> bool:
        return True

    def toggle_remote_access() -> bool:
        return True


# Shared memory store for active prompts
_active_offline_prompt: Optional[Dict[str, Any]] = None


def set_offline_prompt(prompt_data: Optional[Dict[str, Any]]) -> None:
    """Set the currently active Antigravity prompt for the offline mobile UI."""
    global _active_offline_prompt
    _active_offline_prompt = prompt_data


def get_offline_prompt() -> Optional[Dict[str, Any]]:
    """Get the currently active Antigravity prompt."""
    global _active_offline_prompt
    return _active_offline_prompt


def get_local_ip() -> str:
    """Find the best local IP address for offline LAN access."""
    import socket

    # 1. Try socket probing common targets
    for target in ("8.8.8.8", "1.1.1.1", "192.168.1.1", "10.42.0.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((target, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass

    # 2. Try hostname -I
    try:
        out = subprocess.check_output("hostname -I 2>/dev/null", shell=True, text=True).strip()
        for candidate in out.split():
            if candidate and not candidate.startswith("127.") and not candidate.startswith("172.17."):
                return candidate
    except Exception:
        pass

    # 3. Try ip route get
    try:
        out = subprocess.check_output("ip route get 1.1.1.1 2>/dev/null", shell=True, text=True).strip()
        if "src " in out:
            candidate = out.split("src ")[1].split()[0]
            if candidate and not candidate.startswith("127."):
                return candidate
    except Exception:
        pass

    # 4. Try nmcli IP detection
    try:
        out = subprocess.check_output("nmcli -g IP4.ADDRESS dev show 2>/dev/null", shell=True, text=True).strip()
        for line in out.splitlines():
            cand = line.strip().split("/")[0]
            if cand and not cand.startswith("127.") and not cand.startswith("172.17."):
                return cand
    except Exception:
        pass

    return "127.0.0.1"


# ==============================================================================
# HTML Mobile Application Template
# ==============================================================================
MOBILE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="theme-color" content="#090d16">
  <title>Hermes Hub</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: rgba(22, 27, 34, 0.85);
      --card-border: rgba(255, 255, 255, 0.1);
      --primary: #58a6ff;
      --success: #3fb950;
      --danger: #f85149;
      --warning: #d29922;
      --text: #f0f6fc;
      --text-muted: #8b949e;
      --radius: 14px;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      -webkit-tap-highlight-color: transparent;
    }
    body {
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 14px;
      padding-bottom: 70px;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 4px 16px 4px;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 16px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .brand-logo {
      font-size: 24px;
    }
    .brand-title {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }
    .badge {
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 20px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge-offline {
      background: rgba(63, 185, 80, 0.15);
      color: var(--success);
      border: 1px solid rgba(63, 185, 80, 0.3);
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 16px;
    }
    .full-width {
      grid-column: span 2;
    }
    .card {
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 14px;
      position: relative;
      overflow: hidden;
    }
    .card-title {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .btn {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--card-border);
      color: var(--text);
      padding: 12px 14px;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      transition: all 0.15s ease;
      touch-action: manipulation;
    }
    .btn:active {
      transform: scale(0.97);
      background: rgba(255, 255, 255, 0.12);
    }
    .btn-primary {
      background: rgba(88, 166, 255, 0.15);
      color: var(--primary);
      border-color: rgba(88, 166, 255, 0.3);
    }
    .btn-success {
      background: rgba(63, 185, 80, 0.18);
      color: var(--success);
      border-color: rgba(63, 185, 80, 0.35);
    }
    .btn-danger {
      background: rgba(248, 81, 73, 0.18);
      color: var(--danger);
      border-color: rgba(248, 81, 73, 0.35);
    }
    .btn-warning {
      background: rgba(210, 153, 34, 0.18);
      color: var(--warning);
      border-color: rgba(210, 153, 34, 0.35);
    }
    .screen-container {
      position: relative;
      border-radius: 10px;
      overflow: hidden;
      background: #000;
      border: 1px solid var(--card-border);
      aspect-ratio: 16/9;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .screen-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .screen-refresh-btn {
      position: absolute;
      bottom: 8px;
      right: 8px;
      padding: 6px 12px;
      font-size: 12px;
      background: rgba(0,0,0,0.65);
      backdrop-filter: blur(8px);
      border-radius: 20px;
      border: 1px solid rgba(255,255,255,0.2);
    }
    .prompt-box {
      border: 1px solid var(--warning);
      background: rgba(210, 153, 34, 0.08);
      animation: pulse-border 2s infinite;
    }
    @keyframes pulse-border {
      0% { border-color: rgba(210, 153, 34, 0.4); }
      50% { border-color: rgba(210, 153, 34, 1.0); }
      100% { border-color: rgba(210, 153, 34, 0.4); }
    }
    .stat-row {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid rgba(255,255,255,0.05);
      font-size: 13px;
    }
    .stat-row:last-child {
      border-bottom: none;
    }
    .terminal-input {
      display: flex;
      gap: 8px;
      margin-top: 10px;
    }
    .terminal-input input {
      flex: 1;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--card-border);
      color: #fff;
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 13px;
      outline: none;
    }
    .terminal-output {
      background: rgba(0,0,0,0.4);
      border-radius: 8px;
      padding: 10px;
      font-family: monospace;
      font-size: 11px;
      color: #7ee787;
      max-height: 120px;
      overflow-y: auto;
      white-space: pre-wrap;
      margin-top: 8px;
      display: none;
    }
    .toast {
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(22, 27, 34, 0.95);
      border: 1px solid var(--primary);
      padding: 10px 18px;
      border-radius: 20px;
      font-size: 13px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
      z-index: 1000;
      display: none;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span class="brand-logo">⚡</span>
      <div>
        <div class="brand-title">Hermes Mobile Hub</div>
        <div style="font-size: 11px; color: var(--text-muted);" id="local-ip-label">Offline Direct</div>
      </div>
    </div>
    <div class="badge badge-offline">Offline LAN</div>
  </header>

  <!-- Antigravity Sandbox Live Approval Card (Dynamic) -->
  <div class="card full-width prompt-box" id="prompt-card" style="display: none; margin-bottom: 16px;">
    <div class="card-title" style="color: var(--warning);">
      <span>⚡ Antigravity Prompt Active</span>
      <span style="font-size: 10px; background: rgba(210,153,34,0.2); padding: 2px 6px; border-radius: 10px;">ACTION REQUIRED</span>
    </div>
    <p id="prompt-desc" style="font-size: 13px; margin-bottom: 12px; color: #fff;">Prompt loading...</p>
    <div style="display: flex; flex-direction: column; gap: 8px;" id="prompt-actions">
      <button class="btn btn-warning" onclick="sendAction('__ACTION_KEY_ENTER__')">⭐ (Best Option) Approve & Run</button>
      <div style="display: flex; gap: 8px;">
        <button class="btn btn-success" style="flex:1;" onclick="sendAction('__ACTION_KEY_Y__')">🟢 Always Allow ('y')</button>
        <button class="btn btn-danger" style="flex:1;" onclick="sendAction('__ACTION_KEY_N__')">🔴 Deny / Skip</button>
      </div>
      <button class="btn" style="background: rgba(255,255,255,0.04);" onclick="sendAction('__ACTION_AUTO_APPROVE_ON__')">⚡ Enable Auto-Approve Mode</button>
    </div>
  </div>

  <!-- Live Desktop Stealth Screen -->
  <div class="card full-width" style="margin-bottom: 16px;">
    <div class="card-title">
      <span>📸 Live Desktop Screen</span>
      <span id="screen-status" style="font-size: 11px; color: var(--success);">Stealth Active</span>
    </div>
    <div class="screen-container">
      <img id="desktop-img" class="screen-img" src="/api/screenshot" alt="Desktop Screenshot" onclick="refreshScreen()">
      <button class="screen-refresh-btn" onclick="refreshScreen()">🔄 Peek</button>
    </div>
  </div>

  <!-- Dual-State Master Toggles -->
  <div class="grid">
    <!-- Master Remote Switch -->
    <button class="btn btn-danger" id="btn-master-remote" onclick="toggleRemote()">
      🔴 Self-Use Mode (Pause)
    </button>
    <!-- Screen Lock / Unlock -->
    <button class="btn" id="btn-lock" onclick="toggleLock()">
      🔒 Lock Screen
    </button>
    <!-- Auto-Approve Mode -->
    <button class="btn" id="btn-auto" onclick="toggleAuto()">
      ⚡ Auto: OFF 🔴
    </button>
    <!-- Mute / Unmute -->
    <button class="btn" id="btn-mute" onclick="toggleMute()">
      🔇 Mute Audio
    </button>
  </div>

  <!-- Camera & Siren Section -->
  <div class="grid">
    <button class="btn" onclick="takeWebcam()">
      📷 Front Webcam Snap
    </button>
    <button class="btn" id="btn-cctv" onclick="toggleCCTV()">
      👁️ CCTV Motion Alert
    </button>
    <button class="btn" onclick="sendAction('__ACTION_VOL_UP__')">
      🔊 Vol +10%
    </button>
    <button class="btn" onclick="sendAction('__ACTION_VOL_DOWN__')">
      🔉 Vol -10%
    </button>
    <button class="btn btn-warning full-width" id="btn-hotspot" onclick="toggleHotspot()">
      📡 Laptop Hotspot: START (Hermes-Offline)
    </button>
  </div>

  <!-- System Health & Battery -->
  <div class="card full-width" style="margin-bottom: 16px;">
    <div class="card-title">
      <span>🔋 Laptop Live Health</span>
      <span style="cursor: pointer;" onclick="fetchStatus()">🔄</span>
    </div>
    <div class="stat-row">
      <span style="color: var(--text-muted);">Battery State:</span>
      <span id="stat-battery" style="font-weight: 600;">Checking...</span>
    </div>
    <div class="stat-row">
      <span style="color: var(--text-muted);">Wi-Fi / Network:</span>
      <span id="stat-wifi" style="font-weight: 600;">Connected</span>
    </div>
    <div class="stat-row">
      <span style="color: var(--text-muted);">Antigravity Watcher:</span>
      <span id="stat-watcher" style="color: var(--success); font-weight: 600;">Active</span>
    </div>
  </div>

  <!-- Offline Shell Command Box -->
  <div class="card full-width">
    <div class="card-title">
      <span>💻 Offline Terminal Console</span>
    </div>
    <div class="terminal-input">
      <input type="text" id="shell-cmd" placeholder="e.g. uptime, free -h, ls..." onkeydown="if(event.key==='Enter') runShell()">
      <button class="btn btn-primary" style="width: auto; padding: 0 16px;" onclick="runShell()">Run</button>
    </div>
    <div class="terminal-output" id="shell-out"></div>
  </div>

  <div class="toast" id="toast">Command sent!</div>

  <script>
    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.display = 'block';
      if (navigator.vibrate) navigator.vibrate(35);
      setTimeout(() => { t.style.display = 'none'; }, 2200);
    }

    async function sendAction(cmd) {
      try {
        const res = await fetch('/api/action', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({cmd: cmd})
        });
        const data = await res.json();
        showToast(data.message || 'Action executed!');
        fetchStatus();
        checkPrompt();
      } catch (e) {
        showToast('Error: ' + e);
      }
    }

    function refreshScreen() {
      const img = document.getElementById('desktop-img');
      img.src = '/api/screenshot?t=' + Date.now();
      showToast('📸 Screen peek refreshed!');
    }

    async function toggleRemote() {
      await sendAction('__ACTION_REMOTE_TOGGLE__');
    }

    async function toggleLock() {
      await sendAction('__ACTION_LOCK_TOGGLE__');
    }

    async function toggleAuto() {
      await sendAction('__ACTION_AUTO_APPROVE_TOGGLE__');
    }

    async function toggleMute() {
      await sendAction('__ACTION_MUTE__');
    }

    async function toggleHotspot() {
      const btn = document.getElementById('btn-hotspot');
      const isStart = btn.innerText.includes('START');
      showToast(isStart ? '📡 Starting laptop offline hotspot...' : '🛑 Stopping hotspot...');
      await sendAction(isStart ? '__ACTION_HOTSPOT_START__' : '__ACTION_HOTSPOT_STOP__');
      setTimeout(fetchStatus, 2500);
    }

    async function toggleCCTV() {
      await sendAction('__ACTION_CCTV_TOGGLE__');
    }

    async function takeWebcam() {
      showToast('📷 Capturing webcam snapshot...');
      window.open('/api/webcam?t=' + Date.now(), '_blank');
    }

    async function runShell() {
      const inp = document.getElementById('shell-cmd');
      const out = document.getElementById('shell-out');
      const cmd = inp.value.trim();
      if (!cmd) return;
      out.style.display = 'block';
      out.innerText = 'Executing: ' + cmd + '...';
      try {
        const res = await fetch('/api/shell', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({cmd: cmd})
        });
        const data = await res.json();
        out.innerText = data.output || '(No output)';
      } catch (e) {
        out.innerText = 'Error: ' + e;
      }
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        // Update IP label
        document.getElementById('local-ip-label').innerText = data.ip + ':7777';

        // Update Master Remote button
        const btnRemote = document.getElementById('btn-master-remote');
        if (data.remote_enabled) {
          btnRemote.className = 'btn btn-danger';
          btnRemote.innerText = '🔴 Self-Use Mode (Pause)';
        } else {
          btnRemote.className = 'btn btn-success';
          btnRemote.innerText = '🟢 Remote Mode (Activate)';
        }

        // Update Lock button
        const btnLock = document.getElementById('btn-lock');
        btnLock.innerText = data.is_locked ? '🔓 Unlock Screen' : '🔒 Lock Screen';

        // Update Auto button
        const btnAuto = document.getElementById('btn-auto');
        btnAuto.innerText = data.auto_approve ? '⚡ Auto: ON 🟢' : '⚡ Auto: OFF 🔴';

        // Update Mute button
        const btnMute = document.getElementById('btn-mute');
        btnMute.innerText = data.is_muted ? '🔊 Unmute Audio' : '🔇 Mute Audio';

        // Update CCTV button
        const btnCctv = document.getElementById('btn-cctv');
        btnCctv.innerText = data.cctv_active ? '🛑 Stop CCTV' : '👁️ CCTV Motion';

        // Update Hotspot button
        const btnHotspot = document.getElementById('btn-hotspot');
        if (btnHotspot) {
          if (data.hotspot_active) {
            btnHotspot.className = 'btn btn-danger full-width';
            btnHotspot.innerText = '🛑 Stop Hotspot (Hermes-Offline)';
          } else {
            btnHotspot.className = 'btn btn-warning full-width';
            btnHotspot.innerText = '📡 Laptop Hotspot: START (Hermes-Offline)';
          }
        }

        // Battery and stats
        document.getElementById('stat-battery').innerText = data.battery || 'Good';
        document.getElementById('stat-wifi').innerText = data.wifi || 'Connected';
        document.getElementById('stat-watcher').innerText = data.remote_enabled ? 'Active 🟢' : 'Paused (Self-Use) 🔴';
      } catch (e) {
        console.log('Status polling failed:', e);
      }
    }

    async function checkPrompt() {
      try {
        const res = await fetch('/api/prompt');
        const data = await res.json();
        const pCard = document.getElementById('prompt-card');
        const pDesc = document.getElementById('prompt-desc');
        if (data.active) {
          pCard.style.display = 'block';
          pDesc.innerText = data.text || 'Antigravity permission required.';
          if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
        } else {
          pCard.style.display = 'none';
        }
      } catch (e) {
        console.log('Prompt poll failed:', e);
      }
    }

    // Initialize & Pollers
    fetchStatus();
    checkPrompt();
    setInterval(fetchStatus, 4000);
    setInterval(checkPrompt, 2000);
  </script>
</body>
</html>
"""


# ==============================================================================
# Flask Endpoints
# ==============================================================================


@app.route("/")
def index():
    """Serve the offline mobile dashboard."""
    return Response(MOBILE_HTML, mimetype="text/html")


@app.route("/api/status")
def api_status():
    """Return live laptop state for mobile UI."""
    # Battery state
    bat_str = "Unavailable"
    try:
        out = subprocess.check_output(
            "upower -i $(upower -e | grep 'BAT') 2>/dev/null | grep -E 'percentage|state'",
            shell=True,
            text=True,
        ).strip()
        lines = [l.strip() for l in out.split("\n") if l.strip()]
        bat_str = ", ".join(lines) if lines else "Battery OK"
    except Exception:
        pass

    # Wifi
    wifi_str = "Local LAN"
    try:
        w_out = subprocess.check_output(
            "nmcli -t -f active,ssid dev wifi 2>/dev/null | grep '^yes'",
            shell=True,
            text=True,
        ).strip()
        if w_out:
            wifi_str = w_out.split(":")[-1]
    except Exception:
        pass

    # Mute
    is_muted = False
    try:
        m_out = subprocess.check_output("pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null", shell=True, text=True)
        is_muted = "yes" in m_out.lower()
    except Exception:
        pass

    # CCTV
    cctv_active = False
    try:
        import laptop_node

        cctv_active = getattr(laptop_node, "CCTV_ENABLED", False)
    except Exception:
        pass

    # Hotspot
    hotspot_active = False
    try:
        import offline_hotspot

        hotspot_active = offline_hotspot.is_hotspot_active()
    except Exception:
        pass

    return jsonify(
        {
            "ip": get_local_ip(),
            "remote_enabled": is_remote_access_enabled(),
            "auto_approve": get_auto_approve_state(),
            "is_locked": is_screen_locked(),
            "is_muted": is_muted,
            "cctv_active": cctv_active,
            "hotspot_active": hotspot_active,
            "battery": bat_str,
            "wifi": wifi_str,
        }
    )


@app.route("/api/prompt")
def api_prompt():
    """Return active Antigravity sandbox prompt or question."""
    prompt = get_offline_prompt()
    if prompt:
        return jsonify({"active": True, **prompt})
    return jsonify({"active": False})


@app.route("/api/action", methods=["POST"])
def api_action():
    """Execute live laptop command or control toggle."""
    data = request.get_json(force=True, silent=True) or {}
    cmd = data.get("cmd", "").strip()
    if not cmd:
        return jsonify({"success": False, "message": "Command empty"}), 400

    res = execute_action(cmd)
    return jsonify({"success": True, "message": res})


@app.route("/api/screenshot")
def api_screenshot():
    """Capture a clean, stealth screenshot and return raw image bytes."""
    if not is_remote_access_enabled():
        svg_placeholder = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">'
            '<rect width="100%" height="100%" fill="#0d1117"/>'
            '<text x="50%" y="45%" font-family="system-ui, sans-serif" font-size="20" font-weight="bold" fill="#f85149" text-anchor="middle">🔴 Self-Use Mode Active</text>'
            '<text x="50%" y="58%" font-family="system-ui, sans-serif" font-size="14" fill="#8b949e" text-anchor="middle">Screen capture paused while you use your laptop</text>'
            '</svg>'
        )
        return Response(svg_placeholder, mimetype="image/svg+xml", headers={"Cache-Control": "no-cache"})

    path = "/tmp/hermes_offline_screen.png"
    captured = capture_desktop_image(path)
    if captured and os.path.exists(captured):
        return send_file(captured, mimetype="image/png", max_age=0)
    return Response(b"", status=503, mimetype="image/png")


@app.route("/api/webcam")
def api_webcam():
    """Capture a webcam photo and stream it."""
    path = "/tmp/hermes_offline_webcam.jpg"
    try:
        os.system(f"ffmpeg -y -f v4l2 -i /dev/video0 -vframes 1 {path} 2>/dev/null")
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return send_file(path, mimetype="image/jpeg", max_age=0)
    except Exception:
        pass
    return "Webcam snapshot unavailable", 503


@app.route("/api/shell", methods=["POST"])
def api_shell():
    """Execute shell command on laptop directly from mobile."""
    data = request.get_json(force=True, silent=True) or {}
    cmd = data.get("cmd", "").strip()
    if not cmd:
        return jsonify({"output": "Empty command"})

    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=WORKSPACE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        out = (proc.stdout + "\n" + proc.stderr).strip()
        return jsonify({"output": out or "(Success with empty output)"})
    except Exception as e:
        return jsonify({"output": f"Error: {e}"})


@app.route("/qr")
def api_qr():
    """Generate a quick QR code to open the mobile hub on phone."""
    ip = get_local_ip()
    url = f"http://{ip}:7777"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


def run_offline_hub(port: int = 7777) -> None:
    """Start the offline mobile server."""
    ip = get_local_ip()
    logger.info(f"🌐 Hermes Offline Mobile Hub active on http://0.0.0.0:{port} (LAN: http://{ip}:{port})")
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_offline_hub()
