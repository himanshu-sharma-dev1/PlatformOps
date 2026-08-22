# Disposable NOC Kafka observability

`docker-compose.kraft.yml` starts the single-node demo broker and
`kafka-topic-init` creates the four topics before any producer or consumer
starts.  Kafka auto-creation stays disabled so a typo cannot silently create a
second stream.

For broker/topic/consumer-group metrics, run a Kafka exporter on the same
Compose network when Prometheus is available:

```bash
docker run --rm --name kafka-exporter --network <compose-network> \
  -e KAFKA_SERVER=kafka:9092 \
  -p 9308:9308 \
  danielqsj/kafka-exporter:v1.8.0
```

Add the exporter endpoint to the Prometheus configuration used by the demo:

```yaml
scrape_configs:
  - job_name: noc-kafka
    static_configs:
      - targets: [kafka-exporter:9308]
```

The exporter is optional and deliberately not part of the broker's default
startup path.  It is read-only; it does not create topics or change retention.
NiFi queue/backpressure and processor metrics remain on the NiFi/Prometheus
integration.  Keep labels bounded: do not turn row IDs, source filenames, or
alarm text into Prometheus labels.

## cPlatform NOC contract

The cPlatform service catalog registers the pinned exporter as
`InfraKafkaExporter` in `cPlatform/config/service_install.yaml`:

- image: `danielqsj/kafka-exporter:v1.8.0`
- network: `cplatform_iktara_cPlatform`
- exporter address: `180.75.0.63:9308`
- broker address: `180.75.0.31:9092`
- optional host publication: `9014:9308`

The NOC Prometheus configuration scrapes the exporter with the `noc-kafka` job
and scrapes NiFi through `/nifi-api/flow/metrics/prometheus`.  Prometheus uses
the exporter’s internal network address, so host-port publication is not
required for scraping.  Port `9014` is also the legacy default for the
process-exporter contract; do not expose both optional exporters on the same
host port at once.  Deploy the Kafka exporter through the service-install
catalog when that port is available, without restarting unrelated services.
