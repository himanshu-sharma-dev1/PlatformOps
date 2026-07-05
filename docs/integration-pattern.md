# PlatformOps Service Integration Guide

Welcome to PlatformOps! This document outlines the standard pattern for integrating your custom models, APIs, and microservices into the PlatformOps ecosystem. By following these conventions, your service will automatically benefit from centralized configuration management, log aggregation, metric scraping, and dependency-aware lifecycle orchestration.

## 1. Application Structure

Your application should be containerized and expose a web server (e.g., FastAPI, Express, Spring Boot) for serving traffic and health status.

A standard project structure looks like this:
```
apps/my-service/
├── Dockerfile          # Multi-stage production ready Dockerfile
├── requirements.txt    # Or package.json, go.mod, etc.
├── src/                # Application source code
│   ├── main.py         # Entrypoint
│   └── ...
└── config.yaml         # Default configuration (mounted by PlatformOps at runtime)
```

## 2. API Endpoints

To integrate with PlatformOps observability and health-checks, your service MUST implement the following endpoints:

### `GET /health`
Returns the liveness status of your service.
- **200 OK**: The service is running and ready to serve traffic.
- **503 Service Unavailable**: The service is down or still initializing.

*Example Response:*
```json
{
  "status": "up",
  "version": "1.0.0",
  "uptime": 3600
}
```

### `GET /metrics` (Optional but Highly Recommended)
Exposes Prometheus-compatible metrics. If provided, PlatformOps will automatically configure the observability plane to scrape this endpoint.

## 3. Configuration Management

PlatformOps manages environment variables and config files via `ConfigSnapshot` records. 
- **Environment Variables**: Prefer loading sensitive secrets (e.g., DB credentials, API keys) via environment variables. PlatformOps injects these securely during deployment.
- **Config Files**: If your service requires a complex configuration file (e.g., `config.yaml` or `settings.json`), design your service to read this file from a predictable path (e.g., `/app/config.yaml`). PlatformOps will mount the active `ConfigSnapshot` at this path during runtime.

## 4. Logging Standards

PlatformOps utilizes an Alloy/Loki pipeline for log aggregation. To ensure your logs are properly parsed and indexed:
1. **Log to stdout/stderr**: Do not write logs to local files inside the container unless strictly necessary.
2. **Structured JSON**: Emit logs as structured JSON where possible. This allows for rich filtering in the PlatformOps UI.
3. **Trace IDs**: If your service processes requests, include a `trace_id` in your log payload for distributed tracing.

*Example Log Payload:*
```json
{
  "timestamp": "2026-07-04T12:00:00Z",
  "level": "INFO",
  "module": "api.inference",
  "message": "Processed model inference request successfully",
  "trace_id": "req_abc123",
  "latency_ms": 124
}
```

## 5. Deployment with PlatformOps

Once your service follows these conventions, you can add it to the PlatformOps catalog. When creating a `ServiceInstance` via the API or Web Dashboard:
- Specify your Docker image.
- Map the required dependencies (e.g., `postgres-core`). PlatformOps' dependency guardrail will ensure your DB is ready before your service starts.
- Link the necessary `ConfigSnapshot`.
