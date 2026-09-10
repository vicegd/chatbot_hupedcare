#!/usr/bin/env sh

echo "=================================================="
echo "        ENVIRONMENT SETUP -- HUPEDCARE"
echo "=================================================="
echo ""

# Navigate to the script folder and then one level up (project root)
cd "$(dirname "$0")/.." || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 not found in PATH."
    exit 1
fi

# Create virtual environment only when missing
if [ ! -d ".venv" ]; then
    echo "[1/3] Creating virtual environment .venv..."
    python3 -m venv .venv
else
    echo "[1/3] Virtual environment already exists. Skipping creation."
fi

echo "[2/3] Activating the environment..."
# POSIX-compatible activation (works with /bin/sh)
source .venv/bin/activate

echo "[3/3] Installing/Updating libraries from requirements.txt..."
python3 -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo ""
echo "=================================================="
echo "   ALL SET! The environment is 100% configured."
echo "=================================================="
echo ""