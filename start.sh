#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

mkdir -p logs

echo "=================================================="
echo "🤖 Starting Hermes Autonomous Telegram Agent..."
echo "Bot: @Dadijiibot"
echo "=================================================="

# Check if already running
if pgrep -f "python3 bot.py" > /dev/null; then
    echo "⚠️ Hermes Agent is already running! (PID: $(pgrep -f 'python3 bot.py'))"
    exit 0
fi

nohup python3 bot.py >> logs/agent.log 2>&1 &
PID=$!
echo "✅ Hermes Agent started in background with PID: $PID"
echo "📜 View live logs anytime with: tail -f logs/agent.log"
