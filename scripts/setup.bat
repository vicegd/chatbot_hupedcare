@echo off
echo ==================================================
echo        ENVIRONMENT SETUP -- HUPEDCARE
echo ==================================================
echo.

:: Navigate to the script's folder, then UP one level to the project root
cd /d "%~dp0.."

IF NOT EXIST .venv (
    echo [1/3] Creating virtual environment .venv...
    python -m venv .venv
) ELSE (
    echo [1/3] Virtual environment already exists. Skipping creation.
)

echo [2/3] Activating the environment...
call .venv\Scripts\activate.bat

echo [3/3] Installing/Updating libraries from requirements.txt...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

echo.
echo ==================================================
echo   ALL SET! The environment is 100%% configured.
echo ==================================================
echo.
pause