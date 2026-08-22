#!/bin/bash
####################################################################################################################################
echo "starting server"
#############################################"#######################################################################################
REPO_DIR="../MCPClient"
GIT_TOKEN="${GITHUB_TOKEN:-}"



# Clone if missing
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "?? Cloning repo..."
    git clone https://$GIT_TOKEN@github.com/iktara-ai/MCPClient.git "$REPO_DIR"
else
    echo "???? Repo already exists, skipping clone."
fi

bash CutilPackages/cutil_pkg.sh
sleep 5
pip install CommonUtils-1.0.22-py3-none-any.whl
sleep 10
python manage.py cplatform_createdb || true
sleep 10
python manage.py clickhouse_query
python manage.py makemigrations
python manage.py makemigrations cPlatformIO
python manage.py makemigrations proxymentis
python manage.py migrate
python manage.py template_preconfig Churn
python manage.py collectstatic --noinput
DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_PASSWORD=admin python manage.py createsuperuser --email=admin@admin.com --noinput
python manage.py cplatform_preconfig

shutdown_children() {
    local pid
    for pid in \
        "${beat_pid:-}" \
        "${worker_pid:-}" \
        "${gunicorn_pid:-}" \
        "${nginx_pid:-}"; do
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
}

reap_children() {
    while wait -n 2>/dev/null; do
        :
    done
}

trap 'shutdown_children; exit 0' TERM INT
trap 'reap_children' CHLD

celery -A cPlatform beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler &
beat_pid=$!

celery -A cPlatform worker --purge --loglevel=info --pool=solo -Q cPlatform_dataflow &
worker_pid=$!

gunicorn cPlatform.wsgi:application --bind 0.0.0.0:8001 --workers 2 --threads 4 --timeout 3600 &
gunicorn_pid=$!

nginx -g 'daemon off;' &
nginx_pid=$!

startup_grace_seconds=20
startup_deadline=$(( $(date +%s) + startup_grace_seconds ))

while true; do
    now=$(date +%s)
    if ! kill -0 "${gunicorn_pid}" 2>/dev/null; then
        if [ "${now}" -lt "${startup_deadline}" ]; then
            sleep 2
            continue
        fi
        echo "gunicorn pid ${gunicorn_pid} is not running; stopping container"
        shutdown_children
        exit 1
    fi

    if ! kill -0 "${nginx_pid}" 2>/dev/null; then
        if [ "${now}" -lt "${startup_deadline}" ]; then
            sleep 2
            continue
        fi
        echo "nginx pid ${nginx_pid} is not running; stopping container"
        tail -n 50 /var/log/nginx/error.log 2>/dev/null || true
        shutdown_children
        exit 1
    fi

    if ! kill -0 "${beat_pid}" 2>/dev/null; then
        echo "[WARNING] Celery beat process exited; restarting beat..."
        rm -f celerybeat-schedule* celerybeat.pid
        celery -A cPlatform beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler &
        beat_pid=$!
    fi

    if ! kill -0 "${worker_pid}" 2>/dev/null; then
        echo "[WARNING] Celery worker process exited; restarting worker..."
        celery -A cPlatform worker --purge --loglevel=info --pool=solo -Q cPlatform_dataflow &
        worker_pid=$!
    fi

    sleep 5
done
