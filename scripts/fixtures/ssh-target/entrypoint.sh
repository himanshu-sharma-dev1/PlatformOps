#!/bin/sh
set -eu

key_file=${ACCEPTANCE_SSH_AUTHORIZED_KEY_FILE:?authorized key file is required}
[ -s "$key_file" ] || { echo "authorized key file is empty" >&2; exit 2; }

ssh-keygen -A >/dev/null 2>&1
install -d -m 0700 /root/.ssh
install -m 0600 "$key_file" /root/.ssh/authorized_keys
cat >/etc/ssh/sshd_config <<'EOF'
Port 22
ListenAddress 0.0.0.0
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
StrictModes yes
PidFile /run/sshd.pid
# Ansible's community.docker module uses the remote Python SDK rather than the
# CLI wrapper, so pin its daemon endpoint in every SSH session as well.
SetEnv DOCKER_HOST=tcp://docker-engine:2375
EOF

# Docker CLI traffic is deliberately TCP-only and stays inside the private
# acceptance network; no /var/run/docker.sock is mounted in this target.
exec /usr/sbin/sshd -D -e
