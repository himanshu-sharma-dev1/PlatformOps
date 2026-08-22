#!/bin/sh
set -eu

# sshd does not preserve the container environment for non-login commands;
# force the disposable DinD TCP endpoint so every remote Docker operation is
# target-bound and no Unix/host socket fallback is possible.
export DOCKER_HOST="${DOCKER_HOST:-tcp://docker-engine:2375}"
exec /usr/bin/docker.real "$@"
