"""Runtime control for the small cPlatform/NiFi NOC alarm demo.

The regular cPlatform stream integrations are service-backed and keep their
existing lifecycle.  The NOC demo is intentionally different: its contract
points at the shared NiFi/Kafka stack and owns one NiFi process group.  This
module keeps that special case small and explicit while exposing a stable
runtime snapshot for the UI.

    The checked-in replay simulator and NiFi process group are controlled as one
    logical stream.  The simulator is an optional isolated HTTP runtime (the
    source rows are still delivered by NiFi), so cPlatform does not register or
    deploy a second user-facing service.  Kafka, PostgreSQL, and Prometheus
    observations are read from the AgenticNOC runtime endpoint when it is
    available; a missing observer is reported as ``unavailable`` instead of being
    replaced with synthetic numbers.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import requests
from django.utils import timezone

from cPlatform.AppLogging import app_logger

from .demo_control_plane import (
    AGENTICNOC_INGEST_PATH,
    CONTROL_ACTIONS,
    HTTP_BASE_PATH,
    HTTP_FLOW_NAME,
    HTTP_LISTEN_PORT,
    LEGACY_FLOW_NAME,
    SIMULATOR_KIND,
    UI_DEMO_FLOW_FILE,
    UI_DEMO_FLOW_NAME,
    build_stream_contract,
    new_cycle_id,
)


DEFAULT_NIFI_URL = "http://180.75.0.10:8883"
DEFAULT_AGENTICNOC_URL = "http://180.75.0.7:8000"
DEFAULT_PROMETHEUS_URL = "http://180.75.0.13:9090"
DEFAULT_KAFKA_BOOTSTRAP = "180.75.0.31:9092"
# The HTTP path is the canonical new StreamFlow.  The legacy FTP/local Kafka
# flow remains addressable for existing process groups and dataflows.
NIFI_FLOW_NAME = HTTP_FLOW_NAME
NIFI_LEGACY_FLOW_NAME = LEGACY_FLOW_NAME
NIFI_HTTP_INGEST_PATH = f"/{HTTP_BASE_PATH}"
RUNTIME_KEY = "control_plane_runtime"
STALE_UI_DEMO_PROCESSORS = {
    "Attach replay headers",
    "ExecuteStreamCommand",
    "Limit replay rate",
    "Merge deduped records to CSV",
    "Publish raw alarm JSON",
    "Set output CSV filename",
    "Split into raw alarm rows",
    "Strip two Aviat CSV preamble lines",
    "Write deduped CSV",
}
STALE_UI_DEMO_CONTROLLER_SERVICES = {
    "NOC CSV Record Writer",
    "NOC JSON Tree Reader",
    "NOC Kafka Connection",
}


def _normalize_simulator_url(value: Any) -> str:
    value = str(value or "").strip().rstrip("/")
    for suffix in ("/api/v1/status", "/api/status", "/status"):
        if value.endswith(suffix):
            return value[: -len(suffix)].rstrip("/")
    return value


class NocRuntimeError(RuntimeError):
    """An expected runtime-control or observability failure."""


class NocSimulatorClient:
    """Stateful adapter for the cPlatform replay simulator contract.

    When ``NOC_SIMULATOR_URL`` (or ``SIMULATOR_URL``) is configured, actions
    are forwarded to the isolated HTTP simulator's lifecycle endpoints.  The
    fallback remains an in-process contract so cPlatform can register and
    inspect a stream before that optional runtime is provisioned.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        lifecycle: Mapping[str, Any] | None = None,
        timeout: float = 8.0,
    ) -> None:
        self.base_url = _normalize_simulator_url(
            base_url
            or os.environ.get("NOC_SIMULATOR_URL")
            or os.environ.get("NOC_SIMULATOR_BASE_URL")
            or os.environ.get("SIMULATOR_URL")
            or ""
        )
        self.lifecycle = dict(lifecycle or {})
        self.timeout = timeout

    def _path(self, action: str) -> str:
        value = str(self.lifecycle.get(action) or f"/{action}").strip()
        if value.startswith(("http://", "https://")):
            parsed = urlparse(value)
            value = parsed.path or "/"
        return value if value.startswith("/") else f"/{value}"

    def configure(self, contract: Mapping[str, Any], cycle_id: str) -> dict[str, Any]:
        simulator = contract.get("simulator") if isinstance(contract.get("simulator"), Mapping) else {}
        replay = contract.get("replay") if isinstance(contract.get("replay"), Mapping) else {}
        source = contract.get("source") if isinstance(contract.get("source"), Mapping) else {}
        nifi = contract.get("nifi") if isinstance(contract.get("nifi"), Mapping) else {}
        stream_id = str(contract.get("stream_id") or "noc-alarm-stream")
        vendor = str(contract.get("vendor") or simulator.get("vendor") or "aviat").strip().lower()
        continuous = bool(simulator.get("continuous", replay.get("continuous", True)))
        events_per_second = int(
            simulator.get("events_per_second") or replay.get("events_per_second") or 100
        )
        source_type = str(simulator.get("source_type") or source.get("type") or "local_path")
        target_url = str(
            simulator.get("target_url")
            or os.environ.get("SIMULATOR_NIFI_URL")
            or os.environ.get("NOC_SIMULATOR_NIFI_URL")
            or f"http://180.75.0.10:{int(nifi.get('listen_port') or HTTP_LISTEN_PORT)}/{str(nifi.get('base_path') or HTTP_BASE_PATH).strip('/')}"
        )
        payload = {
            "cycle_id": cycle_id,
            "stream_id": stream_id,
            "vendor": vendor,
            "rate": events_per_second,
            "continuous": continuous,
            "input_dir": str(simulator.get("input_dir") or source.get("path") or "/data/incoming"),
            "archive_dir": str(simulator.get("archive_dir") or "/data/sent"),
            "target_url": target_url,
            "source_system": str(simulator.get("source_system") or "cplatform-http-simulator"),
            "file_pattern": str(source.get("file_pattern") or simulator.get("file_pattern") or "*.csv"),
        }
        result: dict[str, Any] = {
            "kind": str(simulator.get("kind") or SIMULATOR_KIND),
            "controller": str(simulator.get("controller") or "cplatform"),
            "state": "configured",
            "available": bool(self.base_url),
            "cycle_id": cycle_id,
            "stream_id": stream_id,
            "source_type": source_type,
            "events_per_second": events_per_second,
            "mode": str(simulator.get("mode") or replay.get("mode") or "continuous"),
            "continuous": continuous,
            "input_dir": payload["input_dir"],
            "archive_dir": payload["archive_dir"],
            "target_url": target_url,
        }
        if self.base_url:
            result.update(_request_json(self.base_url, "POST", self._path("configure"), payload, timeout=self.timeout))
            result["configured"] = True
            result["cycle_id"] = cycle_id
            result["events_per_second"] = events_per_second
            result["continuous"] = continuous
        return result

    def set_state(
        self,
        state: str,
        *,
        cycle_id: str | None = None,
        action: str | None = None,
    ) -> dict[str, Any]:
        if state not in {"running", "paused", "stopped", "failed"}:
            raise NocRuntimeError(f"unsupported simulator state: {state}")
        action = action or {
            "running": "start",
            "paused": "pause",
            "stopped": "stop",
        }.get(state)
        if action not in {"start", "pause", "resume", "stop"}:
            raise NocRuntimeError(f"unsupported simulator action: {action}")
        result: dict[str, Any] = {
            "kind": SIMULATOR_KIND,
            "controller": "cplatform",
            "state": state,
            "cycle_id": cycle_id,
            "available": bool(self.base_url),
        }
        if self.base_url and state != "failed":
            result.update(_request_json(self.base_url, "POST", self._path(action), timeout=self.timeout))
            result["state"] = str(result.get("state") or state)
            result["available"] = True
        return result

    def status(self) -> dict[str, Any]:
        """Read the simulator's authoritative lifecycle state, if deployed.

        A one-shot replay can finish naturally after cPlatform has started it;
        in that case the persisted control-plane state remains ``running``
        unless the UI asks the simulator.  Keeping this probe read-only lets
        the runtime drawer show the actual source state without changing the
        existing NiFi/controller lifecycle semantics.
        """

        result: dict[str, Any] = {
            "kind": SIMULATOR_KIND,
            "controller": "cplatform",
            "available": bool(self.base_url),
        }
        if not self.base_url:
            return result
        result.update(_request_json(self.base_url, "GET", self._path("status"), timeout=self.timeout))
        result["available"] = True
        return result

    def delete(self) -> dict[str, Any]:
        result = {"kind": SIMULATOR_KIND, "controller": "cplatform", "state": "deleted", "available": bool(self.base_url)}
        if self.base_url:
            result.update(_request_json(self.base_url, "POST", self._path("delete"), timeout=self.timeout))
            result["state"] = "deleted"
            result["available"] = True
        return result


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise NocRuntimeError("runtime service returned invalid JSON") from exc
    return payload if isinstance(payload, dict) else {"value": payload}


def _request_json(
    base_url: str,
    method: str,
    path: str,
    payload: Mapping[str, Any] | None = None,
    *,
    timeout: float = 8.0,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    try:
        response = requests.request(method, url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise NocRuntimeError(f"request to {url} failed: {exc}") from exc
    if response.status_code >= 400:
        detail = response.text[:500].strip()
        raise NocRuntimeError(f"request to {url} failed ({response.status_code}): {detail}")
    return _safe_json(response) if response.content else {}


def _load_bootstrap_module() -> Any:
    """Load the checked-in NiFi bootstrap helpers without a package import.

    ``platform`` is also a Python standard-library module, so importing the
    script by path avoids an ambiguous package name in the Django process.
    """

    path = Path(__file__).resolve().parents[3] / "platform/docker/Nifi/scripts/bootstrap_noc_alarm_flow.py"
    spec = importlib.util.spec_from_file_location("noc_nifi_bootstrap", path)
    if spec is None or spec.loader is None:
        raise NocRuntimeError(f"NiFi bootstrap script not found at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _nifi_flow_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "platform/docker/Nifi/flows"


def _contract_flow_file(contract: Mapping[str, Any]) -> str:
    nifi = contract.get("nifi") if isinstance(contract.get("nifi"), Mapping) else {}
    return str(nifi.get("flow_file") or os.environ.get("NOC_NIFI_FLOW_FILE") or UI_DEMO_FLOW_FILE).strip()


def _load_http_flow_manifest(contract: Mapping[str, Any], cycle_id: str) -> dict[str, Any]:
    nifi = contract.get("nifi") if isinstance(contract.get("nifi"), Mapping) else {}
    flow_file = _contract_flow_file(contract)
    manifest_path = _nifi_flow_dir() / flow_file if flow_file else _nifi_flow_dir() / "noc_alarm_http_to_agenticnoc_v1.flow.json"
    if not manifest_path.is_file():
        manifest_path = _nifi_flow_dir() / "noc_alarm_http_to_agenticnoc_v1.flow.json"
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NocRuntimeError(f"HTTP NiFi flow manifest is unavailable at {manifest_path}") from exc
    if isinstance(raw.get("flowContents"), Mapping):
        return _convert_nifi_export_to_manifest(
            raw,
            str(nifi.get("flow_name") or raw.get("flowContents", {}).get("name") or UI_DEMO_FLOW_NAME),
            cycle_id,
        )
    return raw


def _convert_nifi_export_to_manifest(exported: Mapping[str, Any], flow_name: str, cycle_id: str) -> dict[str, Any]:
    contents = exported.get("flowContents") if isinstance(exported.get("flowContents"), Mapping) else exported
    skipped_processor_ids = {
        str(processor.get("identifier") or processor.get("id") or processor.get("instanceIdentifier") or "")
        for processor in contents.get("processors", [])
        if processor.get("name") in STALE_UI_DEMO_PROCESSORS
    }
    connected_ids: set[str] = set()
    connections: list[dict[str, Any]] = []
    for connection in contents.get("connections", []):
        source = connection.get("source") or {}
        destination = connection.get("destination") or {}
        source_id = str(source.get("id") or source.get("identifier") or "")
        destination_id = str(destination.get("id") or destination.get("identifier") or "")
        if not source_id or not destination_id:
            continue
        if source_id in skipped_processor_ids or destination_id in skipped_processor_ids:
            continue
        connected_ids.update({source_id, destination_id})
        connections.append({
            "source": source_id,
            "destination": destination_id,
            "relationships": connection.get("selectedRelationships") or ["success"],
        })

    controller_services: list[dict[str, Any]] = []
    for service in contents.get("controllerServices", []):
        service_id = str(service.get("identifier") or service.get("id") or service.get("instanceIdentifier") or "")
        if not service_id:
            continue
        if service.get("name") in STALE_UI_DEMO_CONTROLLER_SERVICES:
            continue
        controller_services.append({
            "id": service_id,
            "type": service.get("type"),
            "name": service.get("name"),
            "properties": service.get("properties") or {},
        })

    processors: list[dict[str, Any]] = []
    for processor in contents.get("processors", []):
        processor_id = str(processor.get("identifier") or processor.get("id") or processor.get("instanceIdentifier") or "")
        if not processor_id:
            continue
        if processor_id in skipped_processor_ids:
            continue
        properties = dict(processor.get("properties") or {})
        if processor_id not in connected_ids and processor.get("type") == "org.apache.nifi.processors.standard.ExecuteStreamCommand":
            continue
        if processor.get("type") == "NormalizeAlarm":
            properties["Replay Cycle ID"] = cycle_id
        if processor.get("type") == "org.apache.nifi.amqp.processors.PublishAMQP":
            properties["Host Name"] = os.environ.get("NOC_AMQP_HOST", "180.75.0.2")
            properties.setdefault("Username", os.environ.get("NOC_AMQP_USERNAME", "guest"))
            properties.setdefault("Password", os.environ.get("NOC_AMQP_PASSWORD", properties.get("Username") or "guest"))
        processors.append({
            "id": processor_id,
            "type": processor.get("type"),
            "name": processor.get("name"),
            "position": processor.get("position") or {"x": 0, "y": 0},
            "properties": properties,
            "auto_terminated_relationships": processor.get("autoTerminatedRelationships") or [],
        })

    return {
        "flow_name": flow_name,
        "flow_version": str(exported.get("flowEncodingVersion") or "1"),
        "parameters": {},
        "controller_services": controller_services,
        "processors": processors,
        "connections": connections,
    }


def runtime_for(dataflow: Any) -> dict[str, Any]:
    """Return a mutable, migration-free runtime record for a dataflow."""

    conn_info = dict(dataflow.conn_info or {})
    runtime = conn_info.get(RUNTIME_KEY)
    if not isinstance(runtime, dict):
        runtime = {}
    runtime = dict(runtime)
    runtime.setdefault("state", "registered")
    runtime.setdefault("cycle_number", 0)
    runtime.setdefault("run_id", None)
    runtime.setdefault("cycle_id", None)
    runtime.setdefault("group_id", None)
    runtime.setdefault("last_error", None)
    runtime.setdefault("rebuild_required", False)
    runtime.setdefault("simulator_state", "registered")
    runtime.setdefault("simulator", {})
    runtime.setdefault("updated_at", None)
    return runtime


def save_runtime(dataflow: Any, runtime: Mapping[str, Any], *, status: str | None = None) -> None:
    conn_info = dict(dataflow.conn_info or {})
    value = dict(runtime)
    value["updated_at"] = timezone.now().isoformat()
    conn_info[RUNTIME_KEY] = value
    dataflow.conn_info = conn_info
    if status:
        dataflow.dataflow_status = status
    dataflow.save(update_fields=["conn_info", "dataflow_status"])


def _parameter_values(contract: Mapping[str, Any], cycle_id: str) -> dict[str, str]:
    source = contract.get("source") if isinstance(contract.get("source"), Mapping) else {}
    replay = contract.get("replay") if isinstance(contract.get("replay"), Mapping) else {}
    kafka = contract.get("kafka") if isinstance(contract.get("kafka"), Mapping) else {}
    source_type = str(source.get("type") or "local_path")
    input_mode = "ftp" if source_type == "ftp" else "local"
    # NiFi's local processor runs inside the NiFi container.  The UI should
    # therefore use the mounted path (/opt/nifi/data/incoming), not a host path.
    path = str(source.get("path") or "/opt/nifi/data/incoming")
    file_pattern = str(source.get("file_pattern") or ".*\\.csv")
    # Accept the form's simple '*.csv' value as well as a regular expression.
    if "*" in file_pattern and not file_pattern.startswith(".*"):
        file_pattern = re.escape(file_pattern).replace(r"\*", ".*")
    values = {
        "Input Mode": input_mode,
        "Cycle ID": cycle_id,
        "Local Input Directory": path,
        "FTP Host": str(source.get("host") or ""),
        "FTP Port": str(source.get("port") or 21),
        "FTP Username": str(source.get("username") or ""),
        "FTP Password": str(source.get("password") or ""),
        "FTP Remote Path": str(source.get("remote_path") or "/"),
        "File Pattern": file_pattern,
        "Kafka Bootstrap Servers": str(kafka.get("bootstrap_servers") or DEFAULT_KAFKA_BOOTSTRAP),
        "Stream ID": str(contract.get("stream_id") or "noc-alarm-stream"),
        "Events Per Second": str(replay.get("events_per_second") or 100),
        "Continuous Replay": "true" if replay.get("continuous", True) else "false",
        "Replay Mode": str(replay.get("mode") or ("continuous" if replay.get("continuous", True) else "one_shot")),
        # Both modes consume each matching file once.  Continuous keeps the
        # process group running so later files copied into the mounted folder
        # are picked up; it does not silently duplicate the same file under a
        # fixed cycle ID.
        "Keep Source File": "false",
    }
    return values


def _is_http_flow(contract: Mapping[str, Any]) -> bool:
    nifi = contract.get("nifi") if isinstance(contract.get("nifi"), Mapping) else {}
    return str(nifi.get("transport") or "").strip().lower() == "http" or str(
        nifi.get("flow_name") or ""
    ).strip() == HTTP_FLOW_NAME


def _load_mapped_avro_schema() -> str:
    for base in [Path(__file__).resolve().parents[i] for i in range(len(Path(__file__).resolve().parents))]:
        target = base / "platform/docker/Nifi/contracts/noc_alarm_mapped_v1.avsc"
        if target.is_file():
            try:
                return target.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    return json.dumps({
        "type": "record",
        "name": "NocAlarmMapped",
        "namespace": "ai.iktara.noc.alarm",
        "doc": "cPlatform mapped alarm record v1 for NiFi ValidateRecord processor",
        "fields": [
            {"name": "schema_version", "type": "int", "default": 1},
            {"name": "contract", "type": "string", "default": "noc-alarm-mapped.v1"},
            {"name": "vendor", "type": "string", "default": "aviat"},
            {"name": "source_system", "type": ["null", "string"], "default": None},
            {"name": "source_file", "type": ["null", "string"], "default": None},
            {"name": "source_row", "type": ["null", "int"], "default": 1},
            {"name": "event_id", "type": "string"},
            {"name": "alarm_key", "type": "string"},
            {"name": "external_alarm_id", "type": ["null", "string"], "default": None},
            {"name": "event_description", "type": ["null", "string"], "default": None},
            {"name": "object", "type": ["null", "string"], "default": None},
            {"name": "site_id", "type": ["null", "string"], "default": None},
            {"name": "node_id", "type": ["null", "string"], "default": None},
            {"name": "severity", "type": "string", "default": "indeterminate"},
            {"name": "state", "type": "string", "default": "active"},
            {"name": "event_type", "type": "string", "default": "raise"},
            {"name": "canonical_category", "type": ["null", "string"], "default": "UNKNOWN"},
            {"name": "probable_cause_raw", "type": ["null", "string"], "default": None},
            {"name": "specific_problem", "type": ["null", "string"], "default": None},
            {"name": "source_event_time", "type": ["null", "string"], "default": None},
            {"name": "effective_event_time", "type": ["null", "string"], "default": None},
            {"name": "device_raised_at", "type": ["null", "string"], "default": None},
            {"name": "device_cleared_at", "type": ["null", "string"], "default": None},
            {"name": "nms_cleared_at", "type": ["null", "string"], "default": None},
            {"name": "ingested_at", "type": "string"},
            {"name": "trace_id", "type": ["null", "string"], "default": None},
            {"name": "stream_id", "type": ["null", "string"], "default": None},
            {"name": "replay_cycle_id", "type": ["null", "string"], "default": None},
            {"name": "replay_sequence", "type": ["null", "int"], "default": None},
            {"name": "Circle", "type": ["null", "string"], "default": None},
            {"name": "Cleared", "type": ["null", "string"], "default": None},
            {"name": "SpecificProblem", "type": ["null", "string"], "default": None},
            {"name": "ProbableCause", "type": ["null", "string"], "default": None},
            {"name": "AlarmID", "type": ["null", "string"], "default": None},
            {"name": "Site", "type": ["null", "string"], "default": None},
            {"name": "Severity", "type": ["null", "string"], "default": None},
            {"name": "State", "type": ["null", "string"], "default": None},
            {"name": "AlarmName", "type": ["null", "string"], "default": None},
            {"name": "Raised", "type": ["null", "string"], "default": None}
        ]
    })


def _http_parameter_values(contract: Mapping[str, Any], cycle_id: str) -> dict[str, str]:
    nifi = contract.get("nifi") if isinstance(contract.get("nifi"), Mapping) else {}
    replay = contract.get("replay") if isinstance(contract.get("replay"), Mapping) else {}
    return {
        "ListenHTTP Port": str(nifi.get("listen_port") or HTTP_LISTEN_PORT),
        "ListenHTTP Base Path": str(nifi.get("base_path") or HTTP_BASE_PATH).strip("/"),
        "AgenticNOC Ingest URL": str(
            nifi.get("agenticnoc_ingest_url")
            or os.environ.get("AGENTICNOC_INGEST_URL")
            or f"http://180.75.0.7:8000{AGENTICNOC_INGEST_PATH}"
        ),
        "Mapped Alarm Schema": (
            str(nifi.get("mapped_alarm_schema"))
            if nifi.get("mapped_alarm_schema") and str(nifi.get("mapped_alarm_schema")).strip().startswith("{")
            else _load_mapped_avro_schema()
        ),
        "DLQ Directory": str(
            nifi.get("dlq_directory") or "/opt/nifi/nifi-current/logs/noc-dlq"
        ),
        # Resolve the duplicate-cache parameters before creating controller
        # services.  The lightweight bootstrap deliberately does not create a
        # NiFi Parameter Context for a single UI-owned stream.
        "Duplicate Cache Server Host": str(
            nifi.get("duplicate_cache_server_host") or "127.0.0.1"
        ),
        "Duplicate Cache Server Port": str(
            nifi.get("duplicate_cache_server_port") or 4557
        ),
        "Source System": str(
            nifi.get("source_system") or "cplatform-http-simulator"
        ),
        "Vendor": str(contract.get("vendor") or nifi.get("vendor") or "aviat").strip().lower(),
        "Duplicate Cache Service": "noc-http-duplicate-cache",
        "Cycle ID": cycle_id,
        "Stream ID": str(contract.get("stream_id") or "noc-alarm-stream"),
        "Events Per Second": str(replay.get("events_per_second") or 100),
    }


class NocNiFiClient:
    """Small NiFi 2.x REST client for the checked-in NOC flow."""

    def __init__(self, base_url: str | None = None, *, timeout: float = 12.0) -> None:
        self.base_url = (
            base_url
            or os.environ.get("NOC_NIFI_URL")
            or os.environ.get("NIFI_URL")
            or DEFAULT_NIFI_URL
        ).rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return _request_json(self.base_url, method, path, payload, timeout=self.timeout)

    def find_group(self, flow_name: str = NIFI_FLOW_NAME) -> str | None:
        result = self.request("GET", "/nifi-api/flow/process-groups/root")
        flow = result.get("processGroupFlow", {}).get("flow", {})
        for group in flow.get("processGroups", []):
            component = group.get("component", group)
            if component.get("name") == flow_name:
                return str(group.get("id") or component.get("id"))
        return None

    def group(self, group_id: str) -> dict[str, Any]:
        return self.request("GET", f"/nifi-api/flow/process-groups/{group_id}")

    @staticmethod
    def flow_from_group(response: Mapping[str, Any]) -> dict[str, Any]:
        return dict(response.get("processGroupFlow", {}).get("flow", {}))

    def ensure_group(self, flow_name: str = NIFI_FLOW_NAME) -> str:
        group_id = self.find_group(flow_name)
        if group_id:
            return group_id
        created = self.request(
            "POST",
            "/nifi-api/process-groups/root/process-groups",
            {"revision": {"version": 0}, "component": {"name": flow_name, "position": {"x": 0, "y": 0}}},
        )
        group_id = created.get("id") or created.get("component", {}).get("id")
        if not group_id:
            raise NocRuntimeError("NiFi did not return a process-group id")
        return str(group_id)

    def _bootstrap_empty_group(self, group_id: str, contract: Mapping[str, Any], cycle_id: str) -> None:
        bootstrap = _load_bootstrap_module()
        if _is_http_flow(contract):
            manifest = _load_http_flow_manifest(contract, cycle_id)
            values = _http_parameter_values(contract, cycle_id)
            service_ids = bootstrap._create_controller_services(
                self.base_url, group_id, manifest, values
            )
            processor_ids = bootstrap._create_processors(
                self.base_url, group_id, manifest, service_ids, values, "local"
            )
            bootstrap._create_connections(self.base_url, group_id, manifest, processor_ids)
            bootstrap._validate_group(self.base_url, group_id)
            return

        manifest = bootstrap.load_manifest(bootstrap.DEFAULT_MANIFEST)
        values = _parameter_values(contract, cycle_id)
        service_ids = bootstrap._create_controller_services(self.base_url, group_id, manifest, values)
        processor_ids = bootstrap._create_processors(
            self.base_url,
            group_id,
            manifest,
            service_ids,
            values,
            values["Input Mode"],
        )
        bootstrap._create_connections(self.base_url, group_id, manifest, processor_ids)
        bootstrap._validate_group(self.base_url, group_id)

    def _update_controller_service(self, group_id: str, service_name: str, properties: Mapping[str, Any]) -> None:
        bootstrap = _load_bootstrap_module()
        for service in bootstrap._controller_services(self.base_url, group_id):
            component = service.get("component") or {}
            if component.get("name") != service_name:
                continue
            service_id = str(service.get("id") or component.get("id"))
            current = self.request("GET", f"/nifi-api/controller-services/{service_id}")
            revision = current.get("revision") or service.get("revision") or {"version": 0}
            current_component = dict(current.get("component") or component)
            config = dict(current_component.get("properties") or {})
            needs_update = any(config.get(k) != v for k, v in properties.items())
            if not needs_update:
                return
            if current_component.get("state") != "DISABLED":
                try:
                    self.request(
                        "PUT",
                        f"/nifi-api/controller-services/{service_id}/run-status",
                        {"revision": revision, "state": "DISABLED"},
                    )
                    time.sleep(0.5)
                    current = self.request("GET", f"/nifi-api/controller-services/{service_id}")
                    revision = current.get("revision") or revision
                    current_component = dict(current.get("component") or current_component)
                except Exception:
                    pass
            config.update(properties)
            self.request(
                "PUT",
                f"/nifi-api/controller-services/{service_id}",
                {
                    "revision": revision,
                    "component": {
                        "id": service_id,
                        "properties": config,
                    },
                },
            )
            current = self.request("GET", f"/nifi-api/controller-services/{service_id}")
            self.request(
                "PUT",
                f"/nifi-api/controller-services/{service_id}/run-status",
                {"revision": current.get("revision") or {"version": 0}, "state": "ENABLED"},
            )
            return

    def _update_processor(
        self,
        processor: Mapping[str, Any],
        properties: Mapping[str, Any],
        *,
        remove_properties: tuple[str, ...] = (),
    ) -> None:
        component = dict(processor.get("component") or {})
        config = dict(component.get("config") or {})
        existing_props = dict(config.get("properties") or {})
        needs_update = any(existing_props.get(k) != v for k, v in properties.items()) or any(
            key in existing_props for key in remove_properties
        )
        if not needs_update:
            return

        processor_id = str(processor.get("id") or component.get("id"))
        run_status = str(component.get("state") or "").upper()
        rev = processor.get("revision") or {"version": 0}

        if run_status == "RUNNING":
            try:
                stop_res = self.request("PUT", f"/nifi-api/processors/{processor_id}/run-status", {"revision": rev, "state": "STOPPED"})
                rev = stop_res.get("revision") or rev
                time.sleep(0.5)
            except Exception:
                pass

        merged = dict(existing_props)
        for key in remove_properties:
            merged.pop(key, None)
        merged.update(properties)
        config["properties"] = merged
        payload = {
            "revision": rev,
            "component": {"id": processor_id, "config": config},
        }
        res = self.request("PUT", f"/nifi-api/processors/{processor_id}", payload)
        rev = res.get("revision") or rev

        if run_status == "RUNNING":
            try:
                self.request("PUT", f"/nifi-api/processors/{processor_id}/run-status", {"revision": rev, "state": "RUNNING"})
            except Exception:
                pass

    def configure(self, group_id: str, contract: Mapping[str, Any], cycle_id: str) -> dict[str, Any]:
        if _is_http_flow(contract):
            values = _http_parameter_values(contract, cycle_id)
            flow_name = str((contract.get("nifi") or {}).get("flow_name") or HTTP_FLOW_NAME)
            response = self.group(group_id)
            flow = self.flow_from_group(response)
            processors = flow.get("processors", [])
            if not processors:
                self._bootstrap_empty_group(group_id, contract, cycle_id)
                response = self.group(group_id)
                flow = self.flow_from_group(response)
                processors = flow.get("processors", [])
            names = {str(p.get("component", {}).get("name", "")): p for p in processors}
            ingress_name = next((name for name in ("ListenHTTP /aviat row ingress", "ListenHTTP") if name in names), "")
            post_name = next((name for name in ("POST canonical alarm to AgenticNOC",) if name in names), "")
            publish_name = next((name for name in ("Publish raw alarm JSON",) if name in names), "")
            stale_names = sorted(set(names) & STALE_UI_DEMO_PROCESSORS)
            if not ingress_name or stale_names:
                # A previous failed/manual import can leave a same-named group
                # with unrelated components. This stream owns the group, so
                # rebuild it from the configured flow file once instead of
                # leaving the user stuck with a stale NiFi canvas.
                existing_names = ", ".join(sorted(name for name in names if name)) or "none"
                app_logger.warning(
                    "NiFi flow %s requires rebuild; group %s has stale processors [%s]. Existing processors: %s",
                    flow_name,
                    group_id,
                    ", ".join(stale_names) or "none",
                    existing_names,
                )
                self.delete_group(group_id)
                group_id = self.ensure_group(flow_name)
                self._bootstrap_empty_group(group_id, contract, cycle_id)
                response = self.group(group_id)
                flow = self.flow_from_group(response)
                processors = flow.get("processors", [])
                names = {str(p.get("component", {}).get("name", "")): p for p in processors}
                ingress_name = next((name for name in ("ListenHTTP /aviat row ingress", "ListenHTTP") if name in names), "")
                post_name = next((name for name in ("POST canonical alarm to AgenticNOC",) if name in names), "")
                publish_name = next((name for name in ("Publish raw alarm JSON",) if name in names), "")
                if not ingress_name:
                    rebuilt_names = ", ".join(sorted(name for name in names if name)) or "none"
                    raise NocRuntimeError(
                        f"NiFi HTTP flow is missing its ListenHTTP processor after rebuild. Processors: {rebuilt_names}"
                    )
            self._update_processor(
                names[ingress_name],
                {
                    "Listening Port": values["ListenHTTP Port"],
                    "Base Path": values["ListenHTTP Base Path"],
                },
            )
            validate_name = "Validate mapped alarm contract"
            if validate_name in names:
                self._update_processor(
                    names[validate_name],
                    {
                        "Schema Text": values["Mapped Alarm Schema"],
                    },
                )
            # Scope NiFi's duplicate cache by stream, replay cycle, and source
            # row.  The distributed cache is shared by the HTTP flow and a
            # replay can contain vendor rows whose optional fields are blank
            # or whose semantic identity is not stable until AgenticNOC's
            # canonical normalizer sees it.  The source file/row pair is a
            # deterministic delivery identity: a retried row in the same
            # cycle is suppressed, while distinct rows are never collapsed by
            # a malformed vendor payload.  AgenticNOC remains the authority
            # for semantic event_id/alarm_key idempotency.
            extract_name = "Extract duplicate identity attributes"
            if extract_name in names:
                self._update_processor(
                    names[extract_name],
                    {"stream_id": "$[0].stream_id"},
                )
            duplicate_name = "Route duplicate alarm rows"
            if duplicate_name in names:
                self._update_processor(
                    names[duplicate_name],
                    {
                        "Cache Entry Identifier": (
                            "${stream_id}:${replay_cycle_id}:${source_file}:"
                            "${source_row}"
                        ),
                    },
                )
            if post_name:
                self._update_processor(
                    names[post_name],
                    {
                        "HTTP URL": values["AgenticNOC Ingest URL"],
                        "X-AgenticNOC-Vendor": values["Vendor"],
                    },
                    # NiFi 2.x treats the removed NiFi 1.x retry-property name as
                    # an HTTP header.  Explicitly remove it from an already
                    # bootstrapped group; simply omitting it from the manifest is
                    # insufficient because configure() preserves existing props.
                    remove_properties=("Response Retry Attribute Name",),
                )
            if publish_name:
                kafka = contract.get("kafka") if isinstance(contract.get("kafka"), Mapping) else {}
                self._update_processor(
                    names[publish_name],
                    {
                        "Topic Name": str(kafka.get("raw_topic") or kafka.get("topic") or "noc.alarm.raw.v1"),
                    },
                )
                self._update_controller_service(
                    group_id,
                    "NOC Kafka Connection",
                    {"bootstrap.servers": str(kafka.get("bootstrap_servers") or DEFAULT_KAFKA_BOOTSTRAP)},
                )
            if "Limit replay rate" in names:
                self._update_processor(names["Limit replay rate"], {"Maximum Rate": values["Events Per Second"]})
            if "Attach replay headers" in names:
                self._update_processor(
                    names["Attach replay headers"],
                    {
                        "stream_id": str(contract.get("stream_id") or "noc-alarm-stream"),
                        "cycle_id": values["Cycle ID"],
                        "replay_eps": values["Events Per Second"],
                        "continuous_replay": "true",
                        "replay_mode": "continuous",
                    },
                )
            if "NormalizeAlarm" in names:
                self._update_processor(names["NormalizeAlarm"], {"Replay Cycle ID": values["Cycle ID"]})
            if "PublishAMQP" in names:
                amqp_username = os.environ.get("NOC_AMQP_USERNAME", "guest")
                self._update_processor(
                    names["PublishAMQP"],
                    {
                        "Host Name": os.environ.get("NOC_AMQP_HOST", "180.75.0.2"),
                        "Username": amqp_username,
                        "Password": os.environ.get("NOC_AMQP_PASSWORD", amqp_username),
                    },
                )
            return {
                "group_id": group_id,
                "flow_name": flow_name,
                "transport": "http",
                "listen_port": int(values["ListenHTTP Port"]),
                "base_path": values["ListenHTTP Base Path"],
                "agenticnoc_ingest_url": values["AgenticNOC Ingest URL"],
            }

        values = _parameter_values(contract, cycle_id)
        response = self.group(group_id)
        flow = self.flow_from_group(response)
        processors = flow.get("processors", [])
        if not processors:
            self._bootstrap_empty_group(group_id, contract, cycle_id)
            response = self.group(group_id)
            flow = self.flow_from_group(response)
            processors = flow.get("processors", [])

        source_type = values["Input Mode"]
        names = {str(p.get("component", {}).get("name", "")): p for p in processors}
        source_name = "Read FTP alarm files" if source_type == "ftp" else "Read local alarm files"
        # A source-mode edit cannot safely reuse the other processor.  The
        # control endpoint marks this condition for a rebuild instead of
        # silently starting a flow that reads the wrong source.
        expected_source = "Read FTP alarm files" if source_type == "ftp" else "Read local alarm files"
        if expected_source not in names:
            raise NocRuntimeError("NiFi flow source mode differs; delete and recreate the stream to rebuild it")

        source = contract.get("source") if isinstance(contract.get("source"), Mapping) else {}
        file_pattern = values["File Pattern"]
        source_props: dict[str, Any]
        if source_type == "ftp":
            source_props = {
                "Hostname": values["FTP Host"],
                "Port": values["FTP Port"],
                "Username": values["FTP Username"],
                "Password": values["FTP Password"],
                "Remote Path": values["FTP Remote Path"],
                "File Filter Regex": file_pattern,
            }
        else:
            source_props = {"Input Directory": values["Local Input Directory"], "File Filter": file_pattern}
        if source_name in names:
            self._update_processor(names[source_name], source_props)
        if "Limit replay rate" in names:
            self._update_processor(names["Limit replay rate"], {"Maximum Rate": values["Events Per Second"]})
        if "Attach replay headers" in names:
            self._update_processor(
                names["Attach replay headers"],
                {
                    "stream_id": values["Stream ID"],
                    "cycle_id": values["Cycle ID"],
                    "replay_eps": values["Events Per Second"],
                    "continuous_replay": values["Continuous Replay"],
                    "replay_mode": values["Replay Mode"],
                },
            )
        return {
            "group_id": group_id,
            "flow_name": str((contract.get("nifi") or {}).get("flow_name") or NIFI_LEGACY_FLOW_NAME),
            "transport": "kafka",
            "source": source_type,
            "source_path": source.get("path") if source_type != "ftp" else source.get("remote_path"),
            "events_per_second": int(values["Events Per Second"]),
        }

    def _processor_ids(self, group_id: str) -> list[tuple[str, str, Mapping[str, Any]]]:
        try:
            flow = self.flow_from_group(self.group(group_id))
        except Exception:
            return []
        result: list[tuple[str, str, Mapping[str, Any]]] = []
        for processor in flow.get("processors", []):
            component = processor.get("component", {})
            processor_id = processor.get("id") or component.get("id")
            if processor_id:
                result.append((str(processor_id), str(component.get("name") or processor_id), processor))
        return result

    def set_state(self, group_id: str, state: str) -> dict[str, Any]:
        if state not in {"RUNNING", "STOPPED"}:
            raise ValueError("NiFi processor state must be RUNNING or STOPPED")
        try:
            self.request("PUT", f"/nifi-api/flow/process-groups/{group_id}", {"id": group_id, "state": state})
        except Exception:
            pass
        results = []
        for processor_id, name, processor in self._processor_ids(group_id):
            try:
                current = self.request("GET", f"/nifi-api/processors/{processor_id}")
                revision = current.get("revision") or processor.get("revision") or {"version": 0}
                result = self.request(
                    "PUT",
                    f"/nifi-api/processors/{processor_id}/run-status",
                    {"revision": revision, "state": state},
                )
                results.append({"id": processor_id, "name": name, "state": state, "response": result.get("request", result)})
            except Exception:
                pass
        return {"state": state, "processors": results}

    def delete_group(self, group_id: str) -> None:
        # NiFi refuses to delete a process group while one of its controller
        # services is enabled.  Reuse the checked-in bootstrap cleanup helper
        # so processor queues and record-reader/writer services are disabled
        # in the same order for both the CLI and UI lifecycle paths.
        try:
            bootstrap = _load_bootstrap_module()
            bootstrap._delete_group(self.base_url, group_id)
        except Exception as exc:  # noqa: BLE001 - translate bootstrap errors to API shape
            if isinstance(exc, NocRuntimeError):
                raise
            raise NocRuntimeError(str(exc)) from exc

    def snapshot(self, group_id: str | None) -> dict[str, Any]:
        if not group_id:
            return {"available": False, "state": "not-created", "message": "NiFi flow has not been created"}
        response = self.group(group_id)
        flow = self.flow_from_group(response)
        process_group_flow = response.get("processGroupFlow", {})
        breadcrumb = process_group_flow.get("breadcrumb", {}) if isinstance(process_group_flow, Mapping) else {}
        nested_breadcrumb = breadcrumb.get("breadcrumb", {}) if isinstance(breadcrumb, Mapping) else {}
        flow_name = str(nested_breadcrumb.get("name") or NIFI_FLOW_NAME)
        states = []
        for processor in flow.get("processors", []):
            component = processor.get("component", {})
            status = processor.get("status", {})
            states.append(
                {
                    "id": processor.get("id") or component.get("id"),
                    "name": component.get("name"),
                    "state": status.get("runStatus") or component.get("state") or "UNKNOWN",
                    "validation": component.get("validationStatus"),
                    "validation_errors": component.get("validationErrors") or [],
                }
            )
        queued = 0
        connections = []
        for connection in flow.get("connections", []):
            status = connection.get("status", {})
            size = status.get("aggregateSnapshot", {}).get("flowFilesQueued")
            try:
                size_int = int(size or 0)
            except (TypeError, ValueError):
                size_int = 0
            queued += size_int
            connections.append(
                {
                    "id": connection.get("id"),
                    "source": connection.get("source", {}).get("name"),
                    "destination": connection.get("destination", {}).get("name"),
                    "queued": size_int,
                }
            )
        return {
            "available": True,
            "group_id": group_id,
            "flow_name": flow_name,
            "processors": states,
            "connections": connections,
            "queued_flowfiles": queued,
        }


def _clean_source(contract: Mapping[str, Any]) -> dict[str, Any]:
    source = contract.get("source") if isinstance(contract.get("source"), Mapping) else {}
    return {
        "type": source.get("type"),
        "path": source.get("path"),
        "remote_path": source.get("remote_path"),
        "file_pattern": source.get("file_pattern"),
        "host": source.get("host"),
        "port": source.get("port"),
        "username": source.get("username"),
    }


def _remote_runtime(dataflow_id: str, cycle_id: str | None, group_id: str | None = None) -> dict[str, Any]:
    base = (os.environ.get("AGENTICNOC_RUNTIME_URL") or "").strip()
    if not base:
        base_url = os.environ.get("AGENTICNOC_BASE_URL", DEFAULT_AGENTICNOC_URL).rstrip("/")
        base = base_url + "/api/stream/runtime/"
    try:
        response = requests.get(
            base,
            params={
                "dataflow_id": dataflow_id,
                "cycle_id": cycle_id or "",
                "nifi_group_id": group_id or "",
            },
            timeout=float(os.environ.get("NOC_RUNTIME_TIMEOUT", "5")),
        )
        if response.status_code >= 400:
            return {"available": False, "error": f"AgenticNOC returned {response.status_code}"}
        return _safe_json(response)
    except requests.RequestException as exc:
        return {"available": False, "error": str(exc)}


def snapshot_for(dataflow: Any, *, include_remote: bool = True) -> dict[str, Any]:
    runtime = runtime_for(dataflow)
    contract = (dataflow.conn_info or {}).get("control_plane_contract") or {}
    if not contract:
        return {
            "success": False,
            "available": False,
            "dataflow_id": dataflow.dataflow_id,
            "message": "stream is not a NOC control-plane contract",
        }
    nifi = {"available": False, "message": "not queried"}
    try:
        nifi = NocNiFiClient().snapshot(runtime.get("group_id"))
    except NocRuntimeError as exc:
        nifi = {"available": False, "error": str(exc)}
    remote = _remote_runtime(str(dataflow.dataflow_id), runtime.get("cycle_id"), runtime.get("group_id")) if include_remote else {"available": False}
    simulator_contract = contract.get("simulator") if isinstance(contract.get("simulator"), Mapping) else {}
    replay_contract = contract.get("replay") if isinstance(contract.get("replay"), Mapping) else {}
    simulator = dict(runtime.get("simulator") or {})
    simulator.update({
        "available": bool(simulator.get("available", False)),
        "kind": str(simulator_contract.get("kind") or SIMULATOR_KIND),
        "controller": str(simulator_contract.get("controller") or "cplatform"),
        "state": str(runtime.get("simulator_state") or runtime.get("state") or "registered"),
        "cycle_id": runtime.get("cycle_id"),
        "source_type": simulator_contract.get("source_type") or (contract.get("source") or {}).get("type"),
        "events_per_second": simulator_contract.get("events_per_second") or replay_contract.get("events_per_second"),
        "mode": simulator_contract.get("mode") or replay_contract.get("mode"),
        "control_actions": list(simulator_contract.get("control_actions") or CONTROL_ACTIONS),
    })
    # The simulator may stop by itself after a one-shot file has been sent.
    # Refresh its read-only status so the drawer does not display a stale
    # persisted ``running`` value.  A missing simulator remains an explicit
    # unavailable optional component.
    try:
        live_simulator = NocSimulatorClient(
            str(simulator_contract.get("url") or "").strip() or None,
            lifecycle=simulator_contract.get("lifecycle")
            if isinstance(simulator_contract.get("lifecycle"), Mapping)
            else None,
        ).status()
        if live_simulator.get("available"):
            simulator.update(live_simulator)
    except NocRuntimeError as exc:
        simulator["status_error"] = str(exc)
    observed_state = str(runtime.get("state", "registered"))
    simulator_state = str(simulator.get("state") or "")
    # A one-shot replay can finish without a control request.  In that case
    # the source is no longer running even if the persisted control record
    # still says ``running``; expose the authoritative simulator state to the
    # UI while leaving the NiFi process group available for the next cycle.
    if simulator.get("available") and simulator_state in {"stopped", "deleted"} and observed_state in {
        "starting", "running", "paused"
    }:
        observed_state = simulator_state
        # A one-shot replay can finish without a cPlatform action request.
        # Persist the authoritative terminal state as well as exposing it in
        # the snapshot; otherwise the next Start request sees the old
        # persisted ``running`` state and incorrectly treats Start as a
        # no-op, reusing the previous cycle ID.
        if runtime.get("state") != observed_state or runtime.get("simulator_state") != simulator_state:
            runtime = dict(runtime)
            runtime["state"] = observed_state
            runtime["simulator_state"] = simulator_state
            runtime["simulator"] = dict(simulator)
            save_runtime(dataflow, runtime, status="Disable")
    snapshot: dict[str, Any] = {
        "success": True,
        "available": True,
        "dataflow_id": dataflow.dataflow_id,
        "stream_name": dataflow.dataflow_name,
        "run_id": runtime.get("run_id"),
        "cycle_id": runtime.get("cycle_id"),
        "state": observed_state,
        "source": _clean_source(contract),
        "replay": contract.get("replay", {}),
        "simulator": simulator,
        "kafka": {"available": False, "bootstrap_servers": (contract.get("kafka") or {}).get("bootstrap_servers")},
        "postgresql": {"available": False},
        "prometheus": {"available": False},
        "workers": {"available": False},
        "nifi": nifi,
        "last_error": runtime.get("last_error"),
        "updated_at": runtime.get("updated_at"),
    }
    if isinstance(remote, dict) and remote.get("success", True):
        for key in ("kafka", "postgresql", "prometheus", "workers", "nifi", "simulator", "incidents", "dlq", "alarm_summary"):
            if key in remote:
                snapshot[key] = remote[key]
        snapshot["observer"] = {"available": True, "source": "agenticnoc", "updated_at": remote.get("updated_at")}
    else:
        snapshot["observer"] = {"available": False, "error": remote.get("error") if isinstance(remote, dict) else "unavailable"}
    return snapshot


def apply_action(dataflow: Any, action: str) -> dict[str, Any]:
    """Apply one idempotent lifecycle action and return its live snapshot."""

    normalized = str(action or "").strip().lower()
    if normalized not in set(CONTROL_ACTIONS):
        raise NocRuntimeError("action must be start, pause, resume, stop, or delete")
    contract = (dataflow.conn_info or {}).get("control_plane_contract") or {}
    if not contract:
        raise NocRuntimeError("dataflow does not contain a NOC control-plane contract")
    runtime = runtime_for(dataflow)
    client = NocNiFiClient()
    simulator_contract = contract.get("simulator") if isinstance(contract.get("simulator"), Mapping) else {}
    simulator_url = str(simulator_contract.get("url") or "").strip() or None
    lifecycle = simulator_contract.get("lifecycle") if isinstance(simulator_contract.get("lifecycle"), Mapping) else None
    simulator = NocSimulatorClient(simulator_url, lifecycle=lifecycle)

    if normalized == "delete":
        if runtime.get("group_id"):
            client.delete_group(str(runtime["group_id"]))
        runtime["simulator_state"] = "deleted"
        runtime["simulator"] = simulator.delete()
        from . import StrmflowMgmt

        message = StrmflowMgmt.dataflow_delete_request(dataflow.dataflow_id)
        return {"success": not str(message).lower().startswith("unable"), "deleted": True, "message": message, "dataflow_id": dataflow.dataflow_id}

    try:
        if normalized == "start":
            if runtime.get("state") in {"running", "starting"} and runtime.get("group_id"):
                # Reconcile a one-shot simulator that completed naturally
                # before applying the idempotent-running fast path.  Without
                # this read, a stale persisted state prevents a later Start
                # from allocating a new cycle.
                try:
                    live_simulator = simulator.status()
                except NocRuntimeError:
                    live_simulator = {}
                live_state = str(live_simulator.get("state") or "")
                if live_simulator.get("available") and live_state in {"stopped", "deleted"}:
                    runtime["state"] = live_state
                    runtime["simulator_state"] = live_state
                    runtime["simulator"] = dict(live_simulator)
                    save_runtime(dataflow, runtime, status="Disable")
                else:
                    return snapshot_for(dataflow)
            runtime["state"] = "starting"
            runtime["last_error"] = None
            runtime["cycle_number"] = int(runtime.get("cycle_number") or 0) + 1
            runtime["cycle_id"] = new_cycle_id(str(contract.get("stream_id") or dataflow.dataflow_name), runtime["cycle_number"])
            runtime["run_id"] = str(uuid.uuid4())
            runtime["simulator"] = simulator.configure(contract, str(runtime["cycle_id"]))
            runtime["simulator_state"] = "starting"
            save_runtime(dataflow, runtime, status="Enable")
            if runtime.get("rebuild_required") and runtime.get("group_id"):
                client.delete_group(str(runtime["group_id"]))
                runtime["group_id"] = None
            group_id = client.ensure_group(str((contract.get("nifi") or {}).get("flow_name") or NIFI_FLOW_NAME))
            runtime["group_id"] = group_id
            nifi_config = client.configure(group_id, contract, str(runtime["cycle_id"]))
            group_id = str(nifi_config.get("group_id") or group_id)
            runtime["group_id"] = group_id
            client.set_state(group_id, "RUNNING")
            runtime["state"] = "running"
            runtime["simulator_state"] = "running"
            runtime["simulator"] = simulator.set_state(
                "running", action="start", cycle_id=str(runtime["cycle_id"])
            )
            runtime["rebuild_required"] = False
            save_runtime(dataflow, runtime, status="Enable")
        elif normalized == "pause":
            if runtime.get("group_id"):
                client.set_state(str(runtime["group_id"]), "STOPPED")
            runtime["state"] = "paused"
            runtime["simulator_state"] = "paused"
            runtime["simulator"] = simulator.set_state("paused", cycle_id=runtime.get("cycle_id"))
            save_runtime(dataflow, runtime, status="Disable")
        elif normalized == "resume":
            if not runtime.get("group_id"):
                raise NocRuntimeError("stream has not been started")
            client.set_state(str(runtime["group_id"]), "RUNNING")
            runtime["state"] = "running"
            runtime["simulator_state"] = "running"
            runtime["simulator"] = simulator.set_state(
                "running", action="resume", cycle_id=runtime.get("cycle_id")
            )
            save_runtime(dataflow, runtime, status="Enable")
        elif normalized == "stop":
            if runtime.get("group_id"):
                client.set_state(str(runtime["group_id"]), "STOPPED")
            runtime["state"] = "stopped"
            runtime["simulator_state"] = "stopped"
            runtime["simulator"] = simulator.set_state("stopped", cycle_id=runtime.get("cycle_id"))
            save_runtime(dataflow, runtime, status="Disable")
    except Exception as exc:
        runtime["state"] = "failed"
        runtime["simulator_state"] = "failed"
        runtime["last_error"] = str(exc)
        save_runtime(dataflow, runtime, status="Disable")
        if isinstance(exc, NocRuntimeError):
            raise
        raise NocRuntimeError(str(exc)) from exc
    return snapshot_for(dataflow)
