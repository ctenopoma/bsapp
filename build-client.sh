#!/usr/bin/env bash
# build-client.sh
# =================
# Ubuntu 上で Tauri クライアントをビルドするスクリプト。
# Docker コンテナを使い、ビルド後にインストーラーを host/client_dist/ へコピーする。
#
# 使い方:
#   chmod +x build-client.sh
#   ./build-client.sh [linux|windows]  (デフォルト: linux)
#
# 出力先:
#   Linux  : client/src-tauri/target/release/bundle/
#   Windows: client/src-tauri/target/x86_64-pc-windows-gnu/release/bundle/
#
# 前提:
#   - Docker がインストールされていること
#   - このスクリプトをリポジトリルート (bsapp/) から実行すること

set -euo pipefail

# ----------------------------------------------------------------
# 引数解析
# ----------------------------------------------------------------
TARGET="${1:-linux}"
if [[ "$TARGET" != "linux" && "$TARGET" != "windows" ]]; then
  echo "Usage: $0 [linux|windows]" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="bsapp-client-builder"
DIST_DIR="$SCRIPT_DIR/host/client_dist"

echo "====================================================="
echo "  BSApp クライアント ビルド"
echo "  ターゲット : $TARGET"
echo "  ソース     : $SCRIPT_DIR/client"
echo "  出力先     : $DIST_DIR"
echo "====================================================="

# ----------------------------------------------------------------
# Docker イメージのビルド (変更がなければキャッシュを使用)
# ----------------------------------------------------------------
echo ""
echo "[1/3] Docker ビルドイメージを作成中..."
docker build \
  -f "$SCRIPT_DIR/Dockerfile.client" \
  -t "$IMAGE_NAME" \
  "$SCRIPT_DIR"

# ----------------------------------------------------------------
# コンテナ内でのビルドスクリプト
# ----------------------------------------------------------------
if [[ "$TARGET" == "windows" ]]; then
  RUST_TARGET="x86_64-pc-windows-gnu"
  BUNDLE_SUBDIR="$RUST_TARGET/release/bundle"
  BUNDLE_DIR_IN_CONTAINER="/build/client/src-tauri/target/$BUNDLE_SUBDIR"
  BUILD_CMD="find '$BUNDLE_DIR_IN_CONTAINER' -type f \\( -name '*.exe' -o -name '*.msi' \\) -delete 2>/dev/null || true; cd /build/client && npm ci && npm run tauri build -- --target $RUST_TARGET"
  ARTIFACT_PATTERNS=("*.exe" "*.msi")
else
  RUST_TARGET="x86_64-unknown-linux-gnu"
  BUNDLE_SUBDIR="release/bundle"
  BUNDLE_DIR_IN_CONTAINER="/build/client/src-tauri/target/$BUNDLE_SUBDIR"
  BUILD_CMD="find '$BUNDLE_DIR_IN_CONTAINER' -type f \\( -name '*.AppImage' -o -name '*.deb' \\) -delete 2>/dev/null || true; cd /build/client && npm ci && npm run tauri build"
  ARTIFACT_PATTERNS=("*.AppImage" "*.deb")
fi

BUNDLE_DIR="$SCRIPT_DIR/client/src-tauri/target/$BUNDLE_SUBDIR"

echo ""
echo "[2/3] コンテナ内でビルド中 (ターゲット: $RUST_TARGET)..."
docker run --rm \
  -v "$SCRIPT_DIR/client:/build/client" \
  "$IMAGE_NAME" \
  bash -c "$BUILD_CMD"

# ----------------------------------------------------------------
# 成果物を host/client_dist/ にコピー
# ----------------------------------------------------------------
echo ""
echo "[3/3] 成果物を $DIST_DIR にコピー中..."
mkdir -p "$DIST_DIR"

if [[ -d "$BUNDLE_DIR" ]]; then
  for pattern in "${ARTIFACT_PATTERNS[@]}"; do
    find "$DIST_DIR" -maxdepth 1 -type f -name "$pattern" -delete
    find "$BUNDLE_DIR" -type f -name "$pattern" -exec cp -v {} "$DIST_DIR/" \;
  done
  echo ""
  echo "コピー完了: $DIST_DIR"
  ls -lh "$DIST_DIR/"
else
  echo "警告: バンドルディレクトリが見つかりません: $BUNDLE_DIR" >&2
  echo "ビルドが失敗したか、出力パスが異なる可能性があります。" >&2
fi

# ----------------------------------------------------------------
# version.json の version フィールドを tauri.conf.json から自動更新
# ----------------------------------------------------------------
TAURI_VERSION=$(grep '"version"' "$SCRIPT_DIR/client/src-tauri/tauri.conf.json" \
  | head -1 | sed 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [[ -n "$TAURI_VERSION" && -f "$DIST_DIR/version.json" ]]; then
  # jq がある場合はそちらを使う、なければ sed で簡易更新
  if command -v jq &>/dev/null; then
    TMP=$(mktemp)
    jq --arg v "$TAURI_VERSION" '.version = $v' "$DIST_DIR/version.json" > "$TMP"
    mv "$TMP" "$DIST_DIR/version.json"
  else
    sed -i "s/\"version\"[[:space:]]*:[[:space:]]*\"[^\"]*\"/\"version\": \"$TAURI_VERSION\"/" \
      "$DIST_DIR/version.json"
  fi
  echo "version.json を v$TAURI_VERSION に更新しました。"
fi

echo ""
echo "====================================================="
echo "  ビルド完了!"
echo "  次のステップ:"
echo "  1. $DIST_DIR/version.json の filename/url フィールドを確認・更新する"
echo "  2. ホストサーバーを再起動して配布を有効にする"
echo "====================================================="
