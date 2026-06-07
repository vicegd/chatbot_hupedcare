#!/usr/bin/env sh

# Interval between supervision cycles (86400 seconds = 24 hours)
INTERVAL=86400

# Navigate to the script folder and then one level up (project root)
cd "$(dirname "$0")/.." || exit 1

while true; do
    echo "=================================================="
    echo "    SERVER & COLLECTOR SUPERVISOR -- HUPEDCARE"
    echo "    $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=================================================="
    echo ""

    echo "[1/3] Checking server.py status..."

    if ! pgrep -f "python3 src/server.py" > /dev/null; then
        echo "  - [ALERT] Server is down. Starting it now..."
        . .venv/bin/activate
        nohup python3 src/server.py > /dev/null 2>&1 &
        sleep 3
        echo "  - [OK] Server started in the background."
    else
        echo "  - [OK] Server is already running."
    fi

    echo ""
    echo "[2/3] Starting data update (collector.py)..."
    . .venv/bin/activate
    python3 src/collector.py

    echo ""
    echo "[3/3] Cycle finished. Next run in $INTERVAL seconds (24 h)."
    echo ""

    sleep $INTERVAL
done