@echo off
REM start-web.bat - フロントエンド (Vite dev server) を起動
REM ブラウザで http://localhost:5173 を開いてください

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

echo [INFO] フロントエンド起動中... (http://localhost:5173)
cd /d "!SCRIPT_DIR!\client"

if not exist ".env.local" (
    echo [ERROR] client\.env.local が見つかりません。先に setup.bat を実行してください。
    exit /b 1
)

call npm run dev
endlocal
