#!/usr/bin/env bash
# start-all.sh - Linux/Mac: Start infra via Docker Compose + launch app
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "====================================================="
echo "  BSApp - Start (Docker)"
echo "====================================================="
echo ""

# -- 1. Start infra via Docker Compose --------------------
echo "[1/3] Starting infra via Docker Compose..."

if ! command -v docker &>/dev/null; then
    echo "[ERROR] docker not found. Please install Docker."
    exit 1
fi

cd "$SCRIPT_DIR"
docker compose up -d
echo ""

# -- 2. Wait for PostgreSQL --------------------------------
echo "[2/3] Waiting for PostgreSQL..."
RETRIES=30
until docker exec bsapp-postgres pg_isready -U bsapp -d bsapp &>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [[ $RETRIES -le 0 ]]; then
        echo "[ERROR] PostgreSQL did not start."
        docker compose logs postgres
        exit 1
    fi
    sleep 1
done
echo "[OK] PostgreSQL ready"
echo ""

# -- 3. Launch application --------------------------------
echo "[3/3] Starting application..."
echo ""
echo "  Backend  : http://localhost:8080"
echo "  Frontend : http://localhost:5173"
echo ""
echo "  Press Ctrl+C to stop"
echo "  Stop infra: docker compose down"
echo "====================================================="
echo ""

# Launch backend in background
cd "$SCRIPT_DIR/host"
uv run uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload &
BACKEND_PID=$!

# Launch frontend in background
sleep 2
cd "$SCRIPT_DIR/client"
npm run dev &
FRONTEND_PID=$!

# Cleanup on Ctrl+C
cleanup() {
    echo ""
    echo "[INFO] Stopping application..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    echo "[INFO] Stopped (Docker containers still running: docker compose down)"
}
trap cleanup INT TERM

# Open browser (Linux / Mac)
sleep 3
if command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:5173" 2>/dev/null || true
elif command -v open &>/dev/null; then
    open "http://localhost:5173" 2>/dev/null || true
fi

echo "[INFO] Started"

# Wait for child processes
wait
