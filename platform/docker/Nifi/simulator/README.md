# HTTP alarm row simulator

This is an isolated source container for the additive `noc-alarm-http-to-agenticnoc-v1` flow. It has no cPlatform, Kafka, Docker socket, or AgenticNOC library dependency.

The wire format is intentionally compatible with the supplied row-rate script:

```text
POST http://nifi:9080/aviat
Content-Type: text/csv
X-Original-Filename: CURRENT_ALARM_REPORT.csv
X-Row-Number: 1

Event,Object,Site,Raised,Severity,State,Cleared,Event ID
Ethernet port link down,L1LA1,UEMWBSNA01,2026-08-14T10:00:00Z,Major,Active,,1603
```

Every request contains one header and exactly one data row. The first two
lines of a source file are treated as the Aviat report preamble. Files whose
name does not contain `alarm` are ignored, matching the supplied script.

## Container controls

The service binds lifecycle controls on port 8080:

```bash
curl -X POST http://localhost:8080/start
curl -X POST http://localhost:8080/pause
curl -X POST http://localhost:8080/resume
curl -X POST http://localhost:8080/stop
curl http://localhost:8080/status
curl http://localhost:8080/metrics
```

StreamFlow configures a cycle before starting it. The operation is safe to
repeat while stopped and applies the next replay's source, rate, destination,
and lineage metadata:

```bash
curl -X POST http://localhost:8080/configure \
  -H 'Content-Type: application/json' \
  -d '{"cycle_id":"alarm-cycle-000001","stream_id":"noc-alarm-demo", \
       "rate":100,"continuous":false,"input_dir":"/data/incoming", \
       "archive_dir":"/data/sent","target_url":"http://nifi:9080/aviat"}'
```

These are the canonical cPlatform contract paths.  `/api/*` and `/api/v1/*`
aliases are retained for older callers, and `POST /delete` is the terminal
cleanup alias used by stream deletion.

`SIMULATOR_CONTINUOUS=true` keeps polling and replaying files. Set
`SIMULATOR_MOVE_AFTER_SEND=true` (or pass `--move-after-send`) to archive each
file under `SIMULATOR_ARCHIVE_DIR` after all of its rows are accepted. The
default is to retain files for continuous replay. `--rate` is rows per second,
and `--host`, `--port`, and `--path` have the same meaning as the supplied
row-rate script's NiFi destination arguments.

The mapped JSON contract is
[`noc_alarm_mapped_v1.schema.json`](../contracts/noc_alarm_mapped_v1.schema.json).
`contract.py` is a dependency-free fixture mapper/validator; production
canonicalization remains in the NiFi flow and final alarm policy remains in
AgenticNOC.

Each row POST carries `X-Original-Filename`, `X-Row-Number`, `X-Stream-ID`,
`X-Replay-Cycle-ID`, `X-Replay-Sequence`, and `X-Source-System` when configured,
so stream and cycle-scoped source lineage survives the HTTP hop.
