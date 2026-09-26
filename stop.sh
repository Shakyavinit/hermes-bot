#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "🛑 Stopping Hermes Agent..."
if pkill -f "python3 bot.py"; then
    echo "✅ Hermes Agent stopped successfully."
else
    echo "ℹ️ Hermes Agent was not running."
fi
