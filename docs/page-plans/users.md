# Users page — complete cPlatform parity plan

## Mission

Make every cPlatform user and invitation action reachable and verifiable through
PlatformOps UI/API/persistence/session/email behavior. Users shares the golden
Redis run ID and environment but is proved with disposable identities and
Mailpit, not Redis.

## Source authority

- `/PlatformIO/Users/`, `/invite/accept/<uuid:token>/`, login redirect/auth
  helpers.
- `cPlatformIO/views.py:888-923,1929-2005,3028-3059`.
- `UserMgmnt.py`, Users templates/JavaScript, invite templates, and email logic.
- PlatformOps matrix §6; `UsersView.tsx`, `App.tsx`, `authActions.ts`,
  `routers/auth_users.py`, user orchestrator/models.

## Current evidence problems to resolve first

- Matrix says the invitation UI is unreachable because `App.tsx` gates it on a
  nonexistent `renderUsersView` function.
- Current Redis harness can use a token returned directly by the API when
  Mailpit is unavailable; that does not prove email delivery.
- Preview/accept failures are warnings rather than authoritative failures.
- It does not assert token single-use, expiry, revoke/resend invalidation,
  role/status edit, non-admin authorization, session change, user deletion, or
  residue cleanup.
- User/invite IDs are not stored in the canonical manifest for cleanup.
- The current run does not prove browser routing from an emailed link.

## Work package U0 — contract freeze

- [ ] Enumerate login/logout/me, list, add, edit, delete, invite, copy, resend,
  revoke, preview, accept, and all token states.
- [ ] Record exact cPlatform user fields, roles, permissions, defaults,
  validation, uniqueness, status transitions, payloads, and error behavior.
- [ ] Determine password rules and whether activation/deactivation/self-delete/
  last-admin restrictions are legacy behavior or PlatformOps-native.
- [ ] Capture sanitized email subject/body/link fixtures without tokens.

## Work package U1 — authentication and page reachability

- [ ] Prove unauthenticated access redirects/shows login and APIs return 401.
- [ ] Prove valid/invalid login, `/me`, logout, expired/revoked token, and session
  clearing.
- [ ] Make Users reachable for authorized admins and forbidden for non-admins.
- [ ] Replace the nonexistent-renderer gate with explicit invite routing based
  on URL token and preview state.
- [ ] Prove direct emailed link works in a fresh browser session without an
  existing admin token.
- [ ] Test loading, malformed token, network failure, retry, and completed state.

## Work package U2 — active user CRUD

- [ ] List/refresh active and pending users with stable IDs and counts.
- [ ] Create an active user with every legacy field and verify password hashing,
  role/permissions, status, event, and immediate login.
- [ ] Validate duplicate email/name, malformed email/phone, invalid role,
  password rules, missing fields, and unauthorized requests.
- [ ] Edit all fields actually editable in cPlatform, not only role.
- [ ] Prove permission/status changes affect the next API request and refreshed
  session, not merely the displayed row.
- [ ] Delete according to legacy semantics and verify session/token behavior,
  events, and no dangling invite.

## Work package U3 — invitation lifecycle

- [ ] Invite through the UI and require exactly one matching Mailpit message.
- [ ] Parse the token/link from the delivered message; direct API response token
  cannot substitute in authoritative mode.
- [ ] Verify email subject, recipient, link host/port, escaping, and no secret
  leakage beyond the intended one-time link.
- [ ] Preview valid token and display correct invited identity/role.
- [ ] Accept with valid password; persist active user and consumed token once.
- [ ] Login with the accepted credentials and verify correct authorization.
- [ ] Reuse token and require deterministic terminal failure.
- [ ] Resend and require one new message/token; old token must fail.
- [ ] Revoke and require preview/accept failure.
- [ ] Exercise expired, malformed, unknown, already-used, already-revoked, and
  wrong-user token states.
- [ ] Ensure resend/revoke are idempotent or return exact legacy errors.

## Work package U4 — authorization and concurrency

- [ ] Non-admin list/create/edit/delete/invite/resend/revoke all fail without
  side effects or success events.
- [ ] Concurrent acceptance of one token yields exactly one active account.
- [ ] Concurrent duplicate invites follow the legacy uniqueness rule.
- [ ] Role/status changes invalidate or constrain existing sessions as required.
- [ ] Audit payloads contain actor/target/action/outcome but no password/token.

## Authoritative Users harness changes

- Mailpit unavailable, missing message, preview failure, accept failure, or
  login failure must fail the phase—not warn and continue.
- Record operator ID, invitee ID, invite IDs/tokens as redacted hashes, Mailpit
  message IDs, and event IDs in the evidence manifest.
- Drive at least the invitation-link acceptance step through a browser test.
- Add resend/revoke/expiry/single-use/non-admin cases.
- Delete all disposable users/invites/messages where supported and query residue
  by run ID/email afterward.

## Required evidence

Sanitized UI screenshots/traces, API contracts, user/invite rows without hashes,
Mailpit metadata and redacted body, token-state transitions, login/me responses,
authorization denials, operational events, concurrency result, and cleanup
queries. Never store raw passwords, bearer tokens, or full invitation tokens.

## Final Users acceptance

Admin creates user and complete invitation lifecycle; invited user accepts via
the delivered browser link and logs in; admin edits access; non-admin mutations
fail; resend/revoke/expiry/single-use/concurrency behave correctly; cleanup has
no run-labeled user or invite residue.

Users is complete only when every required §6 matrix row is Parity-complete and
Mailpit/browser evidence—not a returned token—proves invitation delivery.
