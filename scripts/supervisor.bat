@echo off

:: Navigate to the script's folder, then UP one level to the project root
cd /d "%~dp0.."

:LOOP
echo ==================================================
echo     SERVER & COLLECTOR SUPERVISOR -- HUPEDCARE
for /f "tokens=1-2 delims= " %%a in ("%date% %time%") do echo     %%a %%b
echo ==================================================
echo.

echo [1/3] Checking server.py status...

:: Search Windows processes for any python instance running server.py
wmic process where "name='python.exe'" get CommandLine | findstr /i "server.py" >nul

if %errorlevel% neq 0 (
    echo  - [ALERT] Server is down. Starting it now...
    start "HUPEDCARE_Server" /MIN cmd /c "call .venv\Scripts\activate.bat & python src\server.py"
    timeout /t 3 /nobreak >nul
    echo  - [OK] Server started in the background.
) else (
    echo  - [OK] Server is already running.
)

echo.
echo [2/3] Starting data update (collector.py)...
call .venv\Scripts\activate.bat
python src\collector.py

echo.
echo [3/3] Cycle finished. Next run in 24 hours.
echo.

:: Wait 86400 seconds = 24 hours (timeout accepts max 99999 s, so split in two waits)
timeout /t 99999 /nobreak >nul
timeout /t 99999 /nobreak >nul

goto LOOP