#!/bin/bash
set -e

echo "[PlatformOps] Starting PlatformOps initialization..."

# 1. Wait for PostgreSQL
POSTGRES_HOST="${POSTGRES_SERVER_IP:-platformops_db}"
POSTGRES_PORT="${POSTGRES_SERVER_PORT:-5432}"

echo "[PlatformOps] Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "${POSTGRES_USER:-postgres}" >/dev/null 2>&1; do
    echo "[PlatformOps] PostgreSQL is unavailable - sleeping 1s"
    sleep 1
done
echo "[PlatformOps] PostgreSQL is ready!"

# 2. Run database migrations
echo "[PlatformOps] Running database migrations..."
python manage.py migrate --noinput

# 3. Create default admin superuser if it doesn't exist
echo "[PlatformOps] Verifying superuser..."
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@platformops.io', 'admin')
    print('[PlatformOps] Created default superuser admin:admin')
else:
    print('[PlatformOps] Superuser admin already exists')
"

# 4. Collect static files
echo "[PlatformOps] Collecting static files..."
python manage.py collectstatic --noinput --clear >/dev/null 2>&1 || true

# 5. Start Gunicorn
echo "[PlatformOps] Starting Gunicorn server on 0.0.0.0:8000..."
exec gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 config.wsgi:application
