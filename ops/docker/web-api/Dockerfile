# Production image for the PlatformOps control plane.
#
# The React application is built in this image so the API and UI are shipped
# together.  Runtime Docker operations use the isolated docker-engine service
# (DOCKER_HOST is set by the isolated Compose file); this image never needs a
# host Docker socket.

FROM node:20-alpine AS web-builder

WORKDIR /web

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY apps/web/ ./
RUN npm run build


FROM python:3.12-slim AS api-dependencies

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "psycopg[binary]>=3.2,<4"


FROM python:3.12-slim AS runner

WORKDIR /app

# The API invokes the Docker CLI for local discovery/config operations.  The
# daemon itself is supplied by docker-engine in the isolated Compose project.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Debian's docker.io package does not consistently ship the client binary in
# slim runtime images. Keep the known-good client used by the observability
# and local discovery paths; it talks to the isolated DOCKER_HOST only.
COPY ops/docker/web-api/docker /usr/bin/docker
RUN chmod 0755 /usr/bin/docker

# Keep the Compose CLI available for the API's observability playbooks while
# still connecting it to DOCKER_HOST (never to a host socket).
RUN mkdir -p /usr/libexec/docker/cli-plugins
COPY ops/docker/web-api/docker-compose /usr/libexec/docker/cli-plugins/docker-compose
RUN chmod 0755 /usr/libexec/docker/cli-plugins/docker-compose

# Create a non-root runtime user.  Docker-over-TCP does not require access to a
# host socket, so the user does not receive a docker group or host privileges.
RUN groupadd -g 10001 appgroup && \
    useradd -u 10000 -g appgroup -m -s /bin/bash appuser

COPY --from=api-dependencies /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Keep the source layout expected by settings.resolve() and the orchestrator.
COPY apps/api/platformops /app/apps/api/platformops
COPY catalog /app/catalog
COPY ops/ansible /app/ops/ansible
COPY ops/compose /app/ops/compose

# The frontend is served by FastAPI from this image at /app/dist.
COPY --from=web-builder /web/dist /app/dist

# Install the Ansible collection used by local/remote orchestration paths for
# both the image build user and the unprivileged application user.
RUN ansible-galaxy collection install community.docker \
    && mkdir -p /app/data /home/appuser/.ansible \
    && chown -R appuser:appgroup /app /home/appuser/.ansible

USER appuser
RUN ansible-galaxy collection install community.docker

ENV PORT=8000 \
    HOST=0.0.0.0 \
    PLATFORMOPS_DATABASE_URL=postgresql+psycopg://platformops:platformops@postgres:5432/platformops \
    PLATFORMOPS_LOCAL_MODE=false \
    PLATFORMOPS_PUBLIC_BASE_URL=http://localhost:9004 \
    PLATFORMOPS_GLITCHTIP_BASE_URL=http://glitchtip:8000 \
    PLATFORMOPS_PROMETHEUS_BASE_URL=http://prometheus:9090 \
    PLATFORMOPS_LOKI_BASE_URL=http://loki:3100

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=6 \
    CMD curl --fail --silent http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "platformops.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
