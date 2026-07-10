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
- When implementing features, match the exact behavior described in `docs/features/*.md`.
- Do not add features beyond what cPlatform provides.
- Do not remove or simplify features that cPlatform provides.
- Every new backend endpoint must have a corresponding Pydantic schema in `schemas.py`.
- Every mutating endpoint must call `record_event()` for audit logging.

## Testing Discipline
- After any backend change, run `make check` to verify compilation.
- After any frontend change, run `cd apps/web && npm run build` to verify zero errors.
- Run `scripts/run_e2e_tests.py` to validate functional integrity before committing.

## Code Organization
- New orchestrator logic goes in the appropriate module under `apps/api/platformops/orchestrator/`.
- Export new public functions via `orchestrator/__init__.py`.
- Import in `main.py` via `from .orchestrator import <function_name>`.
- Frontend render functions follow the pattern `renderXxxView()` or `renderXxxWorkspace()` in `main.tsx`.
