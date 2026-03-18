#!/usr/bin/env bash
# build-client.sh
# =================
# Tauri client build script.
# Supports: Docker (Linux/Windows cross-compile) and local Windows build.
#
# Usage:
#   ./build-client.sh [linux|windows|local]
#     linux   : Docker cross-compile for Linux  (.deb / .AppImage)
#     windows : Docker cross-compile for Windows (.exe / .msi via MinGW)
#     local   : Build on the current Windows machine (bypasses rustup shim issue)
#
# Output:
#   host/client_dist/

set -euo pipefail

# ----------------------------------------------------------------
# Tauri signing key (override via environment variable if needed)
# ----------------------------------------------------------------
: "${TAURI_SIGNING_PRIVATE_KEY_PATH:=$HOME/.tauri/bsapp.key}"
: "${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:=}"
export TAURI_SIGNING_PRIVATE_KEY_PATH
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-linux}"
IMAGE_NAME="bsapp-client-builder"
DIST_DIR="$SCRIPT_DIR/host/client_dist"
TAURI_CONF="$SCRIPT_DIR/client/src-tauri/tauri.conf.json"

# ----------------------------------------------------------------
# Validate argument
# ----------------------------------------------------------------
case "$TARGET" in
  linux|windows|local) ;;
  *)
    echo "Usage: $0 [linux|windows|local]" >&2
    exit 1
    ;;
esac

echo "====================================================="
echo "  BSApp Client Build"
echo "  Target : $TARGET"
echo "  Source  : $SCRIPT_DIR/client"
echo "  Output : $DIST_DIR"
echo "====================================================="

# ----------------------------------------------------------------
# Fix PATH for rustup shim ReparsePoint issue (Windows local build)
# KB5079473+ tightened ReparsePoint security, causing gitoxide
# os error 448 when cargo/rustc are resolved via .cargo/bin shims.
# ----------------------------------------------------------------
fix_rustup_path() {
  if [[ "$(uname -s)" != *MINGW* && "$(uname -s)" != *MSYS* && "$(uname -s)" != *CYGWIN* ]]; then
    return
  fi

  local rustup_home="${RUSTUP_HOME:-$USERPROFILE/.rustup}"
  local tc_name
  tc_name=$(rustup show active-toolchain 2>/dev/null | awk '{print $1}') || true
  local tc_bin=""

  if [[ -n "$tc_name" && -f "$rustup_home/toolchains/$tc_name/bin/cargo.exe" ]]; then
    tc_bin="$rustup_home/toolchains/$tc_name/bin"
  else
    # Fallback: find any stable toolchain
    for d in "$rustup_home"/toolchains/stable-*; do
      if [[ -f "$d/bin/cargo.exe" ]]; then
        tc_bin="$d/bin"
        break
      fi
    done
  fi

  if [[ -z "$tc_bin" ]]; then
    echo "WARNING: Could not find Rust toolchain bin directory" >&2
    return
  fi

  echo "[INFO] Using toolchain: $tc_bin"
  # Remove .cargo/bin from PATH; prepend toolchain bin
  PATH="$tc_bin:$(echo "$PATH" | tr ':' '\n' | grep -v '\.cargo/bin' | tr '\n' ':')"
  export PATH
}

# ----------------------------------------------------------------
# Update version.json with version from tauri.conf.json
# ----------------------------------------------------------------
update_version_json() {
  local version="$1"

  if [[ -z "$version" || ! -f "$DIST_DIR/version.json" ]]; then
    return
  fi

  echo "[INFO] Updating version.json to v${version}..."

  if command -v jq &>/dev/null; then
    local tmp
    tmp=$(mktemp)
    jq --arg v "$version" '
      .version = $v |
      .windows.filename = "BSApp_\($v)_x64-setup.exe" |
      .windows.url = "/api/update/download/BSApp_\($v)_x64-setup.exe" |
      .linux.filename = "BSApp_\($v)_amd64.AppImage" |
      .linux.url = "/api/update/download/BSApp_\($v)_amd64.AppImage"
    ' "$DIST_DIR/version.json" > "$tmp"
    mv "$tmp" "$DIST_DIR/version.json"
  else
    # Fallback: sed-based update
    sed -i \
      -e "s/\"version\"[[:space:]]*:[[:space:]]*\"[^\"]*\"/\"version\": \"$version\"/" \
      -e "s/BSApp_[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*_x64-setup\.exe/BSApp_${version}_x64-setup.exe/g" \
      -e "s/BSApp_[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*_amd64\.AppImage/BSApp_${version}_amd64.AppImage/g" \
      "$DIST_DIR/version.json"
  fi
}

# ----------------------------------------------------------------
# Local Windows build
# ----------------------------------------------------------------
if [[ "$TARGET" == "local" ]]; then
  fix_rustup_path

  echo ""
  echo "[1/3] Building..."
  cd "$SCRIPT_DIR/client"
  npm install
  npm run tauri build

  echo ""
  echo "[2/3] Copying artifacts to $DIST_DIR..."
  mkdir -p "$DIST_DIR"
  BUNDLE_DIR="$SCRIPT_DIR/client/src-tauri/target/release/bundle"
  if [[ -d "$BUNDLE_DIR" ]]; then
    find "$BUNDLE_DIR" -type f \( -name '*.exe' -o -name '*.msi' \) -exec cp -v {} "$DIST_DIR/" \;
  else
    echo "WARNING: Bundle directory not found: $BUNDLE_DIR" >&2
  fi

  echo ""
  echo "[3/3] Updating version.json..."
else
  # ----------------------------------------------------------------
  # Docker build (linux / windows cross-compile)
  # ----------------------------------------------------------------
  echo ""
  echo "[1/4] Building Docker image..."
  docker build \
    -f "$SCRIPT_DIR/Dockerfile.client" \
    -t "$IMAGE_NAME" \
    "$SCRIPT_DIR"

  if [[ "$TARGET" == "windows" ]]; then
    RUST_TARGET="x86_64-pc-windows-gnu"
    BUNDLE_SUBDIR="$RUST_TARGET/release/bundle"
    BUNDLE_DIR_IN_CONTAINER="/build/client/src-tauri/target/$BUNDLE_SUBDIR"
    BUILD_CMD="find '$BUNDLE_DIR_IN_CONTAINER' -type f \( -name '*.exe' -o -name '*.msi' \) -delete 2>/dev/null || true; cd /build/client && npm ci && npm run tauri build -- --target $RUST_TARGET"
    ARTIFACT_PATTERNS=("*.exe" "*.msi")
  else
    RUST_TARGET="x86_64-unknown-linux-gnu"
    BUNDLE_SUBDIR="release/bundle"
    BUNDLE_DIR_IN_CONTAINER="/build/client/src-tauri/target/$BUNDLE_SUBDIR"
    BUILD_CMD="find '$BUNDLE_DIR_IN_CONTAINER' -type f \( -name '*.AppImage' -o -name '*.deb' \) -delete 2>/dev/null || true; cd /build/client && npm ci && npm run tauri build"
    ARTIFACT_PATTERNS=("*.AppImage" "*.deb")
  fi

  BUNDLE_DIR="$SCRIPT_DIR/client/src-tauri/target/$BUNDLE_SUBDIR"

  echo ""
  echo "[2/4] Building in container (target: $RUST_TARGET)..."
  docker run --rm \
    -v "$SCRIPT_DIR/client:/build/client" \
    "$IMAGE_NAME" \
    bash -c "$BUILD_CMD"

  echo ""
  echo "[3/4] Copying artifacts to $DIST_DIR..."
  mkdir -p "$DIST_DIR"

  if [[ -d "$BUNDLE_DIR" ]]; then
    for pattern in "${ARTIFACT_PATTERNS[@]}"; do
      find "$DIST_DIR" -maxdepth 1 -type f -name "$pattern" -delete
      find "$BUNDLE_DIR" -type f -name "$pattern" -exec cp -v {} "$DIST_DIR/" \;
    done
  else
    echo "WARNING: Bundle directory not found: $BUNDLE_DIR" >&2
  fi

  echo ""
  echo "[4/4] Updating version.json..."
fi

# ----------------------------------------------------------------
# Update version.json from tauri.conf.json
# ----------------------------------------------------------------
TAURI_VERSION=$(grep '"version"' "$TAURI_CONF" \
  | head -1 | sed 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

update_version_json "$TAURI_VERSION"

echo ""
echo "====================================================="
echo "  Build complete!"
echo "  Output: $DIST_DIR"
ls -lh "$DIST_DIR/" 2>/dev/null || true
echo "====================================================="
