#!/bin/sh
set -eu

# Provision/tear down only the named platformops-isolated acceptance stack.
# The overlay uses unique volumes so the existing isolated DinD state (and its
# unknown historical containers) is never inspected, deleted, or reused.
ACTION=${1:-}
RUN_ID=${2:-}
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BASE_FILE="$ROOT_DIR/ops/compose/docker-compose.isolated.yml"
OVERLAY_FILE="$ROOT_DIR/ops/compose/docker-compose.acceptance.yml"
RUNTIME_ROOT="${TMPDIR:-/tmp}/platformops-redis-acceptance-runtime"
RUNTIME_DIR="$RUNTIME_ROOT/$RUN_ID"
ENV_FILE="$RUNTIME_DIR/compose.env"
IMAGE=${3:-platformops:acceptance-$RUN_ID}

case "$RUN_ID" in
  ""|*[!A-Za-z0-9_-]*) echo "run id must contain only letters, digits, underscore, or hyphen" >&2; exit 2 ;;
esac

compose() {
  docker compose --project-name platformops-isolated --env-file "$ENV_FILE" \
    --file "$BASE_FILE" --file "$OVERLAY_FILE" --profile isolated --profile mailpit "$@"
}

ensure_ssh_fixture_key() {
  key_path="$RUNTIME_DIR/ssh_fixture_key"
  if [ ! -s "$key_path" ] || [ ! -s "$key_path.pub" ]; then
    mkdir -p "$RUNTIME_DIR"
    chmod 700 "$RUNTIME_DIR"
    umask 077
    ssh-keygen -q -t ed25519 -N '' -C "platformops-acceptance-$RUN_ID" -f "$key_path"
  fi
  chmod 600 "$key_path"
  chmod 644 "$key_path.pub"
}

write_env() {
  ensure_ssh_fixture_key
  mkdir -p "$RUNTIME_DIR"
  chmod 700 "$RUNTIME_DIR"
  umask 077
  cat > "$ENV_FILE" <<EOF
PLATFORMOPS_ACCEPTANCE_IMAGE=$IMAGE
PLATFORMOPS_ACCEPTANCE_POSTGRES_VOLUME=platformops-acceptance-postgres-$RUN_ID
PLATFORMOPS_ACCEPTANCE_REDIS_VOLUME=platformops-acceptance-redis-$RUN_ID
PLATFORMOPS_ACCEPTANCE_RABBITMQ_VOLUME=platformops-acceptance-rabbitmq-$RUN_ID
PLATFORMOPS_ACCEPTANCE_PROMETHEUS_VOLUME=platformops-acceptance-prometheus-$RUN_ID
PLATFORMOPS_ACCEPTANCE_LOKI_VOLUME=platformops-acceptance-loki-$RUN_ID
PLATFORMOPS_ACCEPTANCE_DOCKER_VOLUME=platformops-acceptance-docker-$RUN_ID
PLATFORMOPS_ACCEPTANCE_PLATFORMOPS_VOLUME=platformops-acceptance-api-$RUN_ID
PLATFORMOPS_ACCEPTANCE_REMOTE_VOLUME=platformops-acceptance-remote-$RUN_ID
PLATFORMOPS_ACCEPTANCE_IMAGE_TAG=$RUN_ID
PLATFORMOPS_SSH_PUBLIC_KEY_PATH=$RUNTIME_DIR/ssh_fixture_key.pub
PLATFORMOPS_GLITCHTIP_ORG_SLUG=acceptance
PLATFORMOPS_GLITCHTIP_PROJECT_MAP={"redis-core":"redis-core"}
EOF
}

up() {
  write_env
  # Stop only the known isolated Compose project.  This does not remove its
  # containers or volumes, preserving the previous DinD state verbatim.
  docker compose --project-name platformops-isolated --file "$BASE_FILE" \
    --profile isolated --profile mailpit stop >/dev/null 2>&1 || true
  if [ "${PLATFORMOPS_ACCEPTANCE_SKIP_BUILD:-0}" != "1" ]; then
    docker build --label "platformops.acceptance.run=$RUN_ID" -t "$IMAGE" \
      -f "$ROOT_DIR/ops/docker/web-api/Dockerfile" "$ROOT_DIR" >/dev/null
  fi
  compose up -d --wait --force-recreate
  container=$(docker compose --project-name platformops-isolated --env-file "$ENV_FILE" \
    --file "$BASE_FILE" --file "$OVERLAY_FILE" --profile isolated --profile mailpit ps -q platformops)
  [ -n "$container" ] || { echo "acceptance API container was not created" >&2; exit 1; }
  label=$(docker inspect --format '{{index .Config.Labels "platformops.acceptance.run"}}' "$container")
  [ "$label" = "$RUN_ID" ] || { echo "acceptance image label mismatch" >&2; exit 1; }
  echo "run_id=$RUN_ID"
  echo "image=$IMAGE"
  echo "env_file=$ENV_FILE"
}

down() {
  [ -f "$ENV_FILE" ] || exit 0
  # The shared private network may retain explicitly preserved helper
  # containers; reconcile the run-scoped containers/volumes even if Compose
  # cannot remove that network itself.
  compose down --remove-orphans >/dev/null 2>&1 || true
  # Compose cannot reliably remove explicitly named volumes with -v.  Remove
  # only the exact seven names generated above, after the stack is stopped.
  for suffix in postgres redis rabbitmq prometheus loki docker api remote; do
    volume="platformops-acceptance-$suffix-$RUN_ID"
    case "$volume" in platformops-acceptance-*-$RUN_ID) docker volume rm "$volume" >/dev/null 2>&1 || true ;; esac
  done
  rm -f "$ENV_FILE"
  rm -f "$RUNTIME_DIR/ssh_fixture_key" "$RUNTIME_DIR/ssh_fixture_key.pub"
  rmdir "$RUNTIME_DIR" 2>/dev/null || true
  rmdir "$RUNTIME_ROOT" 2>/dev/null || true
}

restore() {
  docker compose --project-name platformops-isolated --file "$BASE_FILE" \
    --profile isolated --profile mailpit up -d --wait
}

refresh() {
  [ -f "$ENV_FILE" ] || { echo "acceptance runtime env not found: $ENV_FILE" >&2; exit 2; }
  support_env="${TMPDIR:-/tmp}/platformops-observability-$RUN_ID/runtime.env"
  [ -f "$support_env" ] || { echo "observability runtime env not found" >&2; exit 2; }
  token=$(sed -n 's/^PLATFORMOPS_OBS_GLITCHTIP_TOKEN=//p' "$support_env")
  case "$token" in ""|*[!A-Za-z0-9]*) echo "observability token was not provisioned" >&2; exit 1 ;; esac
  # Monitoring's typed service request uses the canonical ServiceInstance
  # name, while the disposable GlitchTip project is keyed by redis-core.
  # Add that exact run-scoped name only after phase 2 has created it; keeping
  # this mapping in the acceptance env avoids changing production defaults.
  service_name=${3:-}
  project_map='{"redis-core":"redis-core"}'
  if [ -n "$service_name" ]; then
    project_map=$(python3 - "$service_name" <<'PY'
import json
import sys
name = sys.argv[1]
print(json.dumps({"redis-core": "redis-core", name: "redis-core"}, separators=(",", ":")))
PY
    )
  fi
  grep -v -E '^(PLATFORMOPS_GLITCHTIP_TOKEN|PLATFORMOPS_GLITCHTIP_PROJECT_MAP)=' "$ENV_FILE" > "$ENV_FILE.tmp"
  printf '%s\n' "PLATFORMOPS_GLITCHTIP_TOKEN=$token" >> "$ENV_FILE.tmp"
  printf '%s\n' "PLATFORMOPS_GLITCHTIP_PROJECT_MAP=$project_map" >> "$ENV_FILE.tmp"
  chmod 600 "$ENV_FILE.tmp"
  mv "$ENV_FILE.tmp" "$ENV_FILE"
  compose up -d --wait --force-recreate platformops >/dev/null
}

case "$ACTION" in
  up) up ;;
  down) down ;;
  refresh) refresh "$@" ;;
  restore) restore ;;
  *) echo "usage: $0 {up|down|refresh|restore} RUN_ID [image]" >&2; exit 2 ;;
esac
