# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Docker binary from host to bypass repository network issues
COPY ops/docker/web-api/docker /usr/bin/docker

# Create a non-root user/group for security compliance
RUN groupadd -g 10001 appgroup && \
    useradd -u 10000 -g appgroup -m -s /bin/bash appuser

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Replicate the project directory structure so relative settings paths resolve correctly
COPY apps/api/platformops /app/apps/api/platformops
COPY catalog /app/catalog
COPY ops/ansible /app/ops/ansible

# Install community.docker collection for root and appuser
RUN ansible-galaxy collection install community.docker

# Ensure output directory exists and is owned by appuser
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser
RUN ansible-galaxy collection install community.docker

# Environment variables
ENV PORT=8000
ENV HOST=0.0.0.0
ENV PLATFORMOPS_DATABASE_URL=sqlite:////app/data/platformops.db
ENV PLATFORMOPS_LOCAL_MODE=true

EXPOSE 8000

# Start FastAPI application via Uvicorn with proper app-dir setting
CMD ["uvicorn", "platformops.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
