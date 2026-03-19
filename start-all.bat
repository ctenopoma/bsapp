@echo off
REM start-all.bat - Windows: local PostgreSQL service + app launch
REM Requires PostgreSQL installed directly on Windows

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

echo =====================================================
echo   BSApp - Windows Start (Local Install)
echo =====================================================
echo.

REM -- 1. Check / Start PostgreSQL service ----------------
echo [1/3] Checking PostgreSQL service...

sc query postgresql-x64-16 >nul 2>&1
if errorlevel 1 (
    sc query postgresql-16 >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] PostgreSQL service not found.
        echo           Please start PostgreSQL manually.
        echo           Check service name: sc query state= all ^| findstr /i postgres
        echo.
        goto :skip_pg
    ) else (
        set "PG_SERVICE=postgresql-16"
    )
) else (
    set "PG_SERVICE=postgresql-x64-16"
)

sc query "!PG_SERVICE!" | findstr /i "RUNNING" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Starting PostgreSQL service...
    net start "!PG_SERVICE!" 2>nul
    if errorlevel 1 (
        echo [WARNING] Failed to start service. Run as Administrator.
    ) else (
        echo [OK] PostgreSQL started
    )
) else (
    echo [OK] PostgreSQL is already running
)
:skip_pg
echo.

REM -- 2. Port check --------------------------------------
echo [2/3] Checking ports...
if not defined POSTGRES_PORT set "POSTGRES_PORT=5432"
netstat -an | findstr "LISTENING" | findstr ":!POSTGRES_PORT! " >nul 2>&1
if not errorlevel 1 (
    echo [OK] PostgreSQL !POSTGRES_PORT! OK
) else (
    echo [WARNING] Port !POSTGRES_PORT! not open. Check PostgreSQL.
)
netstat -an | findstr "LISTENING" | findstr ":6333 " >nul 2>&1
if not errorlevel 1 (
    echo [OK] Qdrant 6333 OK
) else (
    echo [INFO] Qdrant 6333 not running - app works without RAG
)
echo.

REM -- 3. Launch app --------------------------------------
echo [3/3] Starting application...
echo.
echo   Backend  : http://localhost:8080
echo   Frontend : http://localhost:5173
echo.
echo   Press Ctrl+C in each window to stop
echo =====================================================
echo.

REM Launch backend in new window
start "BSApp Backend" cmd /k "cd /d ""!SCRIPT_DIR!\host"" && uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload"

REM Wait a bit before starting frontend
timeout /t 3 /nobreak >nul

REM Launch frontend in new window
start "BSApp Frontend" cmd /k "cd /d ""!SCRIPT_DIR!\client"" && npm run dev"

REM Open browser
timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"

echo [INFO] Started. Browser will open automatically.
endlocal
