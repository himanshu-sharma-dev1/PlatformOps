# Plan: Phase A Integrity + Multiuser + cPlatform Log Analyst + LLM Keys

**Source of truth:** latest `cplatform_master` (pulled `origin/master`) + live PlatformOps `:9002`.  
**Date:** 2026-07-10  
**Scope:** implement now (user-approved).

---

## 0. Goals

| Track | Outcome |
|-------|---------|
| **Phase A** | Diagnostics Log Analyst uses real `POST /diagnostics/chat` only. No canned CPU/fake success text. Metrics stay empty when Prom has no data. |
| **Multiuser** | cPlatform-parity user system: roles, invite/accept/resend/revoke, CRUD, login sessions, last-visited snapshot. |
| **Log Analyst** | Same conversational contract as cPlatform `service_log_analytics_chat`: JSON `{answer, evidence, chart_data, suggestions}`, multi-turn history, evidence chips, mini chart, suggestion follow-ups. |
| **LLM** | Groq + Mistral keys/models from cPlatform `diagnostics.validation.env` wired into PlatformOps settings + compose. |

---

## 1. Credentials & env (from cPlatform)

Source file: `cplatform_master/platform/docker/cPlatform/diagnostics.validation.env`

| Setting (cPlatform) | PlatformOps mapping |
|---------------------|---------------------|
| `CPLATFORM_GROQ_API_KEY` | `PLATFORMOPS_GROQ_API_KEY` |
| `CPLATFORM_GROQ_MODEL` | `PLATFORMOPS_GROQ_MODEL` (default `llama-3.1-8b-instant`) |
| `CPLATFORM_LLM_PROVIDER` | `PLATFORMOPS_LLM_PROVIDER` (`mistral` \| `groq` \| `local`) |
| `CPLATFORM_LLM_API_KEY` | `PLATFORMOPS_LLM_API_KEY` / `PLATFORMOPS_MISTRAL_API_KEY` |
| `CPLATFORM_LLM_MODEL` | `PLATFORMOPS_LLM_MODEL` (default `mistral-medium-2508`) |
| `CPLATFORM_LLM_MAX_LOGS` | `PLATFORMOPS_LLM_MAX_LOGS` |
| `CPLATFORM_LLM_MAX_TAIL_LOGS` | `PLATFORMOPS_LLM_MAX_TAIL_LOGS` |
| `CPLATFORM_LLM_TIMEOUT` | `PLATFORMOPS_LLM_TIMEOUT` |

Provider resolution (match cPlatform `_execute_llm_request`):
- **groq** → `https://api.groq.com/openai/v1/chat/completions` + `GROQ` key/model
- **mistral** → `https://api.mistral.ai/v1/chat/completions` + LLM/Mistral key/model
- **local** → `PLATFORMOPS_LLM_URL` + optional key

Default provider for PlatformOps after copy: **`mistral`** (cPlatform live default) with Groq available as switch.

---

## 2. Phase A — integrity

### Backend
1. Shared `orchestrator/llm.py`: `is_llm_configured()`, `execute_llm_request(messages, response_format, temperature)`.
2. `service_log_analytics_chat` uses shared client; richer evidence (live logs + diagnostics analysis issue groups).
3. On LLM failure: return `success: false` + real `error` (never invent chart numbers or fake metrics).
4. Metrics: when Prom unreachable, empty series / nulls (no seed curves in live responses).

### Frontend
1. Replace `sendDirectAnalyticsQuery` / `handleSendAnalyticsChat` canned replies with API call.
2. Render: markdown answer, evidence list, `chart_data` bar strip, dynamic `suggestions`.
3. Require selected service; else prompt operator to select from tree.
4. Multi-turn: send last N user/assistant turns as `history`.

---

## 3. Multiuser system (cPlatform → PlatformOps)

### Data model
```
UserInfo
  user_id (8-char), user_email unique, user_name, user_role
  roles: System_Admin | Operational | Management
  status: active | pending | disabled
  user_number, password_hash, login_count
  session_info JSON (last_visited: {view, cluster, node, service})
  last_login_at, created_at

InviteToken
  token UUID PK, user_name, user_email, user_role, user_number
  permissions JSON, invited_by, created_at, is_used, is_revoked

AuthSession
  token, user_id, expires_at, created_at
```

### API surface
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/login` | email+password → session token |
| POST | `/api/auth/logout` | revoke session |
| GET | `/api/auth/me` | current user + session_info |
| POST | `/api/auth/last-visited` | update last_visited |
| GET | `/api/users` | list (Admin) |
| POST | `/api/users` | add active user (Admin) |
| PUT | `/api/users/{user_id}` | edit |
| DELETE | `/api/users/{user_id}` | delete active |
| POST | `/api/users/invite` | create pending + invite token |
| POST | `/api/users/invite/resend` | bulk resend |
| POST | `/api/users/invite/revoke` | revoke pending + delete |
| GET | `/api/auth/invite/{token}` | invite preview |
| POST | `/api/auth/invite/{token}/accept` | set password, activate |

Bootstrap: if zero users, seed `System_Admin` from  
`PLATFORMOPS_BOOTSTRAP_ADMIN_EMAIL` / `PLATFORMOPS_BOOTSTRAP_ADMIN_PASSWORD`  
(defaults: `admin@platformops.local` / `PlatformOps!Admin`).

Auth mode: Bearer `Authorization` header.  
UI requires login. User-management APIs require `System_Admin`.

---

## 4. Log Analyst UI (cPlatform style)

Diagnostics → **Log analyst** tab:
- Header: service context + LLM provider badge (configured / not)
- Chat transcript (bot/operator avatars)
- Evidence cards under last assistant reply
- Error-rate mini chart from `chart_data`
- Suggestion capsules from API (fallback static only if empty response)
- Terminal-style `$` input + Execute
- Loading state while waiting on LLM

---

## 5. Implementation order

1. Settings + compose env + `llm.py`
2. Models + users module + auth routes + bootstrap
3. Upgrade diagnostics chat backend
4. Frontend: login shell, Users page, real Log Analyst
5. Rebuild web dist, restart `platformops-web-api`, smoke

---

## 6. Verification checklist

- [ ] `npm run build` green
- [ ] Login with bootstrap admin
- [ ] Invite user → accept → login
- [ ] List/edit/delete users
- [ ] Log analyst returns LLM answer with real logs context (or clear error if key invalid)
- [ ] No canned “12.5% CPU” path
- [ ] Main nav still clean; Users under Platform; Advanced unchanged

---

## 7. Non-goals (this pass)

- SMTP email send (invite link shown in UI / returned by API — same as offline-safe cPlatform)
- Full Django auth middleware on every ops endpoint (ops APIs remain open unless later hardened)
- Dataflow / Model registry
