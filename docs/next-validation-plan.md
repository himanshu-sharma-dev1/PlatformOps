# Next validation plan: selected-page MVP behavior

This is an ordered behavior-validation plan, not a hardening backlog. Every
mutating step uses a disposable isolated fixture and records terminal API/job
states, returned payloads, and runtime evidence. The selected-page behavior
mapping is [here](selected-page-functional-parity.md); the evidence ledger is
[`mvp-status.md`](mvp-status.md). The authoritative milestone run uses the
single canonical Redis target and ordered phases in
[`redis-seven-page-acceptance-fixture.md`](redis-seven-page-acceptance-fixture.md).
Redis is the one managed subject for the six operational pages; Users uses the
same run with disposable accounts and Mailpit.

## Preconditions and safety gate

Run from `/root/PlatformOps` with Docker Engine/Compose v2, permission to run
privileged DinD, and network access for image pulls. Confirm that host ports
9020 and, when Mailpit is enabled, 9010 are free for the planned run. Do not
stop, reconfigure, inspect through, or attach to the cPlatform stack.

```sh
make isolated-verify
docker compose -f ops/compose/docker-compose.isolated.yml --profile isolated --profile mailpit config --quiet
docker compose ls --all
```

The target must be Compose project `platformops-isolated`, network
`platformops-isolated_default`, and API `http://127.0.0.1:9020`. Port 9002,
network `cplatform_iktara_cPlatform`, and the host Docker socket are forbidden.
Save command output and the project/container list as the run manifest.

## 1. Fresh isolated fixture

Purpose: remove retained entities and stale jobs before any MVP claim. This is
the only deliberately destructive reset in the plan; confirm the project name
and volumes before running it.

```sh
docker compose --project-name platformops-isolated \
  --file ops/compose/docker-compose.isolated.yml \
  --profile isolated --profile mailpit --profile glitchtip \
  down --volumes --remove-orphans
make build
make isolated-up
PLATFORMOPS_ENABLE_MAILPIT=1 PLATFORMOPS_SMTP_HOST=mailpit make isolated-up
```

Evidence expected:

- `docker compose ls --all` shows the isolated project running; cPlatform
  remains running and unchanged.
- `GET /api/health` is 200; the UI/API is on 9020; Mailpit UI is on 9010.
- Postgres contains only the bootstrap administrator before the test; the
  DinD engine has no test containers; Mailpit has zero baseline messages.
- `docker network inspect platformops-isolated_default` contains only the
  isolated services, and no isolated container is on
  `cplatform_iktara_cPlatform`.

Acceptance gate: all preconditions and baseline checks pass, with the
timestamped manifest attached. If the fixture is not empty or image/build
provenance is unclear, stop and reset rather than interpreting retained state.

## 2. Cluster-first authoritative E2E

Purpose: prove the primary operator path before testing secondary pages.

The current `scripts/run_e2e_tests.py` remains a useful regression baseline,
but it is not by itself the final seven-page proof: it excludes invite mail and
does not yet implement the complete golden Redis evidence/cleanup contract.
Use it until the modular golden-fixture harness exists, then make it a wrapper
or compatibility entry point for that harness rather than maintaining two
different definitions of success.

```sh
PLATFORMOPS_E2E_BASE=http://localhost:9020 python3 scripts/run_e2e_tests.py
```

The script must use the canonical `http://localhost:9020` target; leave
`PLATFORMOPS_E2E_ALLOW_NON_ISOLATED` unset and leave `SKIP_GLITCHTIP=1` for
this cluster-first run. Capture its full stdout, created resource IDs, every
job ID plus terminal response, and the final cleanup responses. Also capture:

```sh
docker compose --project-name platformops-isolated \
  --file ops/compose/docker-compose.isolated.yml \
  --profile isolated exec -T docker-engine \
  docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
docker compose --project-name platformops-isolated \
  --file ops/compose/docker-compose.isolated.yml \
  --profile isolated --profile mailpit ps
```

Evidence must show, in order: cluster create/list/update; node create,
validation, readiness, and connection probe; catalog service create; real
dependency preflight; deploy job reaching `success`; live status from the
isolated Docker endpoint; diagnostics containing the deployed container's real
Redis readiness output; and cleanup with service, node, and cluster reaching
terminal deleted states. Do not accept a database row or simulated event in
place of a Docker-engine observation.

Acceptance gate: auth phase 0 and all eight numbered functional phases (1–8)
pass, the Redis container is running inside DinD, the real readiness line is
present, and cleanup is terminal. A GlitchTip skip and the script's explicit
“mailing/SMTP/invite-email excluded” message are expected here; they are not
evidence for those capabilities.

## 3. Config apply/restore terminal-state proof

Purpose: resolve the retained fixture's failed restore job and prove actual
apply/restore behavior, not merely HTTP acceptance.

Use the fresh service ID from milestone 2. Authenticate with the bootstrap
admin, then run the Config workspace, validate, snapshot, apply, compare, and
restore calls used by `scripts/run_e2e_tests.py`. For every job, poll
`GET /api/jobs/{id}` until one of `success`, `failed`, or `error`, and save the
terminal JSON and job output/error. Require `success` for both apply and
restore. Verify the content marker in the target host path/container after
apply and verify the pre-apply content after restore.

Evidence expected:

- workspace and snapshots identify the same service and source;
- validation returns `ok=true`;
- apply and restore each return a job ID and reach `success` with no detached
  ORM/callback error;
- compare, drift, rename, and timeline responses refer to the resulting
  versions; and
- the actual isolated service/container reflects the restored content.

Acceptance gate: no job is accepted solely because its HTTP response is 200;
both terminal jobs are successful and content is verified at the runtime
target. If either job fails, record the exact output/error and leave Config in
the **Unverified** state.

## 4. Observability and metrics proof

Purpose: distinguish implemented query routes from actual telemetry.

With the same isolated fixture, call the authenticated read-only endpoints:

```sh
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:9020/api/observability/pipeline
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:9020/api/observability/status
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:9020/api/metrics/node
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:9020/api/metrics/processes?node_id=$NODE_ID"
```

Record the Prometheus/Loki URLs, response payloads, `prometheus_reachable`,
pipeline readiness, collector status, and any returned series. If values are
empty, query Prometheus directly inside its isolated container to show whether
the relevant series are absent; do not turn an empty result into a success
claim. If collectors/exporters are intentionally deployed, capture their
container status and a non-empty query result.

Acceptance gate: the APIs return schema-valid, honest status; a reachable
Prometheus path has either traceable non-empty series or a documented empty
state caused by absent exporters; no cPlatform telemetry endpoint is used.
Loki history/backfill remains unproven unless an actual isolated collector
ships and the resulting stream is retrieved.

## 5. User invite and Mailpit proof

Purpose: close the capability intentionally excluded from the main E2E suite.
Keep Mailpit enabled on 9010 and SMTP internal at `mailpit:1025`. Use a unique
test address per fresh fixture.

1. Log in as the bootstrap administrator.
2. `POST /api/users/invite` with a unique `user_name`, `user_email`, and
   `user_role=Operational`.
3. Query Mailpit's local API/UI at `http://127.0.0.1:9010` and prove one new
   message has the exact recipient, subject `PlatformOps invitation`, and an
   activation URL/token.
4. `GET /api/auth/invite/{token}` and require `state=valid`.
5. `POST /api/auth/invite/{token}/accept` with a temporary password, then log
   in as the invited user and verify the user is active.
6. Delete or revoke the disposable user through the authenticated admin path;
   record the Mailpit message ID and final database/user state.

Acceptance gate: the message is new in this fixture (not the historical
2026-08-10 message), delivery and token preview succeed, accept changes the
user to active, and the invited user can authenticate. If SMTP is disabled,
that is an honest negative result, not Mailpit proof.

## 6. Optional GlitchTip and remote disposable proof

Purpose: validate integrations that are outside the base MVP fixture without
touching cPlatform or production credentials. Run only after milestones 1–5.

For isolated GlitchTip, use a fresh project and explicit profile:

```sh
PLATFORMOPS_ENABLE_GLITCHTIP=1 \
PLATFORMOPS_ENABLE_MAILPIT=1 PLATFORMOPS_SMTP_HOST=mailpit \
  make isolated-up
```

Record `docker compose ps`, the authenticated IntegrationStatus/Health/Uptime/
Keys responses, and the GlitchTip service logs. Keep exception capture and
mail-producing paths disabled unless the test explicitly observes Mailpit.
The GlitchTip profile has no host port; do not substitute cPlatform ports 9008
or 9011. Acceptance requires the isolated endpoint to respond and the API to
report its actual configured/unconfigured state.

For remote SSH/cloud behavior, use only a disposable node/VM and temporary
credentials approved for this test. Exercise node validation, connection,
discovery, live status, one catalog deployment, logs, and teardown. Capture
the remote endpoint/container identity and prove that a remote failure does
not fall back to the local DinD engine. Acceptance requires clean teardown,
no persistent credential leakage, and no cPlatform network, volume, or
container changes. Without such a disposable environment, leave this
milestone **Unverified**.

## Evidence handoff

Store long transcripts under `/tmp` during a run, then promote only concise
facts and exact residual failures to [`mvp-status.md`](mvp-status.md). Run
`git diff --check` after documentation changes. A validation pass is complete
only when each milestone has its commands, terminal evidence, and acceptance
gate recorded; historical or retained-runtime observations never substitute
for a fresh fixture.
