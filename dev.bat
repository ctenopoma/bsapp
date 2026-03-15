@echo off
REM dev.bat - Tauri dev/build/install/release launcher for Windows
REM
REM Bypasses rustup shims (.cargo\bin) to avoid gitoxide ReparsePoint
REM trust check failure (os error 448) on Windows Security Update KB5079473+.
REM
REM Usage:
REM   dev.bat          (start dev server)
REM   dev.bat build    (release build only)
REM   dev.bat release  (build + copy to host/client_dist + update version.json)
REM   dev.bat install  (npm install)

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
REM Remove trailing backslash
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

REM --- Detect active Rust toolchain ---
set "TOOLCHAIN_BIN="

where rustup >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=1" %%t in ('rustup show active-toolchain 2^>nul') do (
        set "TC_NAME=%%t"
    )
)

if not defined RUSTUP_HOME set "RUSTUP_HOME=%USERPROFILE%\.rustup"
if defined TC_NAME (
    if exist "!RUSTUP_HOME!\toolchains\!TC_NAME!\bin\cargo.exe" (
        set "TOOLCHAIN_BIN=!RUSTUP_HOME!\toolchains\!TC_NAME!\bin"
    )
)

REM Fallback: find any stable toolchain
if not defined TOOLCHAIN_BIN (
    for /d %%d in ("!RUSTUP_HOME!\toolchains\stable-*") do (
        if exist "%%d\bin\cargo.exe" set "TOOLCHAIN_BIN=%%d\bin"
    )
)

if not defined TOOLCHAIN_BIN (
    echo ERROR: Rust toolchain not found. Install rustup and a stable toolchain.
    exit /b 1
)

echo [INFO] Rust toolchain: !TOOLCHAIN_BIN!

REM --- Rebuild PATH: remove .cargo\bin, prepend toolchain bin ---
set "NEW_PATH=!TOOLCHAIN_BIN!"
set "REMAINING=!PATH!"
:parse_path
for /f "tokens=1* delims=;" %%a in ("!REMAINING!") do (
    echo %%a | findstr /i /c:"\.cargo\bin" >nul
    if errorlevel 1 (
        set "NEW_PATH=!NEW_PATH!;%%a"
    )
    set "REMAINING=%%b"
    if defined REMAINING goto :parse_path
)
set "PATH=!NEW_PATH!"

REM --- Parse command ---
set "CMD=%~1"
if "!CMD!"=="" set "CMD=dev"

REM --- Move to client directory ---
cd /d "!SCRIPT_DIR!\client"
if not exist "package.json" (
    echo ERROR: client/package.json not found.
    exit /b 1
)

REM --- Execute ---
if /i "!CMD!"=="install" (
    echo [INFO] Running npm install...
    call npm install
    goto :done
)
if /i "!CMD!"=="dev" (
    taskkill /IM bsapp.exe /F >nul 2>&1
    echo [INFO] Running tauri dev...
    call npm run tauri dev
    goto :done
)
if /i "!CMD!"=="build" (
    echo [INFO] Running tauri build...
    call npm run tauri build
    goto :done
)
if /i "!CMD!"=="release" (
    goto :release
)
echo Usage: dev.bat [dev^|build^|install^|release]
exit /b 1

REM ================================================================
REM  Release: build + copy artifacts + update version.json
REM ================================================================
:release
echo [INFO] Running release build...
call npm run tauri build
if errorlevel 1 (
    echo ERROR: Build failed.
    exit /b 1
)

set "DIST_DIR=!SCRIPT_DIR!\host\client_dist"
set "BUNDLE_DIR=!SCRIPT_DIR!\client\src-tauri\target\release\bundle"
set "TAURI_CONF=!SCRIPT_DIR!\client\src-tauri\tauri.conf.json"

if not exist "!BUNDLE_DIR!" (
    echo ERROR: Bundle directory not found: !BUNDLE_DIR!
    exit /b 1
)

echo.
echo [INFO] Copying artifacts to !DIST_DIR!...
if not exist "!DIST_DIR!" mkdir "!DIST_DIR!"

set "FOUND="
REM for /r does not accept delayed expansion vars; use pushd
pushd "!BUNDLE_DIR!"
for /r %%f in (*.exe *.msi) do (
    copy /y "%%f" "!DIST_DIR!\" >nul
    echo   %%~nxf
    set "FOUND=1"
)
popd
if not defined FOUND (
    echo WARNING: No installer artifacts found in !BUNDLE_DIR!
)

REM Update version.json from tauri.conf.json
if exist "!DIST_DIR!\version.json" if exist "!TAURI_CONF!" (
    for /f "tokens=2 delims=:, " %%v in ('findstr /c:"\"version\"" "!TAURI_CONF!"') do (
        set "VER=%%~v"
        goto :got_version
    )
)
:got_version
if defined VER (
    echo [INFO] Updating version.json to v!VER!...
    powershell -Command "$j = Get-Content '!DIST_DIR!\version.json' -Raw -Encoding UTF8 | ConvertFrom-Json; $j.version = '!VER!'; $j.windows.filename = 'BSApp_' + '!VER!' + '_x64-setup.exe'; $j.windows.url = '/api/update/download/BSApp_' + '!VER!' + '_x64-setup.exe'; $j.linux.filename = 'BSApp_' + '!VER!' + '_amd64.AppImage'; $j.linux.url = '/api/update/download/BSApp_' + '!VER!' + '_amd64.AppImage'; $j | ConvertTo-Json -Depth 10 | Out-File '!DIST_DIR!\version.json' -Encoding utf8NoBOM"
)

echo.
echo [INFO] Release artifacts:
dir /b "!DIST_DIR!"
echo.
echo =====================================================
echo   Release build complete!
echo   Output: !DIST_DIR!
echo =====================================================

:done
endlocal
