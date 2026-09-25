#!/bin/sh
set -e
cd /app
mkdir -p /app/data
alembic upgrade head
if [ "${SEED_ON_START:-false}" = "true" ]; then
  python scripts/seed.py || true
fi
exec "$@"
