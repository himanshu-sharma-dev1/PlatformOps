#!/bin/sh
set -eu

ACTION=${1:-}
RUN_ID=${2:-}
SERVICE_ID=${3:-}
CONTAINER_NAME=${4:-}
PROFILE=${5:-base}
LOG_PATH=${6:-}

case "$RUN_ID" in
  ""|*[!A-Za-z0-9_-]*) echo "run id must contain only letters, digits, underscore, or hyphen" >&2; exit 2 ;;
esac

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPOSE_FILE="$ROOT_DIR/ops/compose/docker-compose.observability.yml"
ISOLATED_FILE="$ROOT_DIR/ops/compose/docker-compose.isolated.yml"
RUNTIME_DIR="${TMPDIR:-/tmp}/platformops-observability-$RUN_ID"
ENV_FILE="$RUNTIME_DIR/runtime.env"
PROM_CONFIG="$RUNTIME_DIR/prometheus.yml"
PROJECT="platformops-observability-$RUN_ID"
EXPORTER="platformops-redis-exporter-$RUN_ID"
MARKER_CONTAINER="platformops-redis-marker-$RUN_ID"

isolated_exec() {
  docker compose -p platformops-isolated -f "$ISOLATED_FILE" --profile isolated exec -T docker-engine "$@"
}

compose() {
  runtime_profile=$PROFILE
  if [ -f "$ENV_FILE" ]; then
    runtime_profile=$(sed -n 's/^PLATFORMOPS_OBS_PROFILE=//p' "$ENV_FILE")
    runtime_profile=${runtime_profile:-$PROFILE}
  fi
  if [ "$runtime_profile" = "glitchtip" ]; then
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile glitchtip "$@"
  else
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
  fi
}

create_runtime() {
  [ -n "$SERVICE_ID" ] && [ -n "$CONTAINER_NAME" ] || {
    echo "up requires: run-id service-id container-name [base|glitchtip]" >&2
    exit 2
  }
  case "$SERVICE_ID" in *[!0-9]*|"") echo "service id must be numeric" >&2; exit 2 ;; esac
  case "$CONTAINER_NAME" in *[!A-Za-z0-9_.-]*|"") echo "invalid container name" >&2; exit 2 ;; esac
  if [ -f "$ENV_FILE" ] && [ -f "$PROM_CONFIG" ]; then
    grep -Fxq "PLATFORMOPS_OBS_SERVICE_ID=$SERVICE_ID" "$ENV_FILE" || { echo "run id already belongs to another service" >&2; exit 2; }
    grep -Fxq "PLATFORMOPS_OBS_CONTAINER_NAME=$CONTAINER_NAME" "$ENV_FILE" || { echo "run id already belongs to another container" >&2; exit 2; }
    grep -Fxq "PLATFORMOPS_OBS_PROFILE=$PROFILE" "$ENV_FILE" || { echo "run id already belongs to another profile" >&2; exit 2; }
    grep -Fxq "PLATFORMOPS_OBS_LOG_PATH=$LOG_PATH" "$ENV_FILE" || { echo "run id already belongs to another log path" >&2; exit 2; }
    return
  fi
  mkdir -p "$RUNTIME_DIR"
  chmod 700 "$RUNTIME_DIR"
  cp "$ROOT_DIR/ops/compose/observability/prometheus.yml" "$PROM_CONFIG"
  sed -i "s/__OBS_SERVICE_ID__/$SERVICE_ID/g; s/__OBS_CONTAINER_NAME__/$CONTAINER_NAME/g; s/__OBS_RUN_ID__/$RUN_ID/g" "$PROM_CONFIG"
  DB_PASSWORD=$(openssl rand -hex 24)
  ADMIN_PASSWORD=$(openssl rand -base64 36 | tr -d '\n')
  SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
  ADMIN_EMAIL="obs-$RUN_ID@example.invalid"
  umask 077
  {
    echo "PLATFORMOPS_OBS_PROJECT=$PROJECT"
    echo "PLATFORMOPS_OBS_PROM_CONFIG=$PROM_CONFIG"
    echo "PLATFORMOPS_ISOLATED_NETWORK=platformops-isolated_default"
    echo "PLATFORMOPS_OBS_DB_PASSWORD=$DB_PASSWORD"
    echo "PLATFORMOPS_OBS_ADMIN_PASSWORD=$ADMIN_PASSWORD"
    echo "PLATFORMOPS_OBS_SECRET_KEY=$SECRET_KEY"
    echo "PLATFORMOPS_OBS_ADMIN_EMAIL=$ADMIN_EMAIL"
    echo "PLATFORMOPS_OBS_SERVICE_ID=$SERVICE_ID"
    echo "PLATFORMOPS_OBS_CONTAINER_NAME=$CONTAINER_NAME"
    echo "PLATFORMOPS_OBS_PROFILE=$PROFILE"
    echo "PLATFORMOPS_OBS_LOG_PATH=$LOG_PATH"
  } > "$ENV_FILE"
}

start_marker() {
  MARKER="OBS-RUN-$RUN_ID"
  TARGET_NETWORK=$(isolated_exec docker inspect --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}' "$CONTAINER_NAME")
  [ -n "$TARGET_NETWORK" ] || { echo "Redis target has no Docker network" >&2; exit 1; }
  recreate_marker=false
  if isolated_exec docker inspect "$MARKER_CONTAINER" >/dev/null 2>&1; then
    actual_container=$(isolated_exec docker inspect --format '{{index .Config.Labels "platformops.observability.container_name"}}' "$MARKER_CONTAINER")
    actual_log_path=$(isolated_exec docker inspect --format '{{index .Config.Labels "platformops.observability.log_path"}}' "$MARKER_CONTAINER")
    [ "$actual_container" = "$CONTAINER_NAME" ] && [ "$actual_log_path" = "$LOG_PATH" ] || recreate_marker=true
  fi
  if [ "$recreate_marker" = true ]; then
    isolated_exec docker rm -f "$MARKER_CONTAINER" >/dev/null
  fi
  if ! isolated_exec docker inspect "$MARKER_CONTAINER" >/dev/null 2>&1; then
    if [ -n "$LOG_PATH" ]; then
      isolated_exec docker run -d --name "$MARKER_CONTAINER" --network "$TARGET_NETWORK" \
        --label "platformops.observability.container_name=$CONTAINER_NAME" \
        --label "platformops.observability.log_path=$LOG_PATH" \
        -e "TARGET_REDIS=$CONTAINER_NAME" -e "OBS_MARKER=$MARKER" redis:7-alpine \
        sh -c 'last_attach=""; while redis-cli -h "$TARGET_REDIS" PING | grep -q PONG; do if [ -s /tmp/alloy-reader-ready ]; then attach=$(cat /tmp/alloy-reader-ready); if [ "$attach" != "$last_attach" ]; then for seq in 0001 0002 0003; do echo "$OBS_MARKER redis=PONG attach=$attach seq=$seq"; sleep 1; done; last_attach=$attach; fi; echo "$OBS_MARKER redis=PONG attach=$attach heartbeat"; fi; sleep 2; done' >/dev/null
    else
      isolated_exec docker run -d --name "$MARKER_CONTAINER" --network "$TARGET_NETWORK" \
        --label "platformops.observability.container_name=$CONTAINER_NAME" \
        -e "TARGET_REDIS=$CONTAINER_NAME" -e "OBS_MARKER=$MARKER" redis:7-alpine \
        sh -c 'while redis-cli -h "$TARGET_REDIS" PING | grep -q PONG; do echo "$OBS_MARKER redis=PONG"; sleep 5; done' >/dev/null
    fi
  else
    running=$(isolated_exec docker inspect --format '{{.State.Running}}' "$MARKER_CONTAINER" 2>/dev/null || true)
    if [ "$running" != "true" ]; then
      isolated_exec docker start "$MARKER_CONTAINER" >/dev/null
    fi
  fi
}

release_marker() {
  ATTACH_ID=$(date +%s%N)
  isolated_exec docker exec "$MARKER_CONTAINER" sh -c 'printf %s "$1" > /tmp/alloy-reader-ready' sh "$ATTACH_ID"
  marker_attempt=0
  until [ "$(isolated_exec docker logs "$MARKER_CONTAINER" 2>/dev/null | grep -F "attach=$ATTACH_ID seq=" | wc -l | tr -d ' ')" -ge 3 ]; do
    marker_attempt=$((marker_attempt + 1))
    [ "$marker_attempt" -lt 15 ] || { echo "Redis-correlated marker burst failed" >&2; exit 1; }
    sleep 1
  done
}

wait_loki_marker() {
  [ -n "$LOG_PATH" ] || return 0
  QUERY="{filename=\"$LOG_PATH\"} |= \"$MARKER\""
  ENCODED_QUERY=$(python3 - "$QUERY" <<'PY'
import sys
from urllib.parse import quote
print(quote(sys.argv[1], safe=""))
PY
)
  loki_attempt=0
  while :; do
    payload=$(compose exec -T loki wget -qO- "http://127.0.0.1:3100/loki/api/v1/query_range?query=$ENCODED_QUERY&limit=100&direction=backward")
    if printf '%s' "$payload" | python3 -c 'import json,re,sys; p=json.load(sys.stdin); marker=sys.argv[1]; path=sys.argv[2]; token=re.compile(r"(?<![A-Za-z0-9_-])"+re.escape(marker)+r"(?![A-Za-z0-9_-])"); values=[v for s in p.get("data",{}).get("result",[]) if s.get("stream",{}).get("filename")==path for v in s.get("values",[])]; raise SystemExit(0 if sum(bool(token.search(str(v[1]))) for v in values if len(v)>=2)>=3 else 1)' "$MARKER" "$LOG_PATH"; then
      return 0
    fi
    loki_attempt=$((loki_attempt + 1))
    [ "$loki_attempt" -lt 30 ] || { echo "Loki did not expose three exact run marker lines" >&2; exit 1; }
    sleep 1
  done
}

wait_alloy_and_loki() {
  [ -f "$ENV_FILE" ] || { echo "runtime state not found: $RUNTIME_DIR" >&2; exit 2; }
  MARKER=${7:-}
  [ -n "$LOG_PATH" ] || { echo "readiness requires the canonical log path" >&2; exit 2; }
  [ -n "$MARKER" ] || { echo "readiness requires the run marker" >&2; exit 2; }
  alloy_container=$(compose ps -q alloy)
  [ -n "$alloy_container" ] || { echo "Alloy container is not present" >&2; exit 1; }
  alloy_attempt=0
  # grafana/alloy intentionally ships without wget/curl.  Probe its bound
  # loopback endpoint from a disposable, image-pinned helper in the same
  # network namespace; this is a direct endpoint check, not a Compose health
  # or API aggregate shortcut.  --rm guarantees no helper residue.
  while ! docker run --rm --network "container:$alloy_container" redis:7-alpine \
      wget -qO- http://127.0.0.1:12345/-/ready >/dev/null 2>&1; do
    alloy_attempt=$((alloy_attempt + 1))
    [ "$alloy_attempt" -lt 45 ] || { echo "Alloy readiness endpoint did not become ready" >&2; exit 1; }
    sleep 1
  done
  wait_loki_marker
  echo "alloy_ready=true loki_marker_lines=3"
}

provision_glitchtip() {
  [ "$PROFILE" = "glitchtip" ] || return 0
  # Create one run-scoped organization/project and a token with the exact
  # read/write scopes used by the typed monitoring adapter.  The token remains
  # only in the mode-700 runtime env; it is never printed or logged.
  # Reload the admin identity from the run-scoped env on re-entry.  This keeps
  # provisioning idempotent when the runtime files predate this shell process.
  ADMIN_EMAIL=${ADMIN_EMAIL:-$(sed -n 's/^PLATFORMOPS_OBS_ADMIN_EMAIL=//p' "$ENV_FILE")}
  [ -n "$ADMIN_EMAIL" ] || { echo "GlitchTip admin email was not provisioned" >&2; exit 1; }
  token=$(compose exec -T -e "PLATFORMOPS_OBS_ADMIN_EMAIL=$ADMIN_EMAIL" glitchtip python manage.py shell -c 'import os; from django.apps import apps; U=apps.get_model("users","User"); u=U.objects.get(email=os.environ["PLATFORMOPS_OBS_ADMIN_EMAIL"]); O=apps.get_model("organizations_ext","Organization"); o,_=O.objects.get_or_create(slug="acceptance", defaults={"name":"Acceptance"}); OU=apps.get_model("organizations_ext","OrganizationUser"); OU.objects.update_or_create(user=u, organization=o, defaults={"role":3}); P=apps.get_model("projects","Project"); p,_=P.objects.get_or_create(organization=o, slug="redis-core", defaults={"name":"Redis Core", "platform":"python"}); A=apps.get_model("api_tokens","APIToken"); a=A.objects.filter(user=u, label="platformops-acceptance").first() or A.objects.create(user=u, label="platformops-acceptance"); a.add_permissions(["org:read","org:write","project:read","project:write","project:admin","event:read","event:write","team:read","member:read"]); print("PLATFORMOPS_TOKEN="+a.token)' 2>/dev/null | sed -n 's/^PLATFORMOPS_TOKEN=//p' | tail -1 | tr -d '\r\n')
  case "$token" in
    ""|*[!A-Za-z0-9]*) echo "GlitchTip token provisioning returned an invalid value" >&2; exit 1 ;;
  esac
  if grep -q '^PLATFORMOPS_OBS_GLITCHTIP_TOKEN=' "$ENV_FILE"; then
    sed "s/^PLATFORMOPS_OBS_GLITCHTIP_TOKEN=.*/PLATFORMOPS_OBS_GLITCHTIP_TOKEN=$token/" "$ENV_FILE" > "$ENV_FILE.tmp"
  else
    cat "$ENV_FILE" > "$ENV_FILE.tmp"
    printf '%s\n' "PLATFORMOPS_OBS_GLITCHTIP_TOKEN=$token" >> "$ENV_FILE.tmp"
  fi
  chmod 600 "$ENV_FILE.tmp"
  mv "$ENV_FILE.tmp" "$ENV_FILE"
}

case "$ACTION" in
  up)
    create_runtime
    isolated_exec docker inspect "$CONTAINER_NAME" >/dev/null
    TARGET_NETWORK=$(isolated_exec docker inspect --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}' "$CONTAINER_NAME")
    [ -n "$TARGET_NETWORK" ] || { echo "Redis target has no Docker network" >&2; exit 1; }
    isolated_exec docker rm -f "$EXPORTER" >/dev/null 2>&1 || true
    isolated_exec docker run -d --name "$EXPORTER" --network "$TARGET_NETWORK" -p 9121:9121 \
      -e "REDIS_ADDR=redis://$CONTAINER_NAME:6379" oliver006/redis_exporter:v1.66.0 >/dev/null
    # Create the explicitly labelled source before Alloy starts.  The Docker
    # source establishes its target set at startup; readiness still polls the
    # exact filename+marker stream after the support stack is healthy.
    start_marker
    compose up -d --wait --force-recreate
    release_marker
    wait_loki_marker
    provision_glitchtip
    ;;
  marker)
    [ -n "$CONTAINER_NAME" ] || { echo "marker requires run-id service-id container-name" >&2; exit 2; }
    case "$CONTAINER_NAME" in *[!A-Za-z0-9_.-]*) echo "invalid container name" >&2; exit 2 ;; esac
    start_marker
    release_marker
    wait_loki_marker
    echo "$MARKER"
    ;;
  verify)
    [ -f "$ENV_FILE" ] || { echo "runtime state not found: $RUNTIME_DIR" >&2; exit 2; }
    compose ps --status running
    docker network inspect platformops-isolated_default >/dev/null
    if compose config | grep -Eq '/var/run/docker.sock|9002:|9008:|ipv4_address|cplatform_iktara'; then
      echo "isolation verifier rejected forbidden configuration" >&2
      exit 1
    fi
    isolated_exec wget -qO- http://127.0.0.1:9121/metrics | grep -Eq '^redis_up(\{| )'
    ;;
  query)
    [ -f "$ENV_FILE" ] || { echo "runtime state not found: $RUNTIME_DIR" >&2; exit 2; }
    QUERY=${6:-}
    [ -n "$QUERY" ] || { echo "query requires a Prometheus expression" >&2; exit 2; }
    compose exec -T prometheus wget -qO- --post-data="query=$QUERY" http://127.0.0.1:9090/api/v1/query
    ;;
  loki-query-range)
    [ -f "$ENV_FILE" ] || { echo "runtime state not found: $RUNTIME_DIR" >&2; exit 2; }
    [ -n "$LOG_PATH" ] || { echo "loki-query-range requires the canonical log path" >&2; exit 2; }
    MARKER=${7:-}
    [ -n "$MARKER" ] || { echo "loki-query-range requires the run marker" >&2; exit 2; }
    QUERY="{filename=\"$LOG_PATH\"} |= \"$MARKER\""
    ENCODED_QUERY=$(python3 - "$QUERY" <<'PY'
import sys
from urllib.parse import quote
print(quote(sys.argv[1], safe=""))
PY
)
    # Match the API's bounded 720-hour history window while allowing a small
    # future guard for Docker timestamp skew between the isolated engines.
    END_NS=$(date +%s%N)
    QUERY_END_NS=$((END_NS + 300000000000))
    START_NS=$((END_NS - 2592000000000000))
    compose exec -T loki wget -qO- "http://127.0.0.1:3100/loki/api/v1/query_range?query=$ENCODED_QUERY&start=$START_NS&end=$QUERY_END_NS&limit=1000&direction=backward"
    ;;
  ready)
    wait_alloy_and_loki "$@"
    ;;
  down)
    [ -f "$ENV_FILE" ] || exit 0
    compose down -v --remove-orphans
    isolated_exec docker rm -f "$EXPORTER" >/dev/null 2>&1 || true
    isolated_exec docker rm -f "$MARKER_CONTAINER" >/dev/null 2>&1 || true
    rm -f "$PROM_CONFIG" "$ENV_FILE"
    rmdir "$RUNTIME_DIR" 2>/dev/null || true
    ;;
  *)
    echo "usage: $0 {up|marker|verify|query|loki-query-range|ready|down} RUN_ID [SERVICE_ID CONTAINER_NAME [base|glitchtip]] [query]" >&2
    exit 2
    ;;
esac
