#!/usr/bin/env bash
# start-web.sh - Start frontend (Vite dev server)
# Open http://localhost:5173 in your browser
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[INFO] Starting frontend... (http://localhost:5173)"
cd "$SCRIPT_DIR/client"

if [[ ! -f ".env.local" ]]; then
    echo "[ERROR] client/.env.local not found. Run setup.sh first."
    exit 1
fi

npm run dev
