#!/usr/bin/env python3
"""Core BE checks for cluster (real imports, no reimplementation)."""
from __future__ import annotations

import json
import os
import pathlib
import sys

SCRATCH = pathlib.Path(os.environ.get("SCRATCH", "/tmp/grok-goal-d145cade8fa9/implementer"))
SCRATCH.mkdir(parents=True, exist_ok=True)
LOG = SCRATCH / "cluster-core-be.log"
lines: list[str] = []
fail = 0

API = pathlib.Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API))


def log(m: str) -> None:
    lines.append(m)
    print(m, flush=True)


def main() -> int:
    global fail
    from platformops.orchestrator.discovery import normalize_docker_ports, load_discovery_policy
    from platformops.catalog import required_dependencies
    from platformops.orchestrator.config import validate_config
    from platformops.schemas import ServiceOut

    cases = [
        ("0.0.0.0:9006->8000/tcp", ["9006:8000"]),
        ("8102:8080", ["8102:8080"]),
    ]
    for raw, expected in cases:
        got = normalize_docker_ports(raw)
        ok = got == expected
        log(f"normalize_docker_ports({raw!r}) -> {got} expected {expected} {'OK' if ok else 'FAIL'}")
        if not ok:
            fail += 1

    policy = load_discovery_policy()
    ok = policy.get("prefer_node_network") is False
    log(f"discovery prefer_node_network=false: {policy.get('prefer_node_network')} {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1

    deps = required_dependencies("dtrain-controller")
    ok = set(["rabbitmq-core", "redis-core", "dtrain-tracker"]).issubset(set(deps))
    log(f"dtrain deps {deps} {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1

    v = validate_config("a:\n  b: 1\n")
    ok = v.get("ok") is True
    log(f"validate_config ok={v} {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1

    class Fake:
        id = 9
        external_id = "SERV1009"
        node_id = 1
        service_key = "x"
        name = "X"
        kind = "app"
        container_name = "c"
        image = "i"
        status = "running"
        config_json = json.dumps({"expose_service": True, "host_port": 8080, "adopted": True})

    out = ServiceOut.model_validate(Fake())
    ok = out.expose_service and out.host_port == 8080 and out.adopted
    log(f"ServiceOut contract flags expose={out.expose_service} port={out.host_port} adopted={out.adopted} {'OK' if ok else 'FAIL'}")
    if not ok:
        fail += 1

    LOG.write_text("\n".join(lines) + f"\n\nfail_count={fail}\n", encoding="utf-8")
    log(f"wrote {LOG} fail_count={fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
