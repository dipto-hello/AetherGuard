#!/bin/sh
set -e
PORT="${PORT:-8000}"
echo "==> [AetherGuard] Initializing database..."
python -c "from app.sandbox.db import init_db; init_db().close()"
echo "==> [AetherGuard] Starting Uvicorn on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
