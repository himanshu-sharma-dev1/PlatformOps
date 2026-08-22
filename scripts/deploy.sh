#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/root/PlatformOps}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-master}"
CONTAINER_NAME="${CONTAINER_NAME:-platformops_web}"
LOCK_FILE="${LOCK_FILE:-/tmp/cplatform-deploy.lock}"
STATE_DIR="${STATE_DIR:-/tmp/cplatform-deploy-state}"
DESIRED_REF_FILE="${DESIRED_REF_FILE:-${STATE_DIR}/desired_ref}"
DESIRED_BRANCH_FILE="${DESIRED_BRANCH_FILE:-${STATE_DIR}/desired_branch}"
DRY_RUN="${DRY_RUN:-0}"
AUTO_STASH="${AUTO_STASH:-1}"
STASH_EXCLUDE_1="${STASH_EXCLUDE_1:-:(exclude)PlatformOps/Models}"
STASH_EXCLUDE_2="${STASH_EXCLUDE_2:-:(exclude)PlatformOps/Models/**}"
STASH_EXCLUDE_3="${STASH_EXCLUDE_3:-:(exclude)PlatformOps/config/PlatformOps_config.yaml}"
STASH_EXCLUDE_4="${STASH_EXCLUDE_4:-:(exclude)PlatformOps/logs}"
STASH_EXCLUDE_5="${STASH_EXCLUDE_5:-:(exclude)PlatformOps/logs/**}"
APP_BASE_URL="${APP_BASE_URL:-http://127.0.0.1}"
WAIT_INTERVAL_SECONDS="${WAIT_INTERVAL_SECONDS:-2}"
WAIT_MAX_SECONDS="${WAIT_MAX_SECONDS:-900}"
DEPLOY_DEBOUNCE_SECONDS="${DEPLOY_DEBOUNCE_SECONDS:-60}"
PRESERVE_CONFIG_PATH="${PRESERVE_CONFIG_PATH:-PlatformOps/config/PlatformOps_config.yaml}"

PRESERVED_FILES=(
  "${PRESERVE_CONFIG_PATH}"
)

log() {
  printf '[%s] %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*"
}

run_git() {
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    local auth_header
    auth_header="$(printf 'x-access-token:%s' "${GITHUB_TOKEN}" | base64 -w0)"
    git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${auth_header}" "$@"
  else
    git "$@"
  fi
}

container_exec() {
  docker exec "${CONTAINER_NAME}" sh -lc "$1"
}

record_desired_ref() {
  local desired_ref="$1"
  mkdir -p "${STATE_DIR}"
  printf '%s\n' "${DEPLOY_BRANCH}" > "${DESIRED_BRANCH_FILE}"
  printf '%s\n' "${desired_ref}" > "${DESIRED_REF_FILE}"
}

read_desired_ref() {
  if [[ -f "${DESIRED_REF_FILE}" ]]; then
    tr -d '\n' < "${DESIRED_REF_FILE}"
  fi
}

backup_preserved_files() {
  PRESERVE_BACKUP_DIR="$(mktemp -d)"
  local rel_path
  for rel_path in "${PRESERVED_FILES[@]}"; do
    [[ -n "${rel_path}" ]] || continue
    if [[ -e "${rel_path}" ]]; then
      mkdir -p "${PRESERVE_BACKUP_DIR}/$(dirname "${rel_path}")"
      cp -a "${rel_path}" "${PRESERVE_BACKUP_DIR}/${rel_path}"
    fi
  done
}

clean_preserved_paths_for_git() {
  local rel_path
  for rel_path in "${PRESERVED_FILES[@]}"; do
    [[ -n "${rel_path}" ]] || continue
    if run_git ls-files --error-unmatch "${rel_path}" >/dev/null 2>&1; then
      run_git restore --source=HEAD --staged --worktree -- "${rel_path}" >/dev/null 2>&1 || true
    fi
  done
}

restore_preserved_files() {
  [[ -n "${PRESERVE_BACKUP_DIR:-}" && -d "${PRESERVE_BACKUP_DIR}" ]] || return 0

  local rel_path
  for rel_path in "${PRESERVED_FILES[@]}"; do
    [[ -n "${rel_path}" ]] || continue
    if [[ -e "${PRESERVE_BACKUP_DIR}/${rel_path}" ]]; then
      mkdir -p "$(dirname "${rel_path}")"
      cp -a "${PRESERVE_BACKUP_DIR}/${rel_path}" "${rel_path}"
    fi
  done

  rm -rf "${PRESERVE_BACKUP_DIR}"
  PRESERVE_BACKUP_DIR=""
}

list_stashable_paths() {
  run_git ls-files -m -o --exclude-standard -- . \
    "${STASH_EXCLUDE_1}" "${STASH_EXCLUDE_2}" "${STASH_EXCLUDE_3}" \
    "${STASH_EXCLUDE_4}" "${STASH_EXCLUDE_5}"
  run_git diff --name-only --cached -- . \
    "${STASH_EXCLUDE_1}" "${STASH_EXCLUDE_2}" "${STASH_EXCLUDE_3}" \
    "${STASH_EXCLUDE_4}" "${STASH_EXCLUDE_5}"
}

stash_non_runtime_changes() {
  local stash_label="$1"
  local stash_paths=()

  if [[ "${AUTO_STASH}" != "1" ]]; then
    log "Working tree is dirty. Refusing auto deploy (AUTO_STASH=0)."
    exit 2
  fi

  mapfile -t stash_paths < <(list_stashable_paths | sort -u)

  if [[ "${#stash_paths[@]}" -eq 0 ]]; then
    log "Working tree only contains preserved runtime paths. Skipping stash."
    return 0
  fi

  log "Working tree is dirty. Stashing local changes as: ${stash_label}"
  run_git stash push -u -m "${stash_label}" -- "${stash_paths[@]}" >/dev/null
}

has_stashable_changes() {
  [[ -n "$(list_stashable_paths | sort -u)" ]]
}

checkout_deploy_target() {
  local current_branch stash_label

  current_branch="$(run_git rev-parse --abbrev-ref HEAD)"
  if [[ "${current_branch}" == "${DEPLOY_BRANCH}" ]]; then
    return 0
  fi

  log "Checking out branch ${DEPLOY_BRANCH} (current: ${current_branch})"
  backup_preserved_files
  clean_preserved_paths_for_git

  if has_stashable_changes; then
    stash_label="auto-deploy-preserve-$(date -u +%Y%m%dT%H%M%SZ)"
    stash_non_runtime_changes "${stash_label}"
  fi

  if ! run_git checkout "${DEPLOY_BRANCH}"; then
    log "Branch checkout failed. Falling back to detached origin/${DEPLOY_BRANCH} checkout."
    run_git checkout --detach "origin/${DEPLOY_BRANCH}"
  fi

  restore_preserved_files
}

wait_for_quiet_window() {
  if [[ "${DEPLOY_DEBOUNCE_SECONDS}" -le 0 ]]; then
    return 0
  fi

  local observed_ref latest_ref
  while true; do
    observed_ref="$(read_desired_ref)"
    [[ -n "${observed_ref}" ]] || observed_ref="$(run_git rev-parse "origin/${DEPLOY_BRANCH}")"
    log "Debouncing deploy for ${DEPLOY_DEBOUNCE_SECONDS}s at ${observed_ref}"
    sleep "${DEPLOY_DEBOUNCE_SECONDS}"
    run_git fetch origin "${DEPLOY_BRANCH}" --prune >/dev/null 2>&1
    latest_ref="$(run_git rev-parse "origin/${DEPLOY_BRANCH}")"
    record_desired_ref "${latest_ref}"
    if [[ "${observed_ref}" == "${latest_ref}" ]]; then
      return 0
    fi
    log "Newer commit detected during debounce. Updating target to ${latest_ref}"
  done
}

wait_for_http_path() {
  local path="$1"
  local url="${APP_BASE_URL}${path}"
  local attempt=1
  local max_attempts

  max_attempts=$((WAIT_MAX_SECONDS / WAIT_INTERVAL_SECONDS))
  if [[ "${max_attempts}" -lt 1 ]]; then
    max_attempts=1
  fi

  while [[ "${attempt}" -le "${max_attempts}" ]]; do
    if curl -fsS --connect-timeout 2 --max-time 5 "${url}" >/dev/null 2>&1; then
      log "Verified ${url}"
      return 0
    fi

    if (( attempt % 15 == 0 )); then
      log "Waiting for ${url} (${attempt}/${max_attempts})"
    fi
    sleep "${WAIT_INTERVAL_SECONDS}"
    attempt=$((attempt + 1))
  done

  log "HTTP check failed for ${url} after ${WAIT_MAX_SECONDS}s"
  return 1
}

collectstatic_if_needed() {
  log "Running collectstatic in ${CONTAINER_NAME}"
  container_exec "cd /app && python manage.py collectstatic --noinput >/tmp/collectstatic.log 2>&1"
}

reload_gunicorn() {
  log "Reloading Gunicorn"
  container_exec '
    set -eu
    cd /app

    gunicorn_master_pid="$(
      ps -eo pid=,ppid=,args= | awk '"'"'
        $3 == "/usr/local/bin/python" &&
        $4 == "/usr/local/bin/gunicorn" &&
        $0 ~ /PlatformOps\.wsgi:application/ {
          print $1
          exit
        }
      '"'"'
    )"

    if [ -n "${gunicorn_master_pid}" ]; then
      kill -HUP "${gunicorn_master_pid}"
      exit 0
    fi

    echo "Gunicorn master process not found; starting a fresh Gunicorn instance" >&2
    nohup /usr/local/bin/gunicorn PlatformOps.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers 2 \
      --threads 4 \
      --timeout 3600 \
      >/tmp/cplatform-gunicorn.log 2>&1 &
  '
}

reload_nginx() {
  log "Reloading Nginx"
  container_exec '
    if [ -f /run/nginx.pid ]; then
      nginx -s reload
    fi
  '
}

restart_celery() {
  log "Restarting Celery beat and worker"
  container_exec '
    set -eu
    cd /app

    beat_pids="$(
      ps -eo pid=,args= | awk '"'"'
        $0 ~ /^ *[0-9]+ +\/usr\/local\/bin\/python \/usr\/local\/bin\/celery -A PlatformOps beat -l INFO --scheduler django_celery_beat\.schedulers:DatabaseScheduler$/ {
          print $1
        }
      '"'"'
    )"
    worker_pids="$(
      ps -eo pid=,args= | awk '"'"'
        $0 ~ /^ *[0-9]+ +\/usr\/local\/bin\/python \/usr\/local\/bin\/celery -A PlatformOps worker --purge --loglevel=info --pool=solo -Q PlatformOps_dataflow$/ {
          print $1
        }
      '"'"'
    )"

    if [ -n "${beat_pids}" ]; then
      kill ${beat_pids} || true
    fi
    if [ -n "${worker_pids}" ]; then
      kill ${worker_pids} || true
    fi

    sleep 2

    nohup celery -A PlatformOps beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler >/tmp/cplatform-celery-beat.log 2>&1 &
    nohup celery -A PlatformOps worker --purge --loglevel=info --pool=solo -Q PlatformOps_dataflow >/tmp/cplatform-celery-worker.log 2>&1 &
  '
}

apply_runtime_updates() {
  local before_commit="$1"
  local after_commit="$2"
  local changed_files
  local needs_collectstatic=0
  local needs_gunicorn_reload=0
  local needs_celery_restart=0
  local needs_nginx_reload=0
  local rebuild_required=0

  changed_files="$(run_git diff --name-only "${before_commit}" "${after_commit}")"
  if [[ -z "${changed_files}" ]]; then
    log "No file changes between ${before_commit} and ${after_commit}. Skipping runtime reload."
    return 0
  fi

  while IFS= read -r changed_file; do
    [[ -n "${changed_file}" ]] || continue
    case "${changed_file}" in
      PlatformOps/static/*|PlatformOps/templates/*|PlatformOps/templates_new/*)
        needs_collectstatic=1
        needs_gunicorn_reload=1
        ;;
      PlatformOps/PlatformOpsIO/*|PlatformOps/Proxy/*|PlatformOps/PlatformOps/*|PlatformOps/manage.py)
        needs_gunicorn_reload=1
        needs_celery_restart=1
        ;;
      platform/nginx/nginx.conf|PlatformOps/docker-compose.yaml)
        needs_nginx_reload=1
        ;;
      PlatformOps/entrypoint_script.sh|PlatformOps/Dockerfile|PlatformOps/requirements*.txt|PlatformOps/requirements-cplatform.txt|PlatformOps/CommonUtils-*.whl)
        rebuild_required=1
        ;;
    esac
  done <<< "${changed_files}"

  if [[ "${needs_collectstatic}" == "1" ]]; then
    collectstatic_if_needed
  fi

  if [[ "${needs_celery_restart}" == "1" ]]; then
    restart_celery
  fi

  if [[ "${needs_gunicorn_reload}" == "1" ]]; then
    reload_gunicorn
  fi

  if [[ "${needs_nginx_reload}" == "1" ]]; then
    reload_nginx
  fi

  if [[ "${rebuild_required}" == "1" ]]; then
    log "Detected image or dependency changes. Mounted-code reload applied, but a rebuild is still required for full effect."
  fi
}

exec 9>"${LOCK_FILE}"

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  log "Repository not found at ${REPO_DIR}"
  exit 1
fi

cd "${REPO_DIR}"

run_git fetch origin "${DEPLOY_BRANCH}" --prune
record_desired_ref "$(run_git rev-parse "origin/${DEPLOY_BRANCH}")"

if ! flock -n 9; then
  log "Another deployment is already running. Requested $(read_desired_ref); active deploy will converge to the latest commit."
  exit 0
fi

checkout_deploy_target

if ! docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  log "Container ${CONTAINER_NAME} not found."
  exit 3
fi

while true; do
  desired_ref="$(read_desired_ref)"
  if [[ -z "${desired_ref}" ]]; then
    desired_ref="$(run_git rev-parse "origin/${DEPLOY_BRANCH}")"
    record_desired_ref "${desired_ref}"
  fi

  wait_for_quiet_window
  desired_ref="$(read_desired_ref)"
  before_commit="$(run_git rev-parse HEAD)"

  backup_preserved_files
  clean_preserved_paths_for_git

  if has_stashable_changes; then
    stash_label="auto-deploy-preserve-$(date -u +%Y%m%dT%H%M%SZ)"
    stash_non_runtime_changes "${stash_label}"
  fi

  log "Fetching latest commits for ${DEPLOY_BRANCH}"
  run_git fetch origin "${DEPLOY_BRANCH}" --prune
  desired_ref="$(read_desired_ref)"
  if [[ -z "${desired_ref}" ]]; then
    desired_ref="$(run_git rev-parse "origin/${DEPLOY_BRANCH}")"
    record_desired_ref "${desired_ref}"
  fi

  log "Deploying ${desired_ref}"
  run_git merge --ff-only "${desired_ref}"
  after_commit="$(run_git rev-parse HEAD)"

  restore_preserved_files

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY_RUN=1 set. Skipping runtime reload."
    log "Deploy check done. Commit: ${before_commit} -> ${after_commit}"
  else
    apply_runtime_updates "${before_commit}" "${after_commit}"
    wait_for_http_path "/"
    wait_for_http_path "/static/css/ds.css"
    wait_for_http_path "/static/javascript/theme.js"
    wait_for_http_path "/static/css/cluster.css"
    log "Deployment successful. Commit: ${before_commit} -> ${after_commit}"
  fi

  latest_remote_ref="$(run_git rev-parse "origin/${DEPLOY_BRANCH}")"
  latest_desired_ref="$(read_desired_ref)"
  if [[ "${after_commit}" == "${latest_remote_ref}" && "${after_commit}" == "${latest_desired_ref}" ]]; then
    break
  fi

  log "A newer target is pending. Continuing deploy loop."
  record_desired_ref "${latest_remote_ref}"
done
