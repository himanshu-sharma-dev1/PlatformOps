#!/usr/bin/env python3
"""Live cluster-page API smoke against a running PlatformOps API.

Drives real HTTP endpoints used by the Clusters FE. Writes a transcript to
SCRATCH or stdout. Exit 0 only if all gating checks pass.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("PLATFORMOPS_BASE", "http://127.0.0.1:9020").rstrip("/")
LIVE_PLATFORMOPS_PORT = 9002
ISOLATED_PLATFORMOPS_PORT = 9020
ALLOW_NON_ISOLATED = "PLATFORMOPS_CLUSTER_SMOKE_ALLOW_NON_ISOLATED"
SCRATCH = pathlib.Path(os.environ.get("SCRATCH", "/tmp/grok-goal-d145cade8fa9/implementer"))
SCRATCH.mkdir(parents=True, exist_ok=True)
LOG = SCRATCH / "cluster-api-smoke.log"
lines: list[str] = []
failures: list[str] = []


def validate_target() -> None:
    """Reject the live cPlatform-coupled endpoint before any HTTP request."""

    parsed = urllib.parse.urlparse(BASE)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit(
            "Unsafe cluster smoke target: PLATFORMOPS_BASE must be an http(s) URL "
            "such as http://127.0.0.1:9020."
        )
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise SystemExit(f"Unsafe cluster smoke target: invalid port in {BASE!r}.") from exc
    if port == LIVE_PLATFORMOPS_PORT:
        raise SystemExit(
            "Refusing cluster smoke against port 9002 (the live cPlatform stack). "
            "Use the isolated target at http://127.0.0.1:9020."
        )
    if port != ISOLATED_PLATFORMOPS_PORT and os.environ.get(ALLOW_NON_ISOLATED, "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        raise SystemExit(
            f"Refusing non-isolated cluster smoke target {BASE!r}. Expected port 9020; "
            f"set {ALLOW_NON_ISOLATED}=1 only for an explicitly reviewed environment."
        )


def log(msg: str) -> None:
    lines.append(msg)
    print(msg, flush=True)


def api(path: str, method: str = "GET", body=None, token: str | None = None, timeout: int = 180):
    public_paths = {"/api/auth/login", "/api/health"}
    if (path.startswith("/api/") or path.startswith("/PlatformIO/")) and path not in public_paths and not token:
        return 401, {"error": "cluster smoke refused an unauthenticated protected request"}
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, {"raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else {"error": str(e)}
        except json.JSONDecodeError:
            return e.code, {"raw": raw, "error": str(e)}
    except urllib.error.URLError as exc:
        return 0, {"error": f"request failed: {exc.reason}"}
    except TimeoutError as exc:
        return 0, {"error": f"request timed out: {exc}"}


def must(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)
        log(f"FAIL: {msg}")
    else:
        log(f"OK: {msg}")


def main() -> int:
    validate_target()
    log(f"BASE={BASE}")
    code, login = api("/api/auth/login", "POST", {"email": "admin", "password": "admin"})
    token = login.get("token") if isinstance(login, dict) else None
    must(code == 200 and isinstance(token, str) and bool(token.strip()), f"login status={code}")
    if not token:
        LOG.write_text("\n".join(lines) + "\nFAILURES:\n" + "\n".join(failures), encoding="utf-8")
        return 1

    code, clusters = api("/api/clusters", token=token)
    must(code == 200 and isinstance(clusters, list) and len(clusters) > 0, f"list clusters {code} n={len(clusters) if isinstance(clusters, list) else '?'}")

    # test-repo / test-registry (may fail connect but endpoint must respond)
    code, tr = api(
        "/api/clusters/test-repo",
        "POST",
        {"repo_type": "github", "repo_url": "https://github.com/octocat/Hello-World", "repo_branch": "master", "repo_token": None},
        token=token,
    )
    # 200 connected; 400 honest git/tls failure still proves body binding works (not 422 schema miss)
    must(code in (200, 400) and code != 422, f"test-repo body-bound status={code} body={str(tr)[:160]}")
    code, treg = api(
        "/api/clusters/test-registry",
        "POST",
        {"registry_type": "dockerhub", "registry_url": "https://registry-1.docker.io", "registry_user": None, "registry_password": None},
        token=token,
    )
    must(code in (200, 400) and code != 422, f"test-registry body-bound status={code} body={str(treg)[:160]}")

    code, nodes = api("/api/nodes", token=token)
    must(code == 200 and isinstance(nodes, list) and len(nodes) > 0, f"list nodes {code}")
    node = next((n for n in nodes if n.get("id") == 12), nodes[0])
    nid = node["id"]
    log(f"using node id={nid} name={node.get('name')}")

    code, conn = api(f"/api/nodes/{nid}/connection", token=token)
    must(code == 200 and "live_probe" in (conn or {}), f"connection/probe {code}")

    code, disc = api(f"/api/nodes/{nid}/discover", "POST", token=token)
    must(code == 200 and ("summary" in disc or "containers_scanned" in disc), f"discover {code} {str(disc)[:160]}")

    code, live = api(f"/api/nodes/{nid}/live-status", token=token)
    must(code == 200 and "items" in live, f"node live-status {code} running={live.get('running_count')}")

    code, svcs = api("/api/services", token=token)
    must(code == 200 and isinstance(svcs, list), f"list services {code}")
    dtrain = next((s for s in svcs if s.get("id") == 85 or s.get("service_key") == "dtrain-controller"), None)
    must(dtrain is not None, "dtrain service present")
    if dtrain:
        must(bool(dtrain.get("external_id")), f"SERV id present {dtrain.get('external_id')}")
        # expose flags on ServiceOut
        must("expose_service" in dtrain, "ServiceOut includes expose_service")
        sid = dtrain["id"]
        code, slive = api(f"/api/services/{sid}/live-status", token=token)
        must(code == 200 and slive.get("overall_status"), f"service live {code} {slive.get('overall_status')}")

        code, ws = api(f"/api/services/{sid}/config?source=live", token=token)
        must(code == 200 and ws.get("config_capabilities", {}).get("apply_enabled") is True, f"config workspace apply_enabled {code}")
        content = ws.get("content") or ""
        marker = f"# platformops_apply_test: {int(time.time())}"
        content = re.sub(r"# platformops_apply_test:.*\n?", "", content)
        content = content.rstrip() + "\n" + marker + "\n"
        code, apply_res = api(
            f"/api/services/{sid}/config/direct-apply",
            "POST",
            {"content": content, "apply_mode": "restart"},
            token=token,
        )
        job = (apply_res or {}).get("job") or apply_res
        must(code == 200 and (job or {}).get("status") == "success", f"direct-apply job={job.get('status') if isinstance(job, dict) else job} code={code}")
        time.sleep(1.5)
        host_path = pathlib.Path(str(ws.get("config_path") or "/tmp/platformops/dtrain/controller/config/dtrain_config.yaml"))
        host_ok = host_path.exists() and marker in host_path.read_text(encoding="utf-8", errors="ignore")
        # Refresh service for current container_name (deploy may rename)
        _, svcs2 = api("/api/services", token=token)
        cur = next((s for s in (svcs2 or []) if s.get("id") == sid), dtrain)
        cname = (cur or {}).get("container_name") or dtrain.get("container_name") or "node-1-dtrain-controller"
        ctr = subprocess.getoutput(f"docker exec {cname} cat /app/config/dtrain_config.yaml 2>/dev/null")
        if marker not in ctr:
            # try sibling names used by adopt/deploy
            for alt in ("node-1-dtrain-controller", "node-12-dtrain-controller"):
                ctr_alt = subprocess.getoutput(f"docker exec {alt} cat /app/config/dtrain_config.yaml 2>/dev/null")
                if marker in ctr_alt:
                    ctr = ctr_alt
                    cname = alt
                    break
        ctr_ok = marker in ctr
        log(f"config check host={host_path} host_ok={host_ok} container={cname} ctr_ok={ctr_ok} job_out={(job or {}).get('output','')[:160]}")
        must(host_ok or ctr_ok, f"config landed host={host_ok} container={ctr_ok}")

        code, pre = api(f"/api/services/{sid}/preflight", "POST", token=token)
        must(code == 200 and "ok" in pre, f"preflight {code} ok={pre.get('ok')}")

        if pre.get("ok"):
            code, djob = api(f"/api/services/{sid}/deploy", "POST", token=token)
            must(code == 200 and djob.get("id"), f"deploy started {code}")
            if djob.get("id"):
                jid = djob["id"]
                final = None
                for _ in range(40):
                    _, j = api(f"/api/jobs/{jid}", token=token)
                    final = j
                    if j.get("status") in ("success", "failed", "error"):
                        break
                    time.sleep(2)
                must(final and final.get("status") == "success", f"deploy terminal status={final.get('status') if final else None}")

        code, patch = api(
            "/PlatformIO/Monitoring/PatchObservability/",
            "POST",
            {"service_id": sid},
            token=token,
            timeout=180,
        )
        # Honest callable: 200 with success bool true/false is OK; must not 500
        must(code == 200 and isinstance(patch, dict) and "success" in patch, f"patch endpoint {code} keys={list(patch)[:8] if isinstance(patch, dict) else type(patch)}")
        log(f"patch result success={patch.get('success')} error={patch.get('error')}")

    orch = next((s for s in svcs if str(s.get("service_key", "")).lower() in ("ai-orchestrator", "cplatform")), None)
    if orch:
        code, delr = api(f"/api/services/{orch['id']}/delete", "POST", token=token)
        must(code in (409, 400), f"AIOrchestrator delete blocked status={code} detail={str(delr)[:200]}")
    else:
        log("SKIP: no AIOrchestrator service to test delete guard")

    code, ev = api(f"/api/events?node_id={nid}&limit=5", token=token)
    must(code == 200 and isinstance(ev, list), f"node events {code}")

    code, jobs = api(f"/api/nodes/{nid}/jobs", token=token)
    must(code == 200, f"node jobs {code}")

    LOG.write_text("\n".join(lines) + "\n\nFAILURES:\n" + ("\n".join(failures) if failures else "(none)") + "\n", encoding="utf-8")
    log(f"wrote {LOG}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
