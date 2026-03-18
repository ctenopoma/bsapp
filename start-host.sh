#!/usr/bin/env bash
# start-host.sh - Start backend (FastAPI + PostgreSQL via Docker)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure Docker infra is running
cd "$SCRIPT_DIR"
docker compose up -d postgres
echo "[INFO] Waiting for PostgreSQL..."
RETRIES=15
until docker exec bsapp-postgres pg_isready -U bsapp -d bsapp &>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [[ $RETRIES -le 0 ]]; then
        echo "[ERROR] PostgreSQL did not start."
        exit 1
    fi
    sleep 1
done
echo "[OK] PostgreSQL ready"

echo "[INFO] Starting backend... (http://localhost:8080)"
cd "$SCRIPT_DIR/host"

if [[ ! -f ".env" ]]; then
    echo "[ERROR] host/.env not found. Run setup.sh first."
    exit 1
fi

uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
