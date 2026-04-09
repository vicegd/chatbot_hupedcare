@echo off
echo ==================================================
echo       HUPEDCARE SUPERVISOR - RAG & SERVER
echo ==================================================

:: 1. Navigate to the exact project directory
cd /d "C:\Users\Vicente\OneDrive - Universidad de Oviedo\Proyectos y contratos de investigacion\HUPEDCARE\chatbot"

:: 2. Check if server.py is currently running
echo [1/3] Checking server.py status...

:: Search Windows processes for any python instance running server.py
wmic process where "name='python.exe'" get CommandLine | findstr /i "server.py" >nul

if %errorlevel% neq 0 (
    echo  - [ALERT] Server is down. Starting it now...
    :: Open a new minimized console (/MIN) for the server to avoid blocking this script
    start "HUPEDCARE_Server" /MIN cmd /c "call .venv\Scripts\activate.bat & python src\server.py"
    :: Give the server 3 seconds to boot up properly
    timeout /t 3 /nobreak >nul
    echo  - [OK] Server started in the background.
) else (
    echo  - [OK] Server is already running.
)

:: 3. Run the collector (collector.py)
echo.
echo [2/3] Starting data update (collector.py)...
call .venv\Scripts\activate.bat
python src\collector.py

echo.
echo [3/3] Supervision process finished.