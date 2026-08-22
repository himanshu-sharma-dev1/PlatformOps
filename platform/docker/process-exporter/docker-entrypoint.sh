#!/bin/sh
set -eu

mkdir -p /var/log/process-exporter

exec /bin/sh -c '/usr/local/bin/process-exporter --procfs /host/proc --config.path /etc/process-exporter/process-exporter.yml --web.listen-address=:9256 2>&1 | tee -a /var/log/process-exporter/process-exporter.log'
