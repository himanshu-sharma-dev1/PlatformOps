#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_service_config_snapshot.sh \
    --node-id <NODE_ID> \
    --container-name <container_id_or_name> \
    [--service-name <service_name>] \
    [--node-volume <remote_node_volume>] \
    [--config-path <in_container_config_path>] \
    [--cplatform-container <cplatform_container_name>] \
    [--publish-root <host_publish_root>]

Default behavior:
  - Copies snapshot script + playbook into PlatformOps container.
  - Runs playbook against dynamicInventory<NODE_ID>.yaml.
  - Fetches snapshot from remote node into:
      /home/ubuntu/Backup_Platform/app/logs/config_snapshots
  - Auto-syncs fetched snapshot tree into:
      /home/ubuntu/Backup_Platform/config
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

NODE_ID=""
TARGET_CONTAINER=""
SERVICE_NAME=""
NODE_VOLUME="/home/ubuntu/Backup_Platform"
CONFIG_PATH=""
CPLATFORM_CONTAINER="platformops_web"
PUBLISH_ROOT="/home/ubuntu/Backup_Platform/config"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --node-id)
      NODE_ID="${2:-}"
      shift 2
      ;;
    --container-name)
      TARGET_CONTAINER="${2:-}"
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
    --config-path)
      CONFIG_PATH="${2:-}"
      shift 2
      ;;
    --cplatform-container)
      CPLATFORM_CONTAINER="${2:-}"
      shift 2
      ;;
    --publish-root)
      PUBLISH_ROOT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      die "unknown argument: $1"
      ;;
  esac
done

[[ -n "$NODE_ID" ]] || die "--node-id is required"
[[ -n "$TARGET_CONTAINER" ]] || die "--container-name is required"

require_cmd docker
require_cmd rsync
require_cmd find
require_cmd mkdir

SCRIPT_SRC_HOST="/home/ubuntu/himanshunew/PlatformOps/platform/ansible/service_config_snapshot.sh"
PLAYBOOK_SRC_HOST="/home/ubuntu/himanshunew/PlatformOps/platform/ansible/playbook/service_config_snapshot_playbook.yml"

[[ -f "$SCRIPT_SRC_HOST" ]] || die "missing script: $SCRIPT_SRC_HOST"
[[ -f "$PLAYBOOK_SRC_HOST" ]] || die "missing playbook: $PLAYBOOK_SRC_HOST"

docker inspect "$CPLATFORM_CONTAINER" >/dev/null 2>&1 || die "PlatformOps container not found: $CPLATFORM_CONTAINER"

echo "[1/4] Copy snapshot artifacts into ${CPLATFORM_CONTAINER}"
docker cp "$SCRIPT_SRC_HOST" "${CPLATFORM_CONTAINER}:/app/platform/ansible/service_config_snapshot.sh"
docker cp "$PLAYBOOK_SRC_HOST" "${CPLATFORM_CONTAINER}:/app/platform/ansible/playbook/service_config_snapshot_playbook.yml"
docker exec "$CPLATFORM_CONTAINER" bash -lc "chmod +x /app/platform/ansible/service_config_snapshot.sh"

echo "[2/4] Run ansible snapshot playbook"
EXTRA_VARS=(
  "-e" "script_src=/app/platform/ansible/service_config_snapshot.sh"
  "-e" "container_name=${TARGET_CONTAINER}"
  "-e" "node_volume=${NODE_VOLUME}"
)
if [[ -n "$SERVICE_NAME" ]]; then
  EXTRA_VARS+=("-e" "service_name=${SERVICE_NAME}")
fi
if [[ -n "$CONFIG_PATH" ]]; then
  EXTRA_VARS+=("-e" "config_path=${CONFIG_PATH}")
fi

docker exec "$CPLATFORM_CONTAINER" bash -lc \
  "ansible-playbook \
    -i /app/platform/ansible/inventory/dynamicInventory${NODE_ID}.yaml \
    /app/platform/ansible/playbook/service_config_snapshot_playbook.yml \
    ${EXTRA_VARS[*]}"

echo "[3/4] Auto-sync fetched snapshot tree into ${PUBLISH_ROOT}"
FETCH_BASE="/home/ubuntu/Backup_Platform/app/logs/config_snapshots"
mkdir -p "$PUBLISH_ROOT"
while IFS= read -r src_dir; do
  rsync -a "${src_dir}/" "${PUBLISH_ROOT}/"
done < <(find "$FETCH_BASE" -type d -path "*/home/ubuntu/Backup_Platform/config")

echo "[4/4] Verify latest snapshots under ${PUBLISH_ROOT}"
find "$PUBLISH_ROOT" -type f -name config.yaml | sort | tail -n 20

echo "DONE: snapshots are now available under ${PUBLISH_ROOT}/<service>/<version>/<timestamp>/config.yaml"

