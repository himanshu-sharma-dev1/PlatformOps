# Project Diary

Record only durable decisions, discarded approaches, and reusable lessons.

## Decisions and Lessons

- **2026-08-13 — Initial context:** The repository's acceptance scope was the
  selected-page MVP, with Cluster → Node → Service as the primary integration
  path.
- **2026-08-13 — Isolation boundary:** Runtime verification uses the private
  `platformops-isolated` Compose/DinD environment; the legacy cPlatform stack,
  network, database, volumes, and host Docker socket remain out of scope.
- **2026-08-13 — Truthful operations:** Missing collectors or external runtime
  access must be represented as empty/unavailable/degraded state rather than
  simulated success.
- **2026-08-21 — Evidence taxonomy:** “Implemented” is not equivalent to
  runtime-tested. Durable status uses Mapped, Implemented, Contract-tested,
  Runtime-proven, and bounded Parity-complete labels.
- **2026-08-21 — Authoritative source:**
  `docs/selected-page-functional-parity.md` and the seven page plans supersede
  older page analyses for current-state claims; historical evidence remains
  labeled as such.
- **2026-08-21 — Port migration:** The current isolated API port is `9020`,
  Mailpit is `9010`, and live cPlatform port `9002` stays blocked.
- **2026-08-22 — One-service acceptance:** Two independent phase-0–8 runs used
  the same canonical `redis-core` identity across all operational pages. A
  green harness banner is insufficient without direct side effects,
  terminal-state, failure/recovery, and residue assertions.
- **2026-08-22 — SSH boundary:** A disposable private SSH target proved remote
  behavior and no local fallback. The supplied external `216.48.189.195`
  credential was rejected and is not an acceptance target.
- **2026-08-22 — Safety disclosure:** Protected cPlatform membership and
  runtime identity comparisons were equal, but a pre-existing `SERV1006`
  restart loop changed its restart-count endpoint/MAC during observation. This
  external volatility must not be rewritten as blanket immutability.
- **2026-08-22 — Closure:** The bounded seven-page deployment is complete; the
  remaining legacy action rows stay at their evidence state until a future
  fresh isolated run proves them.
