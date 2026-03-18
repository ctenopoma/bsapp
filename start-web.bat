@echo off
REM start-web.bat - Start frontend (Vite dev server)
REM Open http://localhost:5173 in your browser

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

echo [INFO] Starting frontend... (http://localhost:5173)
cd /d "!SCRIPT_DIR!\client"

if not exist ".env.local" (
    echo [ERROR] client\.env.local not found. Run setup.bat first.
    exit /b 1
)

call npm run dev
endlocal
