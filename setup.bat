@echo off
REM setup.bat - Initial setup (DB creation + dependency install)
REM
REM Requirements:
REM   - Python 3.13+ with uv
REM   - Node.js 18+
REM   - PostgreSQL (psql must be in PATH)

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

echo =====================================================
echo   BSApp Web - Initial Setup
echo =====================================================
echo.

REM -- 1. Create PostgreSQL DB ----------------------------
echo [1/3] Creating PostgreSQL database...
echo   User: bsapp / Password: bsapp / DB: bsapp
echo.

where psql >nul 2>&1
if errorlevel 1 (
    echo [WARNING] psql not found. Check PostgreSQL PATH.
    echo           Run manually:
    echo             psql -U postgres -c "CREATE USER bsapp WITH PASSWORD 'bsapp';"
    echo             psql -U postgres -c "CREATE DATABASE bsapp OWNER bsapp;"
    echo.
) else (
    psql -U postgres -c "CREATE USER bsapp WITH PASSWORD 'bsapp';" 2>nul
    psql -U postgres -c "CREATE DATABASE bsapp OWNER bsapp;" 2>nul
    echo   Done (errors are OK if already exists)
    echo.
)

REM -- 2. Create backend .env -----------------------------
echo [2/3] Creating config files...
if not exist "!SCRIPT_DIR!\host\.env" (
    copy "!SCRIPT_DIR!\host\.env.example" "!SCRIPT_DIR!\host\.env" >nul
    echo   Created host\.env
) else (
    echo   host\.env already exists (skipped)
)
echo.

REM -- 3. Create frontend .env.local ----------------------
if not exist "!SCRIPT_DIR!\client\.env.local" (
    copy "!SCRIPT_DIR!\client\.env.example" "!SCRIPT_DIR!\client\.env.local" >nul
    echo   Created client\.env.local
) else (
    echo   client\.env.local already exists (skipped)
)
echo.

REM -- 4. Install dependencies ----------------------------
echo [3/3] Installing packages...
echo   [backend] uv sync ...
cd /d "!SCRIPT_DIR!\host"
uv sync
if errorlevel 1 (
    echo [ERROR] uv sync failed. Check uv is installed.
    exit /b 1
)

echo   [frontend] npm install ...
cd /d "!SCRIPT_DIR!\client"
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed.
    exit /b 1
)

echo.
echo =====================================================
echo   Setup complete!
echo.
echo   Next steps:
echo     start-host.bat   ... Start backend
echo     start-web.bat    ... Start frontend
echo     start-all.bat    ... Start both
echo =====================================================
endlocal
