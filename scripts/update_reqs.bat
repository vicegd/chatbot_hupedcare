@echo off
echo ==================================================
echo      DEPENDENCY SAVER -- HUPEDCARE
echo ==================================================
echo.

:: Navigate to the script's folder, then UP one level to the project root
cd /d "%~dp0.."

IF NOT EXIST .venv (
    echo [ERROR] No virtual environment '.venv' found!
    echo Please run scripts\setup.bat first to create the environment.
    echo.
    pause
    exit /b
)

echo [1/2] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [2/2] Scanning installed libraries and updating requirements.txt...
pip list --format=freeze --not-required > requirements.txt

echo.
echo ==================================================
echo   SUCCESS! requirements.txt is now up to date.
echo ==================================================
echo.
pause