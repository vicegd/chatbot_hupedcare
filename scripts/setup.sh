#!/bin/bash

echo "=================================================="
echo "        ENVIRONMENT SETUP -- HUPEDCARE"
echo "=================================================="
echo ""

# Navigate to the script's folder, then UP one level to the project root
cd "$(dirname "$0")/.." || exit

# Check if the virtual environment directory does NOT exist
if [ ! -d ".venv" ]; then
    echo "[1/3] Creating virtual environment (.venv)..."
    python3 -m venv .venv
else
    echo "[1/3] Virtual environment already exists. Skipping creation..."
fi

echo "[2/3] Activating the environment..."
# In Linux, we use 'source' and the path is 'bin' instead of 'Scripts'
source .venv/bin/activate

echo "[3/3] Installing/Updating libraries from requirements.txt..."
# Send the pip upgrade output to null to keep the console clean, equivalent to >nul
python3 -m pip install --upgrade pip > /dev/null
pip install -r requirements.txt

echo ""
echo "=================================================="
echo "   ALL SET! The environment is 100% configured."
echo "=================================================="
echo ""