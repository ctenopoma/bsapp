@echo off
REM setup.bat - 初回セットアップ (DB作成 + 依存パッケージインストール)
REM
REM 使い方:
REM   setup.bat
REM
REM 必要なもの:
REM   - Python 3.13+ + uv
REM   - Node.js 18+
REM   - PostgreSQL (psql コマンドが通ること)

setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

echo =====================================================
echo   BSApp Web - 初回セットアップ
echo =====================================================
echo.

REM ── 1. PostgreSQL DB作成 ──────────────────────────────
echo [1/3] PostgreSQL データベース作成...
echo   ユーザー: bsapp / パスワード: bsapp / DB: bsapp
echo.

where psql >nul 2>&1
if errorlevel 1 (
    echo [WARNING] psql が見つかりません。PostgreSQL の PATH を確認してください。
    echo           手動で以下を実行してください:
    echo             psql -U postgres -c "CREATE USER bsapp WITH PASSWORD 'bsapp';"
    echo             psql -U postgres -c "CREATE DATABASE bsapp OWNER bsapp;"
    echo.
) else (
    psql -U postgres -c "CREATE USER bsapp WITH PASSWORD 'bsapp';" 2>nul
    psql -U postgres -c "CREATE DATABASE bsapp OWNER bsapp;" 2>nul
    echo   完了 (既に存在する場合はエラーが出ますが問題ありません)
    echo.
)

REM ── 2. バックエンド .env 作成 ────────────────────────
echo [2/3] バックエンド設定ファイル作成...
if not exist "!SCRIPT_DIR!\host\.env" (
    copy "!SCRIPT_DIR!\host\.env.example" "!SCRIPT_DIR!\host\.env" >nul
    echo   host\.env を作成しました
) else (
    echo   host\.env は既に存在します (スキップ)
)
echo.

REM ── 3. フロントエンド .env.local 作成 ────────────────
if not exist "!SCRIPT_DIR!\client\.env.local" (
    copy "!SCRIPT_DIR!\client\.env.example" "!SCRIPT_DIR!\client\.env.local" >nul
    echo   client\.env.local を作成しました
) else (
    echo   client\.env.local は既に存在します (スキップ)
)
echo.

REM ── 4. バックエンド依存パッケージ ────────────────────
echo [3/3] パッケージインストール...
echo   [backend] uv sync ...
cd /d "!SCRIPT_DIR!\host"
uv sync
if errorlevel 1 (
    echo [ERROR] uv sync 失敗。uv がインストールされているか確認してください。
    exit /b 1
)

echo   [frontend] npm install ...
cd /d "!SCRIPT_DIR!\client"
call npm install
if errorlevel 1 (
    echo [ERROR] npm install 失敗。
    exit /b 1
)

echo.
echo =====================================================
echo   セットアップ完了！
echo
echo   次のステップ:
echo     start-host.bat   ... バックエンドを起動
echo     start-web.bat    ... フロントエンドを起動
echo     start-all.bat    ... 両方まとめて起動
echo =====================================================
endlocal
