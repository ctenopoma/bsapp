@echo off
REM start-host.bat - バックエンド (FastAPI + PostgreSQL) を起動

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

echo [INFO] バックエンド起動中... (http://localhost:8080)
cd /d "!SCRIPT_DIR!\host"

if not exist ".env" (
    echo [ERROR] host\.env が見つかりません。先に setup.bat を実行してください。
    exit /b 1
)

uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
endlocal
