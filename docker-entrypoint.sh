#!/bin/sh
set -e

# MediaPipe needs GLES libs; install once if missing (avoids full image rebuild).
if ! ldconfig -p 2>/dev/null | grep -q libGLESv2; then
  echo "Installing MediaPipe system libraries..."
  apt-get update -qq
  apt-get install -y --no-install-recommends libegl1 libgles2 libxrender1
  rm -rf /var/lib/apt/lists/*
fi

# HF / cloud: host comes from DATABASE_URL. Compose: defaults to service name "db".
if [ -z "${DB_HOST:-}" ] && [ -n "${DATABASE_URL:-}" ]; then
  read -r DB_HOST DB_PORT <<EOF
$(python3 -c "
from urllib.parse import urlparse
import os
parsed = urlparse(os.environ['DATABASE_URL'].replace('postgresql+asyncpg', 'postgresql', 1))
print(parsed.hostname or 'db', parsed.port or 5432)
")
EOF
fi
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
until python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
s.connect(('${DB_HOST}', ${DB_PORT}))
s.close()
" 2>/dev/null; do
  echo "  Database not reachable yet, retrying in 2s..."
  sleep 2
done

echo "PostgreSQL is up — running migrations..."
alembic upgrade head

echo "Starting API on port ${PORT:-7860}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}"
