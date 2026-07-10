# Runbook: Cluster page + dTrain verification

**Network:** `platformops_prod_network` (do **not** join `cplatform_iktara_cPlatform`)  
**Login:** `admin` / `admin` → UI at `http://localhost:9002`  
**SSH node (this host):** `ubuntu@65.2.63.24` or `ubuntu@172.31.4.83`  
**PEM (do not commit):** `/home/ubuntu/NODE1001.pem`  
**Also available:** `/iktara/cPlatform/cPlatform/temp_pem/NODE1001.pem` (same key)

---

## 1. Preflight

```bash
# SSH works
ssh -i /home/ubuntu/NODE1001.pem -o StrictHostKeyChecking=no ubuntu@172.31.4.83 'hostname'

# Images present
docker images | grep -i dtrain

# Network exists
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
5. Click **Discover** — adopts high-confidence catalog matches only (noise + duplicate keys skipped).
6. Open **Add service** → pick **dtrain-controller** (or Discover may already have adopted `node-1-dtrain-controller`).

---

## 3. dTrain path

### A. Prefer discover/adopt if container already running

```bash
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

*Last verified against host 65.2.63.24 / PlatformOps API :9002.*
