#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  service_config_apply.sh \
    --container-name <container_name> \
    --config-yaml <migrated_config_yaml_path_on_node> \
    [--service-name <service_name>] \
    [--node-volume <node_volume>] \
    [--version <service_version>] \
    [--config-path <in_container_config_path>] \
    [--artifact-id <artifact_id>] \
    [--apply-mode reload|restart]
EOF
}

status_error() {
  local message="$1"
  echo "status=error"
  echo "error=${message}"
  echo "message=${message}"
  if [[ -n "${APPLY_MODE:-}" ]]; then
    echo "apply_mode=${APPLY_MODE}"
  fi
  if [[ -n "${RESOLVED_CONFIG_PATH:-}" ]]; then
    echo "resolved_config_path=${RESOLVED_CONFIG_PATH}"
  fi
  if [[ -n "${BACKUP_PATH:-}" ]]; then
    echo "backup_path=${BACKUP_PATH}"
  fi
  if [[ -n "${ROLLED_BACK:-}" ]]; then
    echo "rolled_back=${ROLLED_BACK}"
  fi
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || status_error "missing_command:$1"
}

to_lower() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}

trim() {
  local value="$1"
  echo "$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
}

to_safe_segment() {
  local raw="$1"
  local safe
  safe="$(echo "$raw" | sed 's/[^A-Za-z0-9._-]/_/g' | sed 's/^_*//;s/_*$//')"
  if [[ -z "$safe" ]]; then
    safe="unknown"
  fi
  echo "$safe"
}

resolve_container_name() {
  local candidate="$1"
  local service_name="$2"

  if [[ -n "$candidate" ]] && docker inspect "$candidate" >/dev/null 2>&1; then
    echo "$candidate"
    return 0
  fi

  local candidate_lower
  local service_lower
  local matched=""
  local count=0
  candidate_lower="$(to_lower "$candidate")"
  service_lower="$(to_lower "$service_name")"

  while IFS= read -r name; do
    local name_lower
    name_lower="$(to_lower "$name")"
    if [[ -n "$candidate_lower" && "$name_lower" == *"$candidate_lower"* ]]; then
      matched="$name"
      count=$((count + 1))
      continue
    fi
  done < <(docker ps --format '{{.Names}}')

  if [[ $count -eq 1 ]]; then
    echo "$matched"
    return 0
  fi
  if [[ $count -gt 1 ]]; then
    status_error "container_name_ambiguous:${candidate}"
  fi

  if [[ -n "$service_lower" ]]; then
    matched=""
    count=0
    while IFS= read -r name; do
      local name_lower
      name_lower="$(to_lower "$name")"
      if [[ "$name_lower" == *"$service_lower"* ]]; then
        matched="$name"
        count=$((count + 1))
      fi
    done < <(docker ps --format '{{.Names}}')

    if [[ $count -eq 1 ]]; then
      echo "$matched"
      return 0
    fi
    if [[ $count -gt 1 ]]; then
      status_error "container_name_ambiguous:${service_name}"
    fi
  fi

  status_error "container_not_found:${candidate}"
}

is_file_in_container() {
  local container="$1"
  local path="$2"
  docker exec "$container" sh -lc "[ -f '$path' ]" >/dev/null 2>&1
}

resolve_candidates() {
  local service_name="$1"
  local service_lower="$2"
  local service_upper="$3"
  local service_title="$4"

  cat <<EOF
/app/${service_name}/config/${service_name}_config.yaml
/app/${service_name}/config/${service_lower}_config.yaml
/app/${service_name}/config/${service_name}Config.yaml
/app/${service_name}/config/${service_lower}Config.yaml
/app/${service_title}/config/${service_title}_config.yaml
/app/${service_title}/config/${service_title}Config.yaml
/${service_name}/config/${service_name}_config.yaml
/${service_name}/config/${service_lower}_config.yaml
/${service_name}/config/${service_name}Config.yaml
/${service_name}/config/${service_lower}Config.yaml
/iktara/${service_name}/config/${service_name}_config.yaml
/iktara/${service_name}/config/${service_lower}_config.yaml
/iktara/${service_name}/config/${service_name}Config.yaml
/iktara/${service_name}/config/${service_lower}Config.yaml
/iktara/${service_title}/config/${service_title}_config.yaml
/iktara/${service_title}/config/${service_title}Config.yaml
EOF

  case "$service_lower" in
    dinfer|inferenceserver|inference)
      cat <<EOF
/iktara/dInfer/dInfer/dInfer/config/dinfer_config.yaml
/iktara/dInfer/dInfer/config/dinfer_config.yaml
/iktara/dInfer/config/dinfer_config.yaml
/iktara/inference/inference_config.yaml
EOF
      ;;
    dtrain|trainingserver|training)
      cat <<EOF
/iktara/dTrain/dTrain/dTrain/config/dtrain_config.yaml
/iktara/dTrain/dTrain/config/dtrain_config.yaml
/iktara/dTrain/config/dtrain_config.yaml
/iktara/training/src/config.yaml
/iktara/Drut_Training/src/config.yaml
EOF
      ;;
    rag|rag2|rag3)
      cat <<EOF
/iktara/Rag/Rag/Rag/config/ragConfig.yaml
/iktara/Rag/Rag/config/ragConfig.yaml
/iktara/Rag/config/ragConfig.yaml
/iktara/Rag2/config/docker_config.yaml
/iktara/Rag3/config/docker_config.yaml
EOF
      ;;
    optioncopilot)
      cat <<EOF
/fintrady/optionCopilot/optionCopilot/config/optionCopilotConfig.yaml
/iktara/optionCopilot/optionCopilot/config/optionCopilotConfig.yaml
/iktara/optionCopilot/config/optionCopilotConfig.yaml
EOF
      ;;
    cplatform|aiorchestrator)
      cat <<EOF
/iktara/cPlatform/cPlatform/config/cPlatform_config.yaml
/cPlatform/config/cPlatform_config.yaml
/cPlatform/config/service_install.yaml
EOF
      ;;
    proxyans)
      cat <<EOF
/iktara/proxyAns/proxyAns/proxyAns/config/ansConfig.yaml
/iktara/proxyAns/proxyAns/config/ansConfig.yaml
EOF
      ;;
    text2sql)
      cat <<EOF
/iktara/text2sql/text2sql/text2sql/config/text2sqlConfig.yml
/iktara/text2sql/text2sql/config/text2sqlConfig.yml
EOF
      ;;
    mcpgateway)
      cat <<EOF
/iktara/mcpGateway/mcpGateway/cPlatform/Subsytems/mcpGateway/config/toolRegistry.yaml
/iktara/mcpGateway/mcpGateway/himanshunew/cPlatform/Subsytems/mcpGateway/config/toolRegistry.yaml
EOF
      ;;
    airtelchurn)
      cat <<EOF
/app/airtelChurn/config/airtelChurnConfig.yaml
/app/airtelChurn/airtelChurn/config/airtelChurnConfig.yaml
/iktara/airtelChurn/config/airtelChurnConfig.yaml
/iktara/airtelChurn/airtelChurn/config/airtelChurnConfig.yaml
EOF
      ;;
    asr)
      cat <<EOF
/iktara/Asr/Asr/config/asr_config.yaml
/iktara/Asr/config/asr_config.yaml
EOF
      ;;
    tts)
      cat <<EOF
/iktara/tts/tts/config/tts_config.yaml
/iktara/tts/config/tts_config.yaml
EOF
      ;;
    text2clk)
      cat <<EOF
/iktara/text2clk/text2clk/config/text2clkConfig.yaml
/iktara/text2clk/config/text2clkConfig.yaml
EOF
      ;;
    analyticsagent)
      cat <<EOF
/iktara/AnalyticsAgent/AnalyticsAgent/config/analyticsConfig.yaml
/iktara/AnalyticsAgent/config/analyticsConfig.yaml
EOF
      ;;
    convcall)
      cat <<EOF
/iktara/convCall/convCall/config/convCall_config.yaml
/iktara/convCall/config/convCall_config.yaml
EOF
      ;;
    convform)
      cat <<EOF
/iktara/convForm/convForm/config/formConfig.yaml
/iktara/convForm/config/formConfig.yaml
EOF
      ;;
    repository)
      cat <<EOF
/iktara/repository/Repository_config.yaml
/iktara/repository/repository/config/Repository_config.yaml
EOF
      ;;
    proxy_datajam|proxydatajam)
      cat <<EOF
/iktara/proxy_datajam/proxy_datajam/config/proxy_datajam_config.yaml
/iktara/proxy_datajam/config/proxy_datajam_config.yaml
EOF
      ;;
    mcpserver)
      cat <<EOF
/iktara/mcpServer/mcpServer/config/toolRegistry.yaml
/iktara/mcpServer/config/toolRegistry.yaml
EOF
      ;;
    airflow|infraairflowscheduler|infraairflowworker|infraairflowdagprocessor|infraairflowtriggerer)
      cat <<EOF
/opt/airflow/airflow.cfg
EOF
      ;;
    infranodeexporter)
      cat <<EOF
/etc/node-exporter/config.yml
EOF
      ;;
  esac

  cat <<EOF
/iktara/${service_name}/${service_name}/${service_name}/config/${service_name}Config.yaml
/iktara/${service_name}/${service_name}/${service_name}/config/${service_lower}Config.yaml
/iktara/${service_name}/${service_name}/${service_name}/config/${service_name}_config.yaml
/iktara/${service_name}/${service_name}/${service_name}/config/${service_lower}_config.yaml
/iktara/${service_title}/${service_title}/${service_title}/config/${service_title}_config.yaml
/iktara/${service_title}/${service_title}/${service_title}/config/${service_title}Config.yaml
/iktara/${service_name}/${service_name}/config/${service_name}Config.yaml
/iktara/${service_name}/${service_name}/config/${service_lower}Config.yaml
/iktara/${service_name}/${service_name}/config/${service_name}_config.yaml
/iktara/${service_name}/${service_name}/config/${service_lower}_config.yaml
/iktara/${service_title}/${service_title}/config/${service_title}_config.yaml
/iktara/${service_title}/${service_title}/config/${service_title}Config.yaml
/iktara/${service_name}/config/${service_name}Config.yaml
/iktara/${service_name}/config/${service_lower}Config.yaml
/iktara/${service_name}/config/${service_name}_config.yaml
/iktara/${service_name}/config/${service_lower}_config.yaml
/iktara/${service_title}/config/${service_title}_config.yaml
/iktara/${service_title}/config/${service_title}Config.yaml
/iktara/${service_upper}/${service_upper}/${service_upper}/config/${service_upper}_CONFIG.yaml
/iktara/${service_lower}/${service_lower}/config/${service_lower}Config.yaml
/iktara/${service_lower}/${service_lower}/config/${service_lower}_config.yaml
/iktara/${service_title}/${service_title}/config/${service_lower}Config.yaml
/iktara/${service_title}/${service_title}/config/${service_lower}_config.yaml
EOF
}

rollback_from_backup() {
  local reason="$1"
  if [[ -n "${BACKUP_PATH:-}" && -f "$BACKUP_PATH" ]]; then
    if sudo docker cp "$BACKUP_PATH" "${CONTAINER_NAME}:${RESOLVED_CONFIG_PATH}" >/dev/null 2>&1; then
      ROLLED_BACK="true"
    else
      ROLLED_BACK="rollback_failed"
    fi
  else
    ROLLED_BACK="backup_missing"
  fi
  status_error "$reason"
}

CONTAINER_NAME=""
SERVICE_NAME=""
NODE_VOLUME=""
VERSION=""
CONFIG_PATH=""
CONFIG_YAML_FILE=""
ARTIFACT_ID=""
APPLY_MODE="reload"
RESOLVED_CONFIG_PATH=""
BACKUP_PATH=""
ROLLED_BACK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --container-name)
      CONTAINER_NAME="${2:-}"
      shift 2
      ;;
    --service-name)
      SERVICE_NAME="${2:-}"
      shift 2
      ;;
    --node-volume)
      NODE_VOLUME="${2:-}"
      shift 2
      ;;
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --config-path)
      CONFIG_PATH="${2:-}"
      shift 2
      ;;
    --config-yaml)
      CONFIG_YAML_FILE="${2:-}"
      shift 2
      ;;
    --artifact-id)
      ARTIFACT_ID="${2:-}"
      shift 2
      ;;
    --apply-mode)
      APPLY_MODE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      status_error "unknown_argument:$1"
      ;;
  esac
done

CONTAINER_NAME="$(trim "$CONTAINER_NAME")"
SERVICE_NAME="$(trim "$SERVICE_NAME")"
NODE_VOLUME="$(trim "$NODE_VOLUME")"
VERSION="$(trim "$VERSION")"
CONFIG_PATH="$(trim "$CONFIG_PATH")"
CONFIG_YAML_FILE="$(trim "$CONFIG_YAML_FILE")"
ARTIFACT_ID="$(trim "$ARTIFACT_ID")"
APPLY_MODE="$(to_lower "$(trim "$APPLY_MODE")")"

[[ -n "$CONTAINER_NAME" ]] || status_error "container_name_required"
[[ -n "$CONFIG_YAML_FILE" ]] || status_error "config_yaml_required"
[[ -f "$CONFIG_YAML_FILE" ]] || status_error "config_yaml_not_found:${CONFIG_YAML_FILE}"
if [[ "$APPLY_MODE" != "reload" && "$APPLY_MODE" != "restart" ]]; then
  status_error "invalid_apply_mode:${APPLY_MODE}"
fi

require_cmd docker
require_cmd date
require_cmd mkdir
require_cmd find
require_cmd grep
require_cmd head

CONTAINER_NAME="$(resolve_container_name "$CONTAINER_NAME" "$SERVICE_NAME")"
RUNNING_STATE="$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || echo false)"
if [[ "$RUNNING_STATE" != "true" ]]; then
  status_error "container_not_running:$CONTAINER_NAME"
fi

IMAGE_REF="$(docker inspect -f '{{.Config.Image}}' "$CONTAINER_NAME" 2>/dev/null || true)"
if [[ -z "$SERVICE_NAME" ]]; then
  CONTAINER_RUNTIME_NAME="$(docker inspect -f '{{.Name}}' "$CONTAINER_NAME" 2>/dev/null | sed 's#^/##' || true)"
  if [[ -n "$CONTAINER_RUNTIME_NAME" && "$CONTAINER_RUNTIME_NAME" == *_* ]]; then
    SERVICE_NAME="${CONTAINER_RUNTIME_NAME%%_*}"
  fi
fi
if [[ -z "$SERVICE_NAME" && -n "$IMAGE_REF" ]]; then
  if [[ "$IMAGE_REF" == *:* ]]; then
    IMAGE_TAG="${IMAGE_REF##*:}"
    SERVICE_NAME="${IMAGE_TAG%%-*}"
  else
    IMAGE_BASENAME="${IMAGE_REF##*/}"
    SERVICE_NAME="${IMAGE_BASENAME%%-*}"
  fi
fi
[[ -n "$SERVICE_NAME" ]] || status_error "service_name_required_or_auto_resolve_failed"

if [[ -z "$VERSION" ]]; then
  if [[ "$IMAGE_REF" == *:* ]]; then
    VERSION="${IMAGE_REF##*:}"
  else
    VERSION="latest"
  fi
fi

if [[ -n "$CONFIG_PATH" ]]; then
  if is_file_in_container "$CONTAINER_NAME" "$CONFIG_PATH"; then
    RESOLVED_CONFIG_PATH="$CONFIG_PATH"
  else
    docker exec "$CONTAINER_NAME" mkdir -p "$(dirname "$CONFIG_PATH")" >/dev/null 2>&1 || true
    docker exec "$CONTAINER_NAME" touch "$CONFIG_PATH" >/dev/null 2>&1 || true
    if is_file_in_container "$CONTAINER_NAME" "$CONFIG_PATH"; then
      RESOLVED_CONFIG_PATH="$CONFIG_PATH"
    else
      status_error "config_path_not_found_in_container:${CONFIG_PATH}"
    fi
  fi
else
  SERVICE_LOWER="$(echo "$SERVICE_NAME" | tr '[:upper:]' '[:lower:]')"
  SERVICE_UPPER="$(echo "$SERVICE_NAME" | tr '[:lower:]' '[:upper:]')"
  SERVICE_TITLE="$(printf '%s' "$SERVICE_LOWER" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"

  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    if is_file_in_container "$CONTAINER_NAME" "$candidate"; then
      RESOLVED_CONFIG_PATH="$candidate"
      break
    fi
  done < <(resolve_candidates "$SERVICE_NAME" "$SERVICE_LOWER" "$SERVICE_UPPER" "$SERVICE_TITLE")
fi

if [[ -z "$RESOLVED_CONFIG_PATH" ]]; then
  FALLBACK_PATH="$(docker exec "$CONTAINER_NAME" find /iktara /fintrady /cPlatform -type f \( -iname "*config*.yaml" -o -iname "*config*.yml" \) 2>/dev/null | grep -v "test" | head -n 1 || true)"
  if [[ -n "$FALLBACK_PATH" ]]; then
    RESOLVED_CONFIG_PATH="$FALLBACK_PATH"
  else
    status_error "config_file_not_found_in_container_for_service:${SERVICE_NAME}"
  fi
fi

TS="$(date -u +%Y%m%dT%H%M%SZ)"
SERVICE_SAFE="$(to_safe_segment "$SERVICE_NAME")"
ARTIFACT_SAFE="$(to_safe_segment "${ARTIFACT_ID:-manual}")"
BACKUP_ROOT="${NODE_VOLUME%/}/config_migration_backup"
if [[ -z "$NODE_VOLUME" ]]; then
  BACKUP_ROOT="/tmp/config_migration_backup"
fi
BACKUP_PATH="${BACKUP_ROOT}/${SERVICE_SAFE}/${TS}_${ARTIFACT_SAFE}.yaml"
sudo mkdir -p "$(dirname "$BACKUP_PATH")"

if ! sudo docker cp "${CONTAINER_NAME}:${RESOLVED_CONFIG_PATH}" "$BACKUP_PATH" >/dev/null 2>&1; then
  status_error "backup_failed:${CONTAINER_NAME}:${RESOLVED_CONFIG_PATH}"
fi

TMP_CONFIG_IN_CONTAINER="/tmp/migrated_config_${TS}.yaml"
if ! sudo docker cp "$CONFIG_YAML_FILE" "${CONTAINER_NAME}:${TMP_CONFIG_IN_CONTAINER}" >/dev/null 2>&1; then
  rollback_from_backup "copy_new_config_failed"
fi

if ! sudo docker exec "$CONTAINER_NAME" sh -lc "cp '$TMP_CONFIG_IN_CONTAINER' '$RESOLVED_CONFIG_PATH' && rm -f '$TMP_CONFIG_IN_CONTAINER'" >/dev/null 2>&1; then
  rollback_from_backup "replace_config_failed"
fi

if ! sudo docker exec "$CONTAINER_NAME" sh -lc "[ -s '$RESOLVED_CONFIG_PATH' ]" >/dev/null 2>&1; then
  rollback_from_backup "empty_config_after_replace"
fi

if [[ "$APPLY_MODE" == "restart" ]]; then
  if ! sudo docker restart "$CONTAINER_NAME" >/dev/null 2>&1; then
    rollback_from_backup "restart_failed"
  fi
  APPLY_ACTION="restart"
else
  if ! sudo docker exec "$CONTAINER_NAME" sh -lc "kill -HUP 1" >/dev/null 2>&1; then
    rollback_from_backup "reload_failed"
  fi
  APPLY_ACTION="reload"
fi

echo "status=applied"
echo "container=${CONTAINER_NAME}"
echo "service=${SERVICE_NAME}"
echo "version=${VERSION}"
echo "apply_mode=${APPLY_MODE}"
echo "apply_action=${APPLY_ACTION}"
echo "resolved_config_path=${RESOLVED_CONFIG_PATH}"
echo "backup_path=${BACKUP_PATH}"
echo "artifact_id=${ARTIFACT_ID}"
echo "message=Config applied successfully"
