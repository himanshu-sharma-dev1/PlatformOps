"""Deterministic diagnostics contracts; no Docker, SSH, or Loki runtime is used."""
from __future__ import annotations

import base64
import gzip
import hashlib
import io
import inspect
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from platformops.db import Base  # noqa: E402
from platformops.models import Cluster, DeploymentJob, Node, ServiceInstance  # noqa: E402
from platformops.orchestrator.diagnostics import impl  # noqa: E402
from platformops.routers import services as services_router  # noqa: E402
from platformops.schemas import (  # noqa: E402
    DiagnosticsFileHistoryOut,
    DiagnosticsLiveOut,
    DiagnosticsBackfillOut,
    LogArchiveDownloadOut,
    LogArchiveOut,
    LogArchiveViewOut,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _service(db: Session, root: Path | None = None) -> ServiceInstance:
    cluster = Cluster(name="diagnostics-test-cluster")
    db.add(cluster)
    db.commit()
    node = Node(cluster_id=cluster.id, name="local", host="localhost", environment="local")
    db.add(node)
    db.commit()
    config = {"log_paths": [str(root)]} if root else {}
    service = ServiceInstance(
        node_id=node.id,
        service_key="redis-core",
        name="Redis Core",
        kind="infrastructure",
        container_name="redis-test",
        status="running",
        config_json=json.dumps(config),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def test_live_tail_preserves_markers_unicode_long_lines_and_cursor(monkeypatch: pytest.MonkeyPatch, db: Session):
    service = _service(db)
    long_marker = "marker-long-" + ("x" * 600)
    output = (
        "2025-01-01T00:00:01.000000000Z marker-normal\n"
        "2025-01-01T00:00:02.000000000Z marker-\u2603-unicode\n"
        f"2025-01-01T00:00:03.000000000Z {long_marker}\n"
    ).encode()
    monkeypatch.setattr("platformops.orchestrator.discovery.resolve_connection_mode", lambda _node: "local")
    monkeypatch.setattr("platformops.orchestrator.docker_runtime.container_logs", lambda *_args, **_kwargs: (output, None))

    first = impl.service_live_logs(db, service, tail_lines=3)
    assert first["error"] is None
    assert [line["message"] for line in first["lines"]] == ["marker-normal", "marker-\u2603-unicode", long_marker]
    assert first["lines"][1]["source"] == "container_stdout"
    second = impl.service_live_logs(db, service, tail_lines=3, cursor=2)
    assert [line["message"] for line in second["lines"]] == [long_marker]
    assert second["next_cursor"] == 3


def test_live_tail_time_range_and_missing_target_are_truthful(monkeypatch: pytest.MonkeyPatch, db: Session):
    service = _service(db)
    output = (
        "2025-01-01T00:00:01Z before\n"
        "2025-01-01T00:00:02Z in-range\n"
        "2025-01-01T00:00:03Z in-range-2\n"
        "2025-01-01T00:00:04Z after\n"
    ).encode()
    monkeypatch.setattr("platformops.orchestrator.discovery.resolve_connection_mode", lambda _node: "local")
    monkeypatch.setattr("platformops.orchestrator.docker_runtime.container_logs", lambda *_args, **_kwargs: (output, None))
    ranged = impl.service_live_logs(
        db,
        service,
        tail_lines=10,
        start="2025-01-01T00:00:02Z",
        end="2025-01-01T00:00:03Z",
    )
    assert [line["message"] for line in ranged["lines"]] == ["in-range", "in-range-2"]
    invalid = impl.service_live_logs(db, service, start="2025-01-01T00:00:04Z", end="2025-01-01T00:00:01Z")
    assert invalid["lines"] == []
    assert "after" in invalid["error"]
    service.node = None
    missing = impl.service_live_logs(db, service)
    assert missing["lines"] == []
    assert "assigned node" in missing["error"]


def test_file_tail_follows_rotation_without_crossing_source(monkeypatch: pytest.MonkeyPatch, db: Session, tmp_path: Path):
    root = tmp_path / "redis-logs"
    root.mkdir()
    rotated = root / "redis.log.1"
    current = root / "redis.log"
    rotated.write_text("old-marker\n", encoding="utf-8")
    current.write_text("current-marker\n", encoding="utf-8")
    service = _service(db, root)
    monkeypatch.setattr("platformops.orchestrator.discovery.resolve_connection_mode", lambda _node: "local")
    first = impl.service_file_tail(db, service, tail_lines=10)
    assert [line["message"] for line in first["lines"]] == ["current-marker"]
    current.rename(root / "redis.log.2")
    new_current = root / "redis.log"
    new_current.write_text("post-rotate-marker\n", encoding="utf-8")
    second = impl.service_file_tail(db, service, tail_lines=10)
    assert [line["message"] for line in second["lines"]] == ["post-rotate-marker"]


def test_file_tail_rejects_traversal_and_remote_never_falls_back_to_host(
    monkeypatch: pytest.MonkeyPatch, db: Session, tmp_path: Path
):
    root = tmp_path / "declared"
    root.mkdir()
    local_shadow = root / "redis.log"
    local_shadow.write_text("must-not-be-read\n", encoding="utf-8")
    service = _service(db, root)
    traversal = impl.service_file_tail(db, service, log_path=str(root / ".." / "outside.log"))
    assert traversal["lines"] == []
    assert "traversal" in traversal["error"].lower() or "configured" in traversal["error"].lower()

    service.node.environment = "remote"
    service.node.host = "remote.example"
    monkeypatch.setattr("platformops.orchestrator.discovery.resolve_connection_mode", lambda _node: "remote")

    class FailedProcess:
        returncode = 1
        stdout = ""
        stderr = "ssh unavailable"

    monkeypatch.setattr(impl.subprocess, "run", lambda *_args, **_kwargs: FailedProcess())
    remote = impl.service_file_tail(db, service, log_path=str(local_shadow))
    assert remote["lines"] == []
    assert "not available" in remote["error"].lower() or "ssh" in remote["error"].lower()


def test_loki_history_has_stable_bidirectional_cursors_and_rejects_mismatch(monkeypatch: pytest.MonkeyPatch, db: Session):
    service = _service(db)
    records = [("100", "marker-1"), ("200", "marker-2"), ("300", "marker-3"), ("400", "marker-4")]

    class Response:
        status_code = 200

        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_get(_url, *, params, **_kwargs):
        if "/query_range" not in _url:
            return Response({"data": {"result": [{"value": ["0", "4"]}]}})
        end = int(params.get("end", "999"))
        start = int(params.get("start", "0"))
        selected = [(ts, msg) for ts, msg in records if start <= int(ts) <= end]
        streams = [{"stream": {"container_name": service.container_name}, "values": selected}]
        return Response({"data": {"result": streams}})

    monkeypatch.setattr(impl.requests, "get", fake_get)
    first = impl.service_container_history(db, service, page_size=2)
    assert [line["message"] for line in first["lines"]] == ["marker-3", "marker-4"]
    assert first["next_cursor"]
    older = impl.service_container_history(db, service, page_size=2, cursor=first["next_cursor"])
    assert [line["message"] for line in older["lines"]] == ["marker-1", "marker-2"]
    assert len({line["message"] for line in first["lines"] + older["lines"]}) == 4
    mismatch = impl.service_container_history(db, service, page_size=3, cursor=first["next_cursor"])
    assert mismatch["lines"] == []
    assert "cursor" in mismatch["error"].lower()


def test_loki_cursor_preserves_distinct_equal_timestamp_lines(monkeypatch: pytest.MonkeyPatch, db: Session):
    service = _service(db)
    records = [("100", f"same-ts-marker-{index}") for index in range(5)]

    class Response:
        status_code = 200

        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_get(url, *, params, **_kwargs):
        if "/query_range" not in url:
            return Response({"data": {"result": [{"value": ["0", "5"]}]}})
        start = int(params.get("start", "0"))
        end = int(params.get("end", "999"))
        values = [(ts, msg) for ts, msg in records if start <= int(ts) <= end]
        return Response({"data": {"result": [{"stream": {}, "values": values}]}})

    monkeypatch.setattr(impl.requests, "get", fake_get)
    seen: list[str] = []
    cursor = ""
    for page in range(1, 4):
        result = impl.service_container_history(db, service, page=page, page_size=2, cursor=cursor)
        seen.extend(line["message"] for line in result["lines"])
        cursor = result.get("next_cursor") or ""
    assert sorted(seen) == sorted(msg for _ts, msg in records)
    assert len(seen) == len(set(seen)) == 5


def test_loki_previous_cursor_uses_forward_direction_and_exact_selector(
    monkeypatch: pytest.MonkeyPatch, db: Session
):
    service = _service(db)
    records = [(str(index * 100), f"marker-{index}") for index in range(1, 5)]
    calls: list[tuple[str, dict[str, str]]] = []

    class Response:
        status_code = 200

        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_get(url, *, params, **_kwargs):
        calls.append((url, dict(params)))
        if "/query_range" not in url:
            return Response({"data": {"result": [{"value": ["0", "4"]}]}})
        start = int(params.get("start", "0"))
        end = int(params.get("end", "999"))
        selected = [(ts, msg) for ts, msg in records if start <= int(ts) <= end]
        return Response({"data": {"result": [{"stream": {}, "values": selected}]}})

    monkeypatch.setattr(impl.requests, "get", fake_get)
    first = impl.service_container_history(db, service, page_size=2)
    assert first["next_cursor"]
    assert calls[1][1]["query"] == '{container_name="redis-test"}'
    older = impl.service_container_history(db, service, page_size=2, cursor=first["next_cursor"])
    assert [line["message"] for line in older["lines"]] == ["marker-1", "marker-2"]
    assert older["previous_cursor"]
    previous = impl.service_container_history(db, service, page_size=2, cursor=older["previous_cursor"])
    assert calls[-1][1]["direction"] == "forward"
    assert [line["message"] for line in previous["lines"]] == ["marker-3", "marker-4"]


def test_file_history_uses_exact_path_source_and_time_range(monkeypatch: pytest.MonkeyPatch, db: Session, tmp_path: Path):
    log_path = tmp_path / "redis.log"
    log_path.write_text("marker-file\n", encoding="utf-8")
    service = _service(db, log_path)
    calls: list[dict[str, str]] = []

    class Response:
        status_code = 200

        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_get(_url, *, params, **_kwargs):
        calls.append(dict(params))
        if "/query_range" not in _url:
            return Response({"data": {"result": [{"value": ["0", "1"]}]}})
        return Response({"data": {"result": [{"stream": {}, "values": [["1735689602000000000", "marker-file"]]}]}})

    monkeypatch.setattr(impl.requests, "get", fake_get)
    result = impl.service_file_history(
        db,
        service,
        start="2025-01-01T00:00:01Z",
        end="2025-01-01T00:00:03Z",
    )
    assert result["source"] == "file_history"
    assert result["lines"][0]["source"] == "file_history"
    assert f'filename="{log_path}"' in calls[1]["query"]
    assert calls[1]["start"] < calls[1]["end"]


def test_file_history_matches_canonical_alloy_filename_label_without_prefix_leakage(
    monkeypatch: pytest.MonkeyPatch, db: Session, tmp_path: Path
):
    """Exercise the acceptance seam: host path -> Alloy filename label -> Loki line."""

    log_path = tmp_path / "parity-redis" / "redis.log"
    log_path.parent.mkdir()
    log_path.write_text("PARITY_REDIS run=integration seq=0001\n", encoding="utf-8")
    service = _service(db, log_path)
    canonical = str(log_path.resolve())
    calls: list[tuple[str, dict[str, str]]] = []

    class Response:
        status_code = 200

        def __init__(self, payload: dict[str, Any]):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_get(url, *, params, **_kwargs):
        calls.append((url, dict(params)))
        assert f'filename="{canonical}"' in params["query"]
        if "/query_range" not in url:
            return Response({"data": {"result": [{"metric": {"filename": canonical}, "value": ["0", "2"]}]}})
        return Response(
            {
                "data": {
                    "result": [
                        {
                            "stream": {
                                "container_name": service.container_name,
                                "filename": canonical,
                            },
                            "values": [
                                ["1735689601000000000", "PARITY_REDIS run=integration seq=0001"],
                                ["1735689602000000000", "PARITY_REDIS run=integration seq=0002"],
                            ],
                        },
                    ]
                }
            }
        )

    monkeypatch.setattr(impl.requests, "get", fake_get)
    result = impl.service_file_history(db, service, log_path=str(log_path), page_size=2)

    assert result["log_path"] == canonical
    assert result["source"] == "file_history"
    assert result["total_count"] == 2
    assert [line["message"] for line in result["lines"]] == [
        "PARITY_REDIS run=integration seq=0001",
        "PARITY_REDIS run=integration seq=0002",
    ]
    assert all(line["source"] == "file_history" for line in result["lines"])
    assert result["next_cursor"]
    assert len(calls) == 2


def test_loki_unavailable_and_empty_history_are_truthful(monkeypatch: pytest.MonkeyPatch, db: Session):
    service = _service(db)

    def fail(*_args, **_kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(impl.requests, "get", fail)
    unavailable = impl.service_container_history(db, service)
    assert unavailable["lines"] == []
    assert unavailable["loki_reachable"] is False
    assert "unavailable" in unavailable["error"].lower()

    class Empty:
        status_code = 200

        def json(self):
            return {"data": {"result": []}}

    monkeypatch.setattr(impl.requests, "get", lambda *_args, **_kwargs: Empty())
    empty = impl.service_container_history(db, service)
    assert empty["lines"] == []
    assert empty["loki_reachable"] is True
    assert empty["error"]


def test_archive_index_checksum_preview_and_valid_bulk_members(db: Session, tmp_path: Path):
    root = tmp_path / "redis-logs"
    root.mkdir()
    content = "marker-normal\nmarker-\u2603-unicode\n" + ("marker-long-" + "x" * 1000) + "\n"
    archive_path = root / "redis-\u2603.log"
    archive_path.write_text(content, encoding="utf-8")
    service = _service(db, root)

    archives = impl.index_log_archives(db, service)
    assert len(archives) == 1
    archive_id = archives[0].id
    assert archives[0].line_count == 3
    assert archives[0].size_bytes == archive_path.stat().st_size
    assert getattr(archives[0], "checksum_sha256", None) == hashlib.sha256(archive_path.read_bytes()).hexdigest()
    again = impl.index_log_archives(db, service)
    assert again[0].id == archive_id

    preview = impl.view_log_archive(db, service, archive_id, max_lines=2)
    assert preview["lines"] == ["marker-normal", "marker-\u2603-unicode"]
    assert preview["truncated"] is True
    download = impl.download_log_archive(db, service, archive_id)
    assert download["ready"] is True
    expected_checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    assert download["checksum_sha256"] == expected_checksum
    assert LogArchiveOut.model_validate(archives[0]).checksum_sha256 == expected_checksum
    response = services_router.diagnostics_archive_download(service.id, archive_id, db)
    assert response.headers["x-checksum-sha256"] == expected_checksum

    result = impl.bulk_download_log_archives(db, service, [archive_id])
    assert result["ready"] is True
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in result["files"]:
            if item["path"]:
                zf.write(item["path"], arcname=item["filename"])
            else:
                zf.writestr(item["filename"], item["content"] or "")
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf:
        assert zf.namelist() == [result["files"][0]["filename"]]
        assert zf.read(zf.namelist()[0]) == archive_path.read_bytes()


def test_remote_busybox_archive_index_uses_portable_listing_and_preserves_gzip_bytes(
    monkeypatch: pytest.MonkeyPatch, db: Session, tmp_path: Path
):
    root = tmp_path / "redis logs"
    root.mkdir()
    plain_name = "redis \u2603.log"
    gzip_name = "redis.log.1.gz"
    plain_bytes = "plain marker\nplain unicode \u2603\n".encode("utf-8")
    gzip_bytes = gzip.compress(b"rotated marker\nrotated marker 2\n")
    service = _service(db, root)
    config = json.loads(service.config_json)
    config["volumes"] = [f"{root}:/var/log/redis"]
    service.config_json = json.dumps(config)
    db.commit()
    calls: list[list[str]] = []
    files = {
        f"/var/log/redis/{plain_name}": plain_bytes,
        f"/var/log/redis/{gzip_name}": gzip_bytes,
    }

    def fake_run(_service, args, **_kwargs):
        calls.append(list(args))
        if args == ["test", "-L", "/var/log/redis"]:
            return False, "", "container command exited with code 1"
        if args == ["test", "-f", "/var/log/redis"]:
            return False, "", "container command exited with code 1"
        if args == ["test", "-d", "/var/log/redis"]:
            return True, "", ""
        if args == ["ls", "-1A", "/var/log/redis"]:
            return True, f"{gzip_name}\n{plain_name}\nappendonly.aof\nescape.log\n", ""
        if args[:2] == ["test", "-f"]:
            return (True, "", "") if args[2] in files or args[2] == "/var/log/redis/escape.log" else (False, "", "container command exited with code 1")
        if args[:2] == ["test", "-L"]:
            return (True, "", "") if args[2] == "/var/log/redis/escape.log" else (False, "", "container command exited with code 1")
        if args[:2] == ["stat", "-c"]:
            return True, f"{len(files[args[3]])}\n", ""
        if args[:1] == ["sha256sum"]:
            return True, f"{hashlib.sha256(files[args[1]]).hexdigest()}  {args[1]}\n", ""
        if args[:2] == ["wc", "-l"]:
            return True, "2\n", ""
        if args[:1] == ["base64"]:
            return True, base64.b64encode(files[args[1]]).decode("ascii"), ""
        raise AssertionError(f"unexpected container command: {args}")

    monkeypatch.setattr(impl, "_run_container_command", fake_run)
    archives = impl.index_log_archives(db, service)

    assert {Path(item.path).name for item in archives} == {gzip_name, plain_name}
    assert all(item.checksum_sha256 for item in archives)
    assert all("appendonly" not in str(item.path) for item in archives)
    assert not any(command and command[0] == "find" for command in calls)
    gzip_archive = next(item for item in archives if Path(item.path).name == gzip_name)
    assert gzip_archive.checksum_sha256 == hashlib.sha256(gzip_bytes).hexdigest()
    download = impl.download_log_archive(db, service, gzip_archive.id)
    assert download["ready"] is True
    assert download["content"] == gzip_bytes
    assert download["checksum_sha256"] == hashlib.sha256(gzip_bytes).hexdigest()

    bundle = impl.bulk_download_log_archives(db, service, [item.id for item in archives])
    assert bundle["ready"] is True
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive_zip:
        for item in bundle["files"]:
            archive_zip.writestr(item["filename"], item["content"])
    with zipfile.ZipFile(io.BytesIO(output.getvalue())) as archive_zip:
        assert archive_zip.read(gzip_name) == gzip_bytes
        plain_member = next(name for name in archive_zip.namelist() if name != gzip_name)
        assert archive_zip.read(plain_member) == plain_bytes


def test_remote_archive_listing_failure_is_not_reported_as_empty(
    monkeypatch: pytest.MonkeyPatch, db: Session, tmp_path: Path
):
    root = tmp_path / "redis-logs"
    root.mkdir()
    service = _service(db, root)
    config = json.loads(service.config_json)
    config["volumes"] = [f"{root}:/var/log/redis"]
    service.config_json = json.dumps(config)
    db.commit()

    def fail_listing(_service, args, **_kwargs):
        if args == ["test", "-L", "/var/log/redis"]:
            return False, "", "container command exited with code 1"
        if args == ["test", "-f", "/var/log/redis"]:
            return False, "", "container command exited with code 1"
        if args == ["test", "-d", "/var/log/redis"]:
            return True, "", ""
        if args == ["ls", "-1A", "/var/log/redis"]:
            return False, "", "BusyBox ls: permission denied"
        raise AssertionError(f"unexpected container command: {args}")

    monkeypatch.setattr(impl, "_run_container_command", fail_listing)
    with pytest.raises(RuntimeError, match="Unable to enumerate declared log directory"):
        impl.index_log_archives(db, service)


def test_diagnostics_http_contracts_are_typed_and_expose_ranges_and_checksums():
    for route_name in ("diagnostics_live", "diagnostics_file_history", "diagnostics_container_history"):
        signature = inspect.signature(getattr(services_router, route_name))
        assert "start" in signature.parameters
        assert "end" in signature.parameters
    assert {"start", "end"}.issubset(DiagnosticsLiveOut.model_fields)
    assert {"start", "end"}.issubset(DiagnosticsFileHistoryOut.model_fields)
    for model in (LogArchiveOut, LogArchiveViewOut, LogArchiveDownloadOut):
        assert "checksum_sha256" in model.model_fields


def test_gzip_archive_checksum_covers_downloaded_bytes_and_symlink_escape_is_rejected(db: Session, tmp_path: Path):
    root = tmp_path / "redis-logs"
    root.mkdir()
    archive_path = root / "redis.log.gz"
    payload = b"marker-gzip\nmarker-gzip-2\n"
    with gzip.open(archive_path, "wb") as stream:
        stream.write(payload)
    service = _service(db, root)
    archives = impl.index_log_archives(db, service)
    assert archives[0].line_count == 2
    expected = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    assert archives[0].checksum_sha256 == expected
    assert impl.download_log_archive(db, service, archives[0].id)["checksum_sha256"] == expected

    outside = tmp_path / "outside.log"
    outside.write_text("do-not-read\n", encoding="utf-8")
    link = root / "escape.log"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")
    from platformops.models import LogArchive

    row = LogArchive(service_id=service.id, path=str(link), size_bytes=outside.stat().st_size, readable="yes")
    db.add(row)
    db.commit()
    result = impl.download_log_archive(db, service, row.id)
    assert result["ready"] is False
    assert "escapes" in result["error"]


def test_archive_rejects_unconfigured_path_and_empty_bulk_selection(db: Session, tmp_path: Path):
    root = tmp_path / "configured"
    root.mkdir()
    outside = tmp_path / "outside.log"
    outside.write_text("secret", encoding="utf-8")
    service = _service(db, root)
    from platformops.models import LogArchive

    row = LogArchive(service_id=service.id, path=str(outside), size_bytes=6, readable="yes")
    db.add(row)
    db.commit()
    assert impl.download_log_archive(db, service, row.id)["ready"] is False
    assert "not allowed" in impl.download_log_archive(db, service, row.id)["error"]
    assert impl.bulk_download_log_archives(db, service, [])["ready"] is False


def test_backfill_unready_job_is_terminal_and_audited(monkeypatch: pytest.MonkeyPatch, db: Session):
    service = _service(db)
    monkeypatch.setattr(
        impl,
        "service_diagnostics",
        lambda *_args, **_kwargs: {"readiness": {"backfill_requirements": {"ready": False, "missing": ["log_paths"]}}},
    )
    result = impl.backfill_service_logs(db, service)
    assert result["ready"] is False
    assert result["job"].status == "failed"
    assert "log_paths" in result["job"].error
    assert db.query(impl.OperationalEvent).filter_by(category="diagnostics").count() >= 1


def test_backfill_route_serializes_safe_job_and_supports_terminal_poll(
    monkeypatch: pytest.MonkeyPatch, db: Session, tmp_path: Path
):
    """Exercise FastAPI response validation for both blocked and completed jobs."""

    service = _service(db, tmp_path / "redis.log")
    api = FastAPI()
    api.include_router(services_router.router)
    api.dependency_overrides[services_router.get_db] = lambda: db
    operation = api.openapi()["paths"][f"/api/services/{{service_id}}/diagnostics/backfill"]["post"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/DiagnosticsBackfillOut"
    )

    monkeypatch.setattr(
        impl,
        "service_diagnostics",
        lambda *_args, **_kwargs: {
            "readiness": {"backfill_requirements": {"ready": False, "missing": ["log_paths"]}}
        },
    )
    with TestClient(api) as client:
        blocked_response = client.post(f"/api/services/{service.id}/diagnostics/backfill")
        assert blocked_response.status_code == 200
        blocked = blocked_response.json()
        DiagnosticsBackfillOut.model_validate(blocked)
        assert blocked["id"] == blocked["job"]["id"]
        assert blocked["status"] == blocked["job"]["status"] == "failed"
        assert blocked["job"]["type"] == "log-backfill"
        assert blocked["job"]["ended_at"] is not None
        assert "log_paths" in blocked["job"]["error"]
        assert "command" not in blocked["job"]

        blocked_poll = client.get(f"/api/jobs/{blocked['id']}")
        assert blocked_poll.status_code == 200
        blocked_poll_payload = blocked_poll.json()
        assert blocked_poll_payload["status"] == "failed"
        assert blocked_poll_payload["command"] == "diagnostics-backfill"
        assert "supersecret" not in blocked_poll_payload["command"]
        blocked_logs = client.get(f"/api/jobs/{blocked['id']}/logs")
        assert blocked_logs.status_code == 200
        assert blocked_logs.json()["command"] == "diagnostics-backfill"
        assert "supersecret" not in blocked_logs.text

        monkeypatch.setattr(
            impl,
            "service_diagnostics",
            lambda *_args, **_kwargs: {
                "readiness": {"backfill_requirements": {"ready": True, "missing": []}}
            },
        )
        monkeypatch.setattr(
            impl,
            "run_job_async",
            lambda session, job, **_kwargs: impl.finish_job(
                session,
                job,
                ok=True,
                output="marker ingested token=supersecret",
                error="password=supersecret",
            ),
        )
        completed_response = client.post(f"/api/services/{service.id}/diagnostics/backfill")
        assert completed_response.status_code == 200
        completed = completed_response.json()
        DiagnosticsBackfillOut.model_validate(completed)
        assert completed["status"] == completed["job"]["status"] == "success"
        assert completed["job"]["output"] == "marker ingested token=[REDACTED]"
        assert completed["job"]["error"] == "password=[REDACTED]"
        assert "supersecret" not in completed["job"]["output"]
        assert "command" not in completed["job"]

        completed_poll = client.get(f"/api/jobs/{completed['id']}")
        assert completed_poll.status_code == 200
        completed_poll_payload = completed_poll.json()
        assert completed_poll_payload["status"] == "success"
        assert completed_poll_payload["command"] == "diagnostics-backfill"
        assert "supersecret" not in completed_poll_payload["output"]
        assert "supersecret" not in completed_poll_payload["error"]
        completed_logs = client.get(f"/api/jobs/{completed['id']}/logs")
        assert completed_logs.status_code == 200
        assert completed_logs.json()["command"] == "diagnostics-backfill"
        assert "supersecret" not in completed_logs.text

        ordinary = DeploymentJob(
            action="deploy",
            command="echo deploy",
            service_id=service.id,
            node_id=service.node_id,
            status="success",
            output="ordinary output",
            error="",
        )
        db.add(ordinary)
        db.commit()
        ordinary_poll = client.get(f"/api/jobs/{ordinary.id}")
        assert ordinary_poll.status_code == 200
        assert ordinary_poll.json()["command"] == "echo deploy"
        assert ordinary_poll.json()["output"] == "ordinary output"
        ordinary_logs = client.get(f"/api/jobs/{ordinary.id}/logs")
        assert ordinary_logs.status_code == 200
        assert ordinary_logs.json()["command"] == "echo deploy"
        assert ordinary_logs.json()["output"] == "ordinary output"

    events = db.query(impl.OperationalEvent).filter_by(category="diagnostics").all()
    assert len(events) == 2
    metadata = [json.loads(event.metadata_json) for event in events]
    assert {item["status"] for item in metadata} == {"failed", "success"}
    assert all(item.get("job_id") for item in metadata)


def test_chat_unconfigured_uses_grounded_legacy_fallback(monkeypatch: pytest.MonkeyPatch, db: Session):
    service = _service(db)
    line = {"timestamp": "2025-01-01T00:00:01Z", "level": "INFO", "message": "marker-normal", "source": "container_stdout"}
    monkeypatch.setattr(impl, "service_diagnostics", lambda *_args, **_kwargs: {"readiness": {}})
    monkeypatch.setattr(impl, "service_diagnostics_analysis", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(impl, "service_live_logs", lambda *_args, **_kwargs: {"lines": [line], "error": None})
    monkeypatch.setattr("platformops.orchestrator.llm.is_llm_configured", lambda: False)
    result = impl.service_log_analytics_chat(db, service, "Analyze marker-normal")
    assert result["success"] is True
    assert "deterministic regex scanning" in result["answer"]
    assert result["evidence"] == [{"t": "00:00:01", "lvl": "INFO", "msg": "marker-normal"}]
    assert len(result["chart_data"]) == 20
    assert result["suggestions"] == [
        "Are there any unusual resource spikes?",
        "Summarise recent warnings",
        "Show events timeline for this service",
    ]
    assert result["provider"] is None
    assert result["_audit_mode"] == "deterministic_fallback"


def test_chat_configured_response_is_strict_and_grounded(monkeypatch: pytest.MonkeyPatch, db: Session):
    service = _service(db)
    line = {"timestamp": "2025-01-01T00:00:01Z", "level": "WARN", "message": "run=canonical marker-warning", "source": "container_stdout"}
    monkeypatch.setattr(impl, "service_diagnostics", lambda *_args, **_kwargs: {"readiness": {}})
    monkeypatch.setattr(impl, "service_diagnostics_analysis", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(impl, "service_live_logs", lambda *_args, **_kwargs: {"lines": [line], "error": None})
    monkeypatch.setattr("platformops.orchestrator.monitoring.impl.query_monitoring_issues", lambda *_args, **_kwargs: {"issues": []})
    monkeypatch.setattr("platformops.orchestrator.llm.is_llm_configured", lambda: True)
    monkeypatch.setattr(
        "platformops.orchestrator.llm.execute_llm_request",
        lambda *_args, **_kwargs: json.dumps({
            "answer": "The canonical warning is present.",
            "evidence": [{"t": "00:00:01", "lvl": "WARN", "msg": "run=canonical marker-warning"}],
            "chart_data": list(range(10)),
            "suggestions": ["Inspect the warning", "Check Redis health", "Review the time window"],
        }),
    )
    result = impl.service_log_analytics_chat(db, service, "Analyze run=canonical")
    assert result["success"] is True
    assert result["provider"] == "mistral"
    assert result["evidence"] == [{"t": "2025-01-01T00:00:01Z", "lvl": "WARN", "msg": "run=canonical marker-warning"}]
    assert result["_audit_mode"] == "configured_provider"


@pytest.mark.parametrize(
    "provider_content",
    [
        None,
        "not-json",
        json.dumps({"answer": "", "evidence": [], "chart_data": list(range(10)), "suggestions": ["a", "b", "c"]}),
        json.dumps({"answer": "cross-service claim", "evidence": [{"t": "00:00:01", "lvl": "ERR", "msg": "other-service-marker"}], "chart_data": list(range(10)), "suggestions": ["a", "b", "c"]}),
    ],
)
def test_chat_provider_failures_use_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch, db: Session, provider_content: str | None,
):
    service = _service(db)
    line = {"timestamp": "2025-01-01T00:00:01Z", "level": "WARN", "message": "run=canonical marker-warning", "source": "container_stdout"}
    monkeypatch.setattr(impl, "service_diagnostics", lambda *_args, **_kwargs: {"readiness": {}})
    monkeypatch.setattr(impl, "service_diagnostics_analysis", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(impl, "service_live_logs", lambda *_args, **_kwargs: {"lines": [line], "error": None})
    monkeypatch.setattr("platformops.orchestrator.monitoring.impl.query_monitoring_issues", lambda *_args, **_kwargs: {"issues": []})
    monkeypatch.setattr("platformops.orchestrator.llm.is_llm_configured", lambda: True)
    monkeypatch.setattr("platformops.orchestrator.llm.execute_llm_request", lambda *_args, **_kwargs: provider_content)
    result = impl.service_log_analytics_chat(db, service, "Analyze run=canonical")
    assert result["success"] is True
    assert result["provider"] is None
    assert result["_audit_mode"] == "deterministic_fallback"
    assert result["evidence"] == [{"t": "00:00:01", "lvl": "WARN", "msg": "run=canonical marker-warning"}]
    assert "other-service-marker" not in json.dumps(result)


def test_chat_rejects_provider_secret_reflection(monkeypatch: pytest.MonkeyPatch, db: Session):
    service = _service(db)
    secret = "synthetic-runtime-secret-marker"
    line = {"timestamp": "2025-01-01T00:00:01Z", "level": "INFO", "message": "run=canonical safe-marker", "source": "container_stdout"}
    monkeypatch.setenv("PLATFORMOPS_MISTRAL_API_KEY", secret)
    monkeypatch.setattr(impl, "service_diagnostics", lambda *_args, **_kwargs: {"readiness": {}})
    monkeypatch.setattr(impl, "service_diagnostics_analysis", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(impl, "service_live_logs", lambda *_args, **_kwargs: {"lines": [line], "error": None})
    monkeypatch.setattr("platformops.orchestrator.monitoring.impl.query_monitoring_issues", lambda *_args, **_kwargs: {"issues": []})
    monkeypatch.setattr(
        "platformops.orchestrator.llm.execute_llm_request",
        lambda *_args, **_kwargs: json.dumps({
            "answer": f"reflected {secret}",
            "evidence": [{"t": "00:00:01", "lvl": "INFO", "msg": "run=canonical safe-marker"}],
            "chart_data": list(range(10)),
            "suggestions": ["a", "b", "c"],
        }),
    )
    result = impl.service_log_analytics_chat(db, service, "Analyze run=canonical")
    assert result["_audit_mode"] == "deterministic_fallback"
    assert secret not in json.dumps(result)
