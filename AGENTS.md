<!-- codex-workflow-id: viettran-edgeAI/codex_workflow -->
<!-- codex-workflow-managed-start -->
# AGENTS.md

## Project Context


## Design Principles

- Keep modules cohesive, interfaces explicit, coupling minimal, and behavior
  testable, replaceable, and reusable.
- Define proportionate acceptance and verification before implementation. Keep
  related tests cohesive; never weaken coverage, assertions, or failure
  visibility to save time or tokens.
- Preserve unrelated user work and use verified facts in durable documentation.

Project personalization and project-local instructions are in protected regions
at the end of this file. They override conflicting workflow defaults, but not
higher-level instructions.

## Working State

- `deployment state`: planning or executing a broad, possibly multi-session
  deployment plan.
- `leaf state`: work outside that plan, including general questions and small,
  bounded edits or operations.

## Project Documentation

The durable project documents are under `agent_docs/`:

- `project_overview.md`: goals, architecture, workflow, and major decisions.
- `project_core_tech.md`: concise special technology or architecture notes.
- `project_structure.md`: layout, modules, components, and ownership.
- `project_progress.md`: goal, overall progress, current position, next milestone.
- `project_diary.md`: lasting decisions, discarded approaches, and lessons.
- `latest_session_work.md`: detailed handoff evidence and continuation point.
- Module-specific documents, when present.

`project_progress.md` and `latest_session_work.md` may be edited only in
`deployment state` or when the user explicitly requests it. The main agent owns
them during normal execution. During automatic deployment closure, the single
`end_of_session` worker owns reconciliation of the complete documentation
framework; no other worker participates in that closure update.

Keep raw logs, temporary reasoning, and short-lived checkpoints out of durable
documents. Never delete a main project document without warning the user and
receiving a second explicit confirmation.

## Route Selection

There are three routes:

- **Light**: leaf-state work. The main agent works directly; no subagents.
- **Medium**: deployment-state work performed by the main agent. Explorer and
  the dedicated End-of-Session worker are the only subagent exceptions. Read
  `~/.codex/codex_workflow/medium_route.md`.
- **Heavy**: deployment-state work orchestrated through specialized workers.
  Read `~/.codex/codex_workflow/heavy_route.md`.

The user selects the route for the session. If unspecified, use Light; do not
infer Medium or Heavy. Light implies `leaf state`; Medium and Heavy imply
`deployment state` only for substantive work. Their direct fast path remains
`leaf state`. Keep the selected route until the user changes it or the session
ends.

## Context Loading

- In Light, inspect only material needed for the current task.
- Before initializing deployment state, classify the request. Questions and
  small or odd bounded tasks use the direct main-agent fast path even when
  Medium or Heavy is selected: call no worker, including Explorer and
  `end_of_session`, and produce no worker statistics.
- For every substantive Medium or Heavy deployment, read the selected route and
  `explorer_companion.md`, then initialize or reuse the single persistent
  Explorer.
- Give Explorer the session goal, known constraints, investigation questions,
  and boundaries. It reads the foundational project documents and relevant
  repository context, then returns the planning brief defined in its contract.
- In Medium, the main agent uses that brief to narrow its direct implementation
  inspection. In Heavy, Explorer is the default gateway for repository,
  architecture, dependency, and external research; the main agent normally
  consumes the brief rather than repeating discovery.
- The main agent may inspect any critical source or evidence, but should do so
  only when it materially affects a decision, resolves uncertainty or
  contradiction, or validates a high-risk integration boundary.
- Resolve stale or conflicting project status with targeted evidence. Load only
  relevant module documentation and avoid replaying raw logs, large diffs,
  directory listings, or complete source files into the main context.
- Before the final response that completes, pauses, or blocks each substantive
  Medium or Heavy deployment, run the automatic handoff defined in
  `end_of_session.md` exactly once. Its worker inherits recent main-agent
  context and performs the complete documentation-framework update. The
  handoff is not a user command.

## Platform Paths

Workflow documents use `/` as a platform-neutral separator. Translate paths to
the current operating system and shell when running filesystem commands.
<!-- codex-workflow-managed-end -->

<!-- codex-workflow-project-personalization-start -->
<!-- codex-workflow-project-personalization-end -->

<!-- codex-workflow-project-local-instructions-start -->
# Agent Rules — PlatformOps

## Change Control (Highest Priority)
- Do not make any code changes unless the user explicitly asks for code changes in the current request.
- Default behavior is analysis, checks, logs, diffs, and reporting only.
- If a request is ambiguous, assume **no code changes**.

## Git Identity (Strict)
All git commits must use this exact identity:
```
git config user.name "himanshu-sharma-dev1"
git config user.email "himanshu-sharma-dev1@users.noreply.github.com"
```

## Reference Codebase — No Edits
- `/home/ubuntu/cplatform_master` is a **read-only reference checkout** of the legacy cPlatform Django project.
- **Never modify files** inside `cplatform_master`. It exists solely for reading, comparing, and understanding legacy behavior.

## Feature Parity Rule
- Active scope is only: Clusters, Config Manager, Users, Monitoring,
  Performance, Diagnostics, and Observability.
- Do not add Batch/Stream I/O, Models, Applications, DB-pull inference, or
  Advanced pages as part of this parity program.
- Follow `docs/current-pages-cplatform-parity-plan.md`; use
  `docs/selected-page-functional-parity.md` as the authoritative action map.
- Observability includes only behavior traceable to cPlatform Monitoring,
  SystemMonitoring, Diagnostics, ClusterConfig, or their helpers. PlatformOps-
  only stack/SRE features do not count toward parity.
- Match cPlatform validation, defaults, persistence, side effects, errors, and
  lifecycle. UI styling may remain PlatformOps-native.
- Do not add, remove, or simplify cPlatform behavior for the scoped pages.
- Every new backend endpoint must have a corresponding Pydantic schema in `schemas.py`.
- Every mutating endpoint must call `record_event()` for audit logging.

## Evidence and Regression Rules
- Track Mapped, Implemented, Contract-tested, Runtime-proven, and
  Parity-complete per action. Endpoint existence is not completion.
- Async work is proven only after terminal job polling and verification of
  database plus real runtime side effects.
- Use `platformops-isolated`, API `9020`, optional Mailpit `9010`, and private
  DinD. Never touch live cPlatform port `9002`, its network/state, or the host
  Docker socket.
- Preserve valid `config_json` through deep merge. Remote failures never fall
  back to local Docker.
- Deliver bounded action groups and keep the complete seven-page regression
  baseline passing.
- Use `docs/redis-seven-page-acceptance-fixture.md` for authoritative E2E. One
  canonical `redis-core` service is the subject across Clusters, Config,
  Monitoring, Performance, Diagnostics, and Observability. Users is proved in
  the same run with disposable accounts and Mailpit. Exporters/telemetry/mail
  components are supporting infrastructure, not extra parity targets.

## Testing Discipline
- After backend changes, run targeted tests, API compilation, backend tests,
  `make isolated-verify`, and the affected isolated scenario.
- After frontend changes, run targeted frontend tests and
  `cd apps/web && npm run build` with installed dependencies.
- Before a parity milestone, run the full seven-page suite from a fresh
  disposable fixture and verify cleanup.
- If host tools are missing, test in the production image and report the limit;
  never claim an unexecuted test passed.

## Code Organization
- New orchestrator logic goes in the appropriate module under `apps/api/platformops/orchestrator/`.
- Export new public functions via `orchestrator/__init__.py`.
- Import in `main.py` via `from .orchestrator import <function_name>`.
- Frontend render functions follow the pattern `renderXxxView()` or `renderXxxWorkspace()` in `main.tsx`.
<!-- codex-workflow-project-local-instructions-end -->
