FROM alpine:3.20

ARG PROCESS_EXPORTER_VERSION=0.8.7

RUN apk add --no-cache ca-certificates curl tar

RUN arch="$(apk --print-arch)" \
    && case "${arch}" in \
        x86_64) exporter_arch="amd64" ;; \
        aarch64) exporter_arch="arm64" ;; \
        *) echo "Unsupported architecture: ${arch}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL -o /tmp/process-exporter.tar.gz \
      "https://github.com/ncabatoff/process-exporter/releases/download/v${PROCESS_EXPORTER_VERSION}/process-exporter-${PROCESS_EXPORTER_VERSION}.linux-${exporter_arch}.tar.gz" \
    && tar -xzf /tmp/process-exporter.tar.gz -C /tmp \
    && mv "/tmp/process-exporter-${PROCESS_EXPORTER_VERSION}.linux-${exporter_arch}/process-exporter" /usr/local/bin/process-exporter \
    && chmod +x /usr/local/bin/process-exporter \
    && rm -rf /tmp/process-exporter*

COPY platform/docker/process-exporter/process-exporter.yml /etc/process-exporter/process-exporter.yml
COPY platform/docker/process-exporter/docker-entrypoint.sh /usr/local/bin/process-exporter-entrypoint.sh

RUN chmod +x /usr/local/bin/process-exporter-entrypoint.sh \
    && mkdir -p /etc/process-exporter /var/log/process-exporter

EXPOSE 9256

ENTRYPOINT ["/usr/local/bin/process-exporter-entrypoint.sh"]
