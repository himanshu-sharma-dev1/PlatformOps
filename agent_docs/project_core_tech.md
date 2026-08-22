# Project Core Technologies

## Languages and Runtimes

- Python 3.12 is the documented backend runtime; the API is packaged with
  Uvicorn and the frontend uses Node/npm during development and builds.
- The frontend is TypeScript/TSX and the repository includes a small example
  service under `apps/example-service/`.

## Frameworks and Libraries

- Backend: FastAPI `0.115.6`, Uvicorn `0.34.0`, Pydantic `2.10.4`,
  `pydantic-settings` `2.7.1`, SQLAlchemy `2.0.36`, PyYAML `6.0.2`,
  `python-multipart`, and `httpx`.
- Operations: `ansible-core` `2.16.3` and Docker SDK for Python `7.1.0`, with
  Ansible collections and Docker tooling supplied in the production image.
- Frontend: React `18.3.1`, React DOM `18.3.1`, TypeScript `5.5.4`, and Vite
  `5.4.0` with the Vite React plugin.

## Build, Test, and Development Tools

- Make targets cover FastAPI development, Vite development, Python
  compilation, pytest-based tests, the combined production image, isolated
  static verification, and isolated Compose lifecycle.
- `cd apps/web && npm run build` runs TypeScript compilation and the Vite
  production build. `make check` combines compilation, backend tests, and the
  isolated static verifier.
- `ops/docker/web-api/Dockerfile` builds the frontend and packages it with the
  API; `ops/ansible/` contains deployment, validation, config, logging, and
  observability playbooks.

## External Services and Infrastructure

- The isolated Compose stack provides PostgreSQL, Redis, RabbitMQ, Prometheus,
  Loki, and a private `docker:27.5.1-dind` engine. Mailpit and GlitchTip
  (`6.1.9` in the completed checkpoint) are disposable support profiles.
- Docker operations in the isolated stack use the private engine over
  `tcp://docker-engine:2375`; the stack does not mount the host Docker socket.
- Terraform AWS templates and a Helm chart exist for packaging/deployment
  scenarios but are outside the seven-page acceptance gate.

## Important Technical Constraints

- Use `ops/compose/docker-compose.isolated.yml` and project name
  `platformops-isolated` for safe runtime verification. Host port `9020` is
  the PlatformOps endpoint; optional Mailpit is `9010`. The legacy compatibility
  stack uses `9002` and must not be used for isolated acceptance.
- The bootstrap administrator defaults to `admin`/`admin` only for development;
  deployment environments must set the documented
  `PLATFORMOPS_BOOTSTRAP_ADMIN_*` settings.
- Prometheus/process metrics and Loki history are valid only when their
  collectors expose fresh, target-scoped evidence. Optional integrations must
  remain distinguishable as unavailable, empty, degraded, or healthy.
- The positive SSH branch used a disposable private target and proved no local
  fallback. The supplied credential for external `216.48.189.195` was
  rejected; cloud/provider launch and exhaustive catalog parity remain
  unverified.
- Current authoritative evidence is recorded in
  `/tmp/platformops-redis-acceptance/` for the two 2026-08-22 run IDs and is
  redacted; credentials, raw keys, and tokens are never durable project data.
