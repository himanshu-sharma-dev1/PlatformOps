# PlatformOps: Diagnostics & Log Analyst Technical Specification

**Canonical Path:** `docs/features/diagnostics-page-detailed-features.md`
**Related Parity Action Matrix:** [`docs/selected-page-functional-parity.md`](../selected-page-functional-parity.md) §3
**Authoritative E2E Test Fixture:** [`docs/redis-seven-page-acceptance-fixture.md`](../redis-seven-page-acceptance-fixture.md) (Phase 5)

---

## 1. Architectural Overview & Workspaces

The PlatformOps Diagnostics workspace (`apps/web/src/views/DiagnosticsView.tsx`) and AI Log Analyst console (`apps/web/src/views/LogAnalystChat.tsx`) provide comprehensive operational log stream analysis, real-time container tailing, historical Loki cursor pagination, log file archive management, and LLM-assisted root cause analysis.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Diagnostics & Logs Workspace                      │
├───────────────────┬─────────────────────────────────────────────────────────┤
│ Left Service Tree │ Main Workspace Tabs:                                    │
│ - Cluster Nodes   │ 1. [Overview & Health] — Summary, target selector, checklist│
│ - Service Leaf    │ 2. [Live Tail]         — Real-time stream & CSS sparkline   │
│   (e.g. redis-core│ 3. [Loki History]      — Stateful anchor cursor pagination  │
│     SERV1000)     │ 4. [Log Archives]      — Raw file browser & streaming ZIP   │
│                   │ 5. [AI Log Analyst]    — Multi-turn LLM root cause analysis │
└───────────────────┴─────────────────────────────────────────────────────────┘
```

---

## 2. REST API Inventory

Backed by routers `apps/api/platformops/routers/diagnostics.py`, `services.py:342-590`, `misc.py`, and orchestrators `orchestrator/diagnostics/impl.py` and `orchestrator/llm.py`.

| Method | Endpoint Path | Description | Implementation Reference |
|---|---|---|---|
| `GET` | `/api/diagnostics/ingestion-stats` | Cluster-wide log ingestion rate (eps) and 1h error counts from Loki | `routers/diagnostics.py:15-18` |
| `GET` | `/api/diagnostics/logs` | Direct PromQL/LogQL log query range endpoint | `routers/diagnostics.py:20-37` |
| `GET` | `/api/services/{id}/diagnostics` | Service health checklist (CPU, memory, disk, uptime, restart counts) | `routers/services.py:342-366` |
| `GET` | `/api/services/{id}/diagnostics/analysis` | Automated anomaly detection, error spike detection, and pattern analysis | `routers/services.py:368-392` |
| `GET` | `/api/services/{id}/diagnostics/targets` | Discovers co-located service container targets (`main`, `worker`, `db`) | `routers/services.py:394-397` |
| `GET` | `/api/services/{id}/diagnostics/live` | Live container stdout/stderr log stream (accepts `target_service_key`) | `routers/services.py:399-429` |
| `GET` | `/api/services/{id}/diagnostics/file-tail` | Real-time tailing of discrete host `.log` files via SSH/local reader | `routers/services.py:501-509` |
| `GET` | `/api/services/{id}/diagnostics/container-history` | Loki stdout/stderr query with bidirectional anchor timestamp cursors | `routers/services.py:530-558` |
| `GET` | `/api/services/{id}/diagnostics/file-history` | Loki query of discrete Promtail-ingested file logs with cursor pagination | `routers/services.py:511-528` |
| `GET` | `/api/services/{id}/diagnostics/archives` | Lists discovered log archive files on host volume mounts | `routers/services.py:432-435` |
| `GET` | `/api/services/{id}/diagnostics/archives/{id}/view` | Read-only raw log viewer for a specific archive file | `routers/misc.py:11-25` |
| `GET` | `/api/services/{id}/diagnostics/archives/{id}/download` | Direct file download of a single log archive | `routers/services.py:437-462` |
| `POST` | `/api/services/{id}/diagnostics/archives/bulk-download` | Streams in-memory `.zip` bundle containing all selected log archives | `routers/services.py:464-499` |
| `POST` | `/api/services/{id}/diagnostics/backfill` | Triggers Promtail backfill pipeline from archive files into Loki | `routers/services.py:588-591` |
| `POST` | `/api/services/{id}/diagnostics/chat` | AI Log Analyst query with log context window, cited spans, and runbook triggers | `routers/services.py:560-586` |

---

## 3. Core Subsystem Mechanics

### 3.1 Multi-Target Diagnostics Scoping
Services composed of multiple containers (e.g. multi-process apps, sidecars, or databases):
* `GET /api/services/{id}/diagnostics/targets` identifies available sub-targets.
* All tail and analysis routes accept `target_service_key` query parameter to inspect specific container targets without changing active service selection.
* `DiagnosticsView.tsx:127-145` renders dynamic pill buttons for immediate target context switching.

### 3.2 18-Bin Square-Root Scaled Event Rate Sparkline
To visualize log velocity and error distribution in real time without being skewed by high-frequency `INFO` volume:
* Loads log entries and chronologically partitions them into **18 distinct bins**.
* Calculates bar height using square-root scaling:
  $$H = 4\text{px} + \text{round}\left( \frac{\sqrt{\text{BinLines}}}{\sqrt{\text{MaxBinLines}}} \times 28\text{px} \right)$$
* Styles bars using stacked CSS linear gradients: `var(--info)` (blue), `var(--warn)` (orange), `var(--err)` (red).

### 3.3 Loki Stateful Cursor Pagination Engine
Because Loki LogQL queries operate on timestamps rather than SQL offsets:
* Queries `count_over_time` to calculate total pages and lines.
* Generates base64-encoded cursor tokens containing the page anchor timestamp (`anchor_ts`), direction (`older`/`newer`), and selector tags.
* Enables bidirectional browsing (`next_cursor` / `previous_cursor`) with responsive `Page X / Y` controls in `DiagnosticsView.tsx:357-379`.

### 3.4 Multi-Provider LLM Log Analyst Engine (`orchestrator/llm.py`)
Provides intelligent root-cause analysis based on live context:
* **Supported Providers**:
  - **Groq** (`llama-3.1-8b-instant` via `https://api.groq.com/openai/v1`)
  - **Mistral** (`mistral-medium-2508` via `https://api.mistral.ai/v1`)
  - **Local Ollama** (`llama3.1:latest` via `http://localhost:11434/v1` with 16k context)
* **Prompt & Schema**: Injects up to 80 recent log lines, service health state, and enforces strict JSON response formatting (`{answer, evidence, chart_data, suggestions}`).
* **Cited Evidence Spans**: Injects `<span class="cited">` markers matching log timestamps.
* **Automated Runbook Action Triggers**: `LogAnalystChat.tsx` renders interactive buttons executing direct SRE remediation runbooks (Restart service, Rollback config, Recheck dependencies).

### 3.5 Streaming Bulk Archive ZIP Downloads
* `POST /api/services/{id}/diagnostics/archives/bulk-download` takes a list of `archive_ids`.
* Reads files from host volumes or container directories.
* Generates an in-memory ZIP stream using Python `zipfile.ZipFile` and returns a `StreamingResponse` (`application/zip`).
* Emits an `OperationalEvent` audit log.

---

## 4. Authoritative Verification via Golden Fixture (Redis Target)

Authoritative Diagnostics verification follows Phase 5 of `docs/redis-seven-page-acceptance-fixture.md`:
1. **Live Tail**: Tail stdout of `redis-core` $\to$ emit `redis-cli ping` and synthetic commands $\to$ verify lines appear in live console.
2. **Loki History**: Query Loki via `container-history` $\to$ verify cursor tokens and pagination controls.
3. **Log Archives & Bulk ZIP**: Stage test `.log` files in Redis volume $\to$ query `/archives` $\to$ execute `POST /archives/bulk-download` and assert valid ZIP payload.
4. **Log Analyst Chat**: Submit prompt *"Analyze recent Redis activity"* $\to$ assert structured JSON answer, cited evidence, and suggestion chips.
