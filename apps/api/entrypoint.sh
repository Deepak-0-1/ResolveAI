#!/bin/sh
set -e
echo "Running database migrations..."
alembic -c packages/db/alembic.ini upgrade head
echo "Starting API..."
exec uvicorn resolveai_api.main:app --host 0.0.0.0 --port 8000
