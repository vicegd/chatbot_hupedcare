#!/usr/bin/env sh

echo "=================================================="
echo "    SERVER & COLLECTOR SUPERVISOR -- HUPEDCARE"
echo "=================================================="
echo ""

# Navigate to the script's folder, then UP one level to the project root
cd "$(dirname "$0")/.." || exit

echo "[1/3] Checking server.py status..."

# Search Linux processes for any python instance running server.py
# 'pgrep -f' is the Linux equivalent of 'wmic process get CommandLine | findstr'
if ! pgrep -f "python3 src/server.py" > /dev/null; then
    echo "  - [ALERT] Server is down. Starting it now..."
    
    # Activate the environment first
    . .venv/bin/activate
    
    # Start the server in the background. 
    # 'nohup' and '&' are the Linux equivalent of Windows 'start /MIN'.
    # '> /dev/null 2>&1' hides the output to prevent it from blocking this script.
    nohup python3 src/server.py > /dev/null 2>&1 &
    
    # Wait 3 seconds
    sleep 3
    echo "  - [OK] Server started in the background."
else
    echo "  - [OK] Server is already running."
fi

echo ""
echo "[2/3] Starting data update (collector.py)..."
# Ensure the environment is activated (in case the if block was skipped)
. .venv/bin/activate
python3 src/collector.py

echo ""
echo "[3/3] Supervision process finished."