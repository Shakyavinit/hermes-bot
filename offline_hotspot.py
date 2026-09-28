#!/usr/bin/env python3
"""
Hermes Autonomous Offline Hotspot Controller
Allows starting and stopping a dedicated offline Wi-Fi access point directly on the laptop.
When started:
- SSID: Hermes-Offline
- Password: hermes12345
- Local IP: 10.42.0.1
- Mobile Hub: http://10.42.0.1:7777
"""

import os
import subprocess
import sys
import time

HOTSPOT_CON_NAME = "Hermes-Hotspot"
HOTSPOT_SSID = "Hermes-Offline"
HOTSPOT_PASSWORD = "hermes12345"
HUB_PORT = 7777


def run_cmd(cmd: str) -> tuple[int, str]:
    """Run shell command and return exit code + output."""
    res = subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = (res.stdout + "\n" + res.stderr).strip()
    return res.returncode, out


def get_wifi_interface() -> str:
    """Find active Wi-Fi interface name (usually wlan0)."""
    code, out = run_cmd("nmcli -t -f DEVICE,TYPE dev | grep ':wifi$'")
    if code == 0 and out:
        return out.split(":")[0]
    return "wlan0"


def is_hotspot_active() -> bool:
    """Check if Hermes-Hotspot is currently active."""
    code, out = run_cmd(f"nmcli -t -f NAME,TYPE,STATE con show --active | grep '^{HOTSPOT_CON_NAME}:'")
    return code == 0 and bool(out)


def get_current_ip() -> str:
    """Get active IP."""
    try:
        from offline_hub import get_local_ip
        return get_local_ip()
    except Exception:
        code, out = run_cmd("hostname -I 2>/dev/null")
        parts = out.split()
        return parts[0] if parts else "127.0.0.1"


def print_qr_banner(url: str):
    """Print ASCII QR code in terminal if qrcode is available."""
    try:
        import qrcode
        qr = qrcode.QRCode()
        qr.add_data(url)
        qr.print_ascii(invert=True)
    except Exception:
        pass


def start_hotspot():
    """Start autonomous offline Wi-Fi Hotspot."""
    if is_hotspot_active():
        print(f"🟢 Hotspot '{HOTSPOT_SSID}' is already active!")
        ip = get_current_ip()
        print(f"📱 Connect phone to Wi-Fi: '{HOTSPOT_SSID}' (Password: '{HOTSPOT_PASSWORD}')")
        print(f"🌐 Mobile Hub URL: http://{ip}:{HUB_PORT}")
        return

    ifname = get_wifi_interface()
    print(f"📡 Starting offline hotspot on interface '{ifname}'...")

    # Delete any stale connection with same name to avoid duplicates
    run_cmd(f"nmcli con delete '{HOTSPOT_CON_NAME}' 2>/dev/null")

    # Create & start hotspot
    cmd = (
        f"nmcli dev wifi hotspot ifname '{ifname}' "
        f"con-name '{HOTSPOT_CON_NAME}' "
        f"ssid '{HOTSPOT_SSID}' "
        f"password '{HOTSPOT_PASSWORD}'"
    )
    code, out = run_cmd(cmd)
    if code != 0:
        print(f"❌ Failed to start hotspot:\n{out}")
        return

    time.sleep(2)
    ip = get_current_ip()
    hub_url = f"http://{ip}:{HUB_PORT}"

    print("=" * 60)
    print("🚀 HERMES OFFLINE HOTSPOT STARTED SUCCESSFULLY!")
    print("=" * 60)
    print(f"📶 Wi-Fi SSID:    {HOTSPOT_SSID}")
    print(f"🔑 Password:       {HOTSPOT_PASSWORD}")
    print(f"📍 Laptop IP:      {ip}")
    print(f"🌐 Mobile Hub URL: {hub_url}")
    print("=" * 60)
    print("📱 STEPS TO CONNECT FROM MOBILE PHONE (ZERO INTERNET):")
    print(f" 1. Phone me Wi-Fi settings kholein aur '{HOTSPOT_SSID}' se connect karein.")
    print(f" 2. Password daalein: '{HOTSPOT_PASSWORD}'")
    print(f" 3. Phone browser (Chrome/Safari) me kholein: {hub_url}")
    print(" 4. 'Add to Home Screen' karke App ki tarah save kar lein!")
    print("=" * 60)

    print_qr_banner(hub_url)


def stop_hotspot():
    """Stop hotspot and restore normal Wi-Fi connection."""
    print("🛑 Stopping offline hotspot...")
    run_cmd(f"nmcli con down '{HOTSPOT_CON_NAME}' 2>/dev/null")
    run_cmd(f"nmcli con delete '{HOTSPOT_CON_NAME}' 2>/dev/null")
    time.sleep(1)
    # Rescan & reconnect to default Wi-Fi
    run_cmd("nmcli dev wifi rescan 2>/dev/null")
    print("✅ Hotspot stopped. Normal Wi-Fi restored.")


def status():
    """Show current network and hub status."""
    active = is_hotspot_active()
    ip = get_current_ip()
    hub_url = f"http://{ip}:{HUB_PORT}"

    print("=" * 50)
    print("📊 HERMES OFFLINE HUB STATUS")
    print("=" * 50)
    print(f"• Hotspot Status: {'ACTIVE 🟢' if active else 'INACTIVE ⚪'}")
    if active:
        print(f"• SSID:           {HOTSPOT_SSID}")
        print(f"• Password:       {HOTSPOT_PASSWORD}")
    print(f"• Local IP:       {ip}")
    print(f"• Mobile Hub URL: {hub_url}")
    print(f"• QR Link:        {hub_url}/qr")
    print("=" * 50)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 offline_hotspot.py [start|stop|status|qr]")
        status()
        return

    arg = sys.argv[1].lower()
    if arg == "start":
        start_hotspot()
    elif arg == "stop":
        stop_hotspot()
    elif arg == "status":
        status()
    elif arg == "qr":
        ip = get_current_ip()
        hub_url = f"http://{ip}:{HUB_PORT}"
        print_qr_banner(hub_url)
        print(f"Mobile Hub URL: {hub_url}")
    else:
        print(f"Unknown action: {arg}. Available: start, stop, status, qr")


if __name__ == "__main__":
    main()
