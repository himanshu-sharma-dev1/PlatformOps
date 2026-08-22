#!/bin/bash
set -e

# Target directory (defaults to the container path, falls back to a relative path)
TARGET_DIR="${1:-/iktara/cPlatform/platform/ansible}"
if [ ! -d "$TARGET_DIR" ]; then
    TARGET_DIR="$(dirname "$0")/../ansible"
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "Could not find ansible directory at $TARGET_DIR"
    exit 1
fi

echo "Patching Ansible playbooks and inventories in $TARGET_DIR to remove become/sudo privileges..."

find "$TARGET_DIR" -type f \( -name "*.yml" -o -name "*.yaml" \) -exec sed -i 's/become:[[:space:]]*true/become: false/gI' {} +
find "$TARGET_DIR" -type f \( -name "*.yml" -o -name "*.yaml" \) -exec sed -i 's/become:[[:space:]]*yes/become: false/gI' {} +
find "$TARGET_DIR" -type f \( -name "*.yml" -o -name "*.yaml" \) -exec sed -i 's/ansible_become:[[:space:]]*true/ansible_become: false/gI' {} +
find "$TARGET_DIR" -type f \( -name "*.yml" -o -name "*.yaml" \) -exec sed -i 's/ansible_become:[[:space:]]*yes/ansible_become: false/gI' {} +
find "$TARGET_DIR" -type f \( -name "*.yml" -o -name "*.yaml" \) -exec sed -i 's/sudo[[:space:]]*docker login/docker login/g' {} +

# Remove sudo commands from specific shell scripts
find "$TARGET_DIR" -type f \( -name "service_config_apply.sh" -o -name "service_config_snapshot.sh" \) -exec sed -i 's/sudo[[:space:]]*mkdir/mkdir/g' {} +
find "$TARGET_DIR" -type f \( -name "service_config_apply.sh" -o -name "service_config_snapshot.sh" \) -exec sed -i 's/sudo[[:space:]]*docker/docker/g' {} +

echo "All root privileges and sudo commands removed from Ansible playbooks and shell scripts."
