@echo off
REM start-all.bat - バックエンドとフロントエンドを別ウィンドウで同時起動

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

echo =====================================================
echo   BSApp Web 起動
echo =====================================================
echo.
echo   バックエンド : http://localhost:8080
echo   フロントエンド: http://localhost:5173
echo.
echo   終了するには各ウィンドウで Ctrl+C を押してください
echo =====================================================
echo.

REM バックエンドを新しいウィンドウで起動
start "BSApp Backend" cmd /k "cd /d ""!SCRIPT_DIR!\host"" && uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload"

REM 少し待ってからフロントエンドを起動 (DBが先に立ち上がるのを待つ)
timeout /t 3 /nobreak >nul

REM フロントエンドを新しいウィンドウで起動
start "BSApp Frontend" cmd /k "cd /d ""!SCRIPT_DIR!\client"" && npm run dev"

REM ブラウザを開く (3秒後)
timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"

echo [INFO] 起動しました。ブラウザが自動で開きます。
endlocal
