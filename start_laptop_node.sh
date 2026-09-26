#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
mkdir -p logs

if pgrep -f "python3 laptop_node.py" > /dev/null; then
    echo "⚠️ Hermes Laptop Node is already running!"
    exit 0
fi

nohup python3 laptop_node.py >> logs/laptop_node.log 2>&1 &
echo "✅ Hermes Laptop Node started in background with PID: $!"
echo "📜 Logs: tail -f logs/laptop_node.log"
