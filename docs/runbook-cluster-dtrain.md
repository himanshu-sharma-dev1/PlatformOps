# Runbook: Cluster page + dTrain verification (legacy)

> **Legacy cPlatform-coupled runbook:** This document records an older remote
> dTrain verification path. It uses port `9002`, fixed SSH hosts/PEM paths,
> direct host Docker commands, and the `platformops_prod_network` network. It
> is not the current isolated MVP runbook and was not revalidated against the
> isolated DinD stack. Those commands can reach or mutate the legacy
> deployment; do not run them for isolated MVP testing.
>
> Current operators should use [the isolated MVP handoff](mvp-status.md),
> PlatformOps on port `9004`, optional Mailpit on `9010`, and its verified local
> Cluster → Node → Redis workflow. dTrain/cloud/remote-node verification is a
> remaining parity task, not a current MVP acceptance result.

**Legacy network:** `platformops_prod_network` (do **not** join
`cplatform_iktara_cPlatform`; this network is still not the isolated DinD
network.)<br>
**Legacy login/UI:** `admin` / `admin` → `http://localhost:9002` (**legacy
only; unsafe for isolated MVP**)<br>
**Legacy SSH node:** `ubuntu@65.2.63.24` or `ubuntu@172.31.4.83` (**remote
host; not isolated DinD**)<br>
**Legacy PEM (do not commit):** `/home/ubuntu/NODE1001.pem`<br>
**Legacy alternate PEM:** `/iktara/cPlatform/cPlatform/temp_pem/NODE1001.pem`
(same key; do not use for isolated MVP)

---

## 1. Preflight

```bash
# LEGACY ONLY — direct SSH to the historical remote verification host.
ssh -i /home/ubuntu/NODE1001.pem -o StrictHostKeyChecking=no ubuntu@172.31.4.83 'hostname'

# LEGACY ONLY — checks the host Docker engine, not isolated DinD.
docker images | grep -i dtrain

# LEGACY ONLY — checks the old host network, not the isolated project network.
docker network ls | grep platformops_prod
```

---

## 2. Cluster + node (UI or API)

1. Login → **Clusters** → **Create Cluster** (e.g. `ops-cluster-verify`).
2. **Provision node**:
   - Host: `65.2.63.24` (or `172.31.4.83`)
   - User: `ubuntu`
   - Key path: `/home/ubuntu/NODE1001.pem` **or** paste PEM
   - Docker network: `platformops_prod_network`
   - Facts: vCPU / memory / storage / GPU as desired
3. Expect **AIOrchestrator** auto-registered (`SERV####`, status `registered`).
4. Click **Validate** (real SSH/docker checks).
5. Click **Discover** — adopts high-confidence catalog matches only (noise + duplicate keys skipped). **Legacy remote path.**
6. Open **Add service** → pick **dtrain-controller** (or Discover may already have adopted `node-1-dtrain-controller`).

---

## 3. dTrain path

### A. Prefer discover/adopt if container already running

```bash
# LEGACY ONLY — direct host Docker inspection of the remote/legacy target.
docker ps --format '{{.Names}}\t{{.Image}}' | grep -i dtrain
```

If `node-1-dtrain-controller` (or similar) is up, **Discover** should adopt it with a `SERV####` id and live status **running**.

### B. Catalog ANSIBLE deploy

1. Catalog → **DTrain Controller** (or `dtrain-controller`).
2. dForm fields load from `catalog/dform/dFormService.json` (TrainingServer schema).
3. Set **ServiceInstall** = `ANSIBLE`.
4. Continue into **Deployment control** → run preflight → deploy.
5. Image tags available on this host: `iktaraai/services:dTrain-*`, `platformops/dtrain-controller:local`.

### C. MANUAL register

Set **ServiceInstall** = `MANUAL` → register only (no fake deploy success). Live status may be `not_found` until a real container exists.

---

## 4. Live status

On cluster detail with a node selected, UI polls `GET /api/nodes/{id}/live-status` every 5s.

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:9002/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin","password":"admin"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s "http://127.0.0.1:9002/api/nodes/12/live-status" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -60
```

Statuses come from **docker inspect** only — never invent healthy.

---

## 5. Lifecycle safety

| Action | Expected |
|--------|----------|
| Delete AIOrchestrator while other services exist | Blocked |
| Delete node with services | Blocked (force only with policy) |
| Delete empty cluster | OK |

---

## 6. Exit criteria checklist

- [ ] Create cluster works
- [ ] Add node with PEM works
- [ ] Spec sheet shows facts
- [ ] AIOrchestrator bootstrap present
- [ ] Discover reports scanned/adopted/skipped/unmatched
- [ ] SERV IDs on services
- [ ] Live status poll paints running/exited/not_found honestly
- [ ] dForm install schema for dtrain + AIOrchestrator
- [ ] dTrain container adopted or deploy attempted with real job output

---

*Historical note: this path was last recorded against host 65.2.63.24 / the
legacy PlatformOps API :9002. It is not a current isolated-MVP verification
record.*
