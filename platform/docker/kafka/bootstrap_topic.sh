#!/usr/bin/env bash
set -euo pipefail

# Run inside the Kafka container or against a reachable broker.  This script
# only creates the demo topics; it never deletes or truncates existing topics.
BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
KAFKA_BIN="${KAFKA_BIN:-/opt/bitnami/kafka/bin}"

TOPICS=(
  "noc.alarm.raw.v1|86400000"
  "noc.alarm.normalized.v1|86400000"
  "noc.incident.candidate.v1|86400000"
  "noc.alarm.dlq.v1|604800000"
)

for attempt in $(seq 1 30); do
  if "${KAFKA_BIN}/kafka-topics.sh" --bootstrap-server "${BOOTSTRAP_SERVERS}" --list >/dev/null 2>&1; then
    break
  fi
  if [[ "${attempt}" == "30" ]]; then
    echo "Kafka did not become ready at ${BOOTSTRAP_SERVERS}" >&2
    exit 1
  fi
  sleep 2
done

for topic_config in "${TOPICS[@]}"; do
  IFS='|' read -r topic retention_ms <<<"${topic_config}"
  "${KAFKA_BIN}/kafka-topics.sh" \
    --bootstrap-server "${BOOTSTRAP_SERVERS}" \
    --create --if-not-exists \
    --topic "${topic}" \
    --partitions 3 \
    --replication-factor 1 \
    --config cleanup.policy=delete \
    --config retention.ms="${retention_ms}"
  "${KAFKA_BIN}/kafka-topics.sh" --bootstrap-server "${BOOTSTRAP_SERVERS}" --describe --topic "${topic}"
done
