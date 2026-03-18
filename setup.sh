#!/usr/bin/env bash
# setup.sh - Initial setup (Docker infra + DB creation + dependency install)
#
# Requirements:
#   - Docker + Docker Compose
#   - Python 3.13+ with uv
#   - Node.js 18+
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "====================================================="
echo "  BSApp Web - Initial Setup (Docker)"
echo "====================================================="
echo ""

# -- 1. Start PostgreSQL via Docker -----------------------
echo "[1/4] Starting PostgreSQL via Docker Compose..."

if ! command -v docker &>/dev/null; then
    echo "[ERROR] docker not found. Please install Docker."
    exit 1
fi

cd "$SCRIPT_DIR"
docker compose up -d postgres
echo ""

# Wait for PostgreSQL to be ready
echo "  Waiting for PostgreSQL..."
RETRIES=30
until docker exec bsapp-postgres pg_isready -U bsapp -d bsapp &>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [[ $RETRIES -le 0 ]]; then
        echo "[ERROR] PostgreSQL did not start."
        exit 1
    fi
    sleep 1
done
echo "  [OK] PostgreSQL ready"
echo ""

# -- 2. Create backend .env ------------------------------
echo "[2/4] Creating config files..."
if [[ ! -f "$SCRIPT_DIR/host/.env" ]]; then
    cp "$SCRIPT_DIR/host/.env.example" "$SCRIPT_DIR/host/.env"
    echo "  Created host/.env"
else
    echo "  host/.env already exists (skipped)"
fi

if [[ ! -f "$SCRIPT_DIR/client/.env.local" ]]; then
    cp "$SCRIPT_DIR/client/.env.example" "$SCRIPT_DIR/client/.env.local"
    echo "  Created client/.env.local"
else
    echo "  client/.env.local already exists (skipped)"
fi
echo ""

# -- 3. Install backend dependencies ---------------------
echo "[3/4] Installing backend packages..."
cd "$SCRIPT_DIR/host"
uv sync
echo ""

# -- 4. Install frontend dependencies --------------------
echo "[4/4] Installing frontend packages..."
cd "$SCRIPT_DIR/client"
npm install
echo ""

echo "====================================================="
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "    ./start-host.sh   ... Start backend"
echo "    ./start-web.sh    ... Start frontend"
echo "    ./start-all.sh    ... Start both"
echo "====================================================="
