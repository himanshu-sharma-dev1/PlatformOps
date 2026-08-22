#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_TAG="${1:-iktaraai/services:glitchtip-iktara-6.1.9}"

cd "$REPO_ROOT"
docker build -f platform/observability/glitchtip-image/Dockerfile -t "$IMAGE_TAG" .

echo "Built $IMAGE_TAG"
