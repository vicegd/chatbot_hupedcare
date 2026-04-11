#!/bin/bash

echo "=================================================="
echo "      DEPENDENCY SAVER -- HUPEDCARE"
echo "=================================================="
echo ""

# Navigate to the script's folder, then UP one level to the project root
cd "$(dirname "$0")/.." || exit

# Check if the virtual environment directory does NOT exist
if [ ! -d ".venv" ]; then
    echo "[ERROR] No virtual environment '.venv' found!"
    echo "Please run scripts/setup.sh first to create the environment."
    echo ""
    exit 1
fi

echo "[1/2] Activating virtual environment..."
source .venv/bin/activate

echo "[2/2] Scanning installed libraries and updating requirements.txt..."
# Use the exact same pip command you had in Windows
pip list --format=freeze --not-required > requirements.txt

echo ""
echo "=================================================="
echo "   SUCCESS! requirements.txt is now up to date."
echo "=================================================="
echo ""