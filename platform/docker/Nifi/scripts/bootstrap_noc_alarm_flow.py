#!/usr/bin/env python3
"""Bootstrap the checked-in NOC alarm flow into a NiFi instance.

The default operation is additive and reuses an existing process group by flow
name.  ``--dry-run``
performs all manifest validation without contacting NiFi, which is useful in a
fresh demo checkout and in CI.  The flow manifest deliberately contains no
secrets; FTP credentials should be supplied through NiFi parameters or the
environment of the deployment job.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TOPIC = "noc.alarm.raw.v1"
MIN_EPS = 1
MAX_EPS = 1000
DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "flows/noc_alarm_raw_v1.flow.json"
DEFAULT_HTTP_MANIFEST = Path(__file__).resolve().parents[1] / "flows/noc_alarm_http_to_agenticnoc_v1.flow.json"
HTTP_FLOW_NAME = "noc-alarm-http-to-agenticnoc-v1"
PARAMETER_REFERENCE = re.compile(r"#\{([^{}]+)\}")
ENV_DEFAULT_REFERENCE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}$")


class BootstrapError(RuntimeError):
    pass


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"unable to read flow manifest {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise BootstrapError(f"flow manifest {path} must be a JSON object")
    if manifest.get("flow_name") == HTTP_FLOW_NAME:
        return load_http_manifest(path)
    if manifest.get("topic") != TOPIC:
        raise BootstrapError(f"manifest topic must be {TOPIC}")
    processors = manifest.get("processors")
    if not isinstance(processors, list) or not processors:
        raise BootstrapError("manifest must define processors")
    ids = [p.get("id") for p in processors if isinstance(p, dict)]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        raise BootstrapError("processor ids must be unique and non-empty")
    services = manifest.get("controller_services", [])
    if not isinstance(services, list):
        raise BootstrapError("controller_services must be a list")
    service_ids = [service.get("id") for service in services if isinstance(service, dict)]
    if len(service_ids) != len(set(service_ids)) or any(not item for item in service_ids):
        raise BootstrapError("controller service ids must be unique and non-empty")
    if any(not isinstance(service, dict) or not service.get("type") for service in services):
        raise BootstrapError("controller services must have a type")
    service_id_set = set(service_ids)
    for processor in processors:
        for property_name in ("Record Reader", "Record Writer"):
            service_id = processor.get("properties", {}).get(property_name)
            if service_id and service_id not in service_id_set:
                raise BootstrapError(
                    f"processor {processor.get('name', processor.get('id'))} references unknown "
                    f"controller service {service_id!r}"
                )
    for processor in processors:
        input_mode = processor.get("input_mode")
        if input_mode is not None and input_mode not in {"local", "ftp"}:
            raise BootstrapError(f"processor {processor.get('id')} has invalid input_mode {input_mode!r}")
    processor_id_set = set(ids)
    for connection in manifest.get("connections", []):
        if connection.get("source") not in processor_id_set or connection.get("destination") not in processor_id_set:
            raise BootstrapError("connections must reference declared processor ids")
    csv_contract = manifest.get("csv_contract", {})
    if csv_contract.get("preamble_lines") != 2:
        raise BootstrapError("csv contract must strip exactly two preamble lines")
    replay = manifest.get("replay_contract", {})
    eps = replay.get("events_per_second", {})
    if eps.get("minimum") != MIN_EPS or eps.get("maximum") != MAX_EPS or eps.get("default") != 100:
        raise BootstrapError("replay contract must be 1-1000 eps with a default of 100")
    if replay.get("continuous") is not True or replay.get("cycle_id_header") != "cycle_id":
        raise BootstrapError("manifest must enable continuous replay and cycle_id")
    return manifest


def load_http_manifest(path: Path = DEFAULT_HTTP_MANIFEST) -> dict[str, Any]:
    """Load and validate the additive HTTP ingress manifest.

    The raw local/FTP flow remains the default PlatformOps stream.  Keeping the
    HTTP checks here lets one bootstrap command validate/import both flows,
    while the dedicated HTTP validator remains usable by deployment checks.
    """

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"unable to read HTTP flow manifest {path}: {exc}") from exc
    if manifest.get("flow_name") != HTTP_FLOW_NAME or manifest.get("flow_version") != "1":
        raise BootstrapError("HTTP manifest must be noc-alarm-http-to-agenticnoc-v1 version 1")
    if manifest.get("contract") != "noc-alarm-mapped.v1":
        raise BootstrapError("HTTP manifest must use noc-alarm-mapped.v1")
    input_contract = manifest.get("input")
    if not isinstance(input_contract, dict) or input_contract.get("processor") != "ListenHTTP":
        raise BootstrapError("HTTP manifest must declare a ListenHTTP input")
    if input_contract.get("port") != 9080 or input_contract.get("base_path") != "aviat":
        raise BootstrapError("HTTP ListenHTTP compatibility endpoint must be 9080/aviat")
    lineage = input_contract.get("source_lineage_headers")
    if not isinstance(lineage, dict) or lineage.get("source_file") != "X-Original-Filename" or lineage.get("source_row") != "X-Row-Number":
        raise BootstrapError("HTTP input must map source filename and row headers")
    processors = manifest.get("processors")
    if not isinstance(processors, list) or not processors:
        raise BootstrapError("HTTP manifest must define processors")
    ids = [item.get("id") for item in processors if isinstance(item, dict)]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        raise BootstrapError("HTTP processor ids must be unique and non-empty")
    processor_types = {item.get("type", "") for item in processors if isinstance(item, dict)}
    listen_processors = [
        item for item in processors
        if isinstance(item, dict) and item.get("type") == "org.apache.nifi.processors.standard.ListenHTTP"
    ]
    header_pattern = listen_processors[0].get("properties", {}).get("HTTP Headers for Attributes", "") if listen_processors else ""
    if "X-Original-Filename" not in header_pattern:
        raise BootstrapError("ListenHTTP must retain source lineage headers")
    required_types = {
        "org.apache.nifi.processors.standard.ListenHTTP",
        "org.apache.nifi.processors.standard.ConvertRecord",
        "org.apache.nifi.processors.standard.ValidateRecord",
        "org.apache.nifi.processors.standard.DetectDuplicate",
        "org.apache.nifi.processors.standard.InvokeHTTP",
        "org.apache.nifi.processors.standard.PutFile",
        "org.apache.nifi.processors.standard.HandleHttpResponse",
    }
    # NiFi 2.x moved JoltTransformJSON from the standard bundle to the Jolt
    # bundle.  Accept either fully-qualified class here so the contract
    # validator works with both the committed 2.x image and older compatible
    # installations; the manifest remains the source of truth for the exact
    # class used by a deployment.
    has_jolt = any(item.endswith("JoltTransformJSON") for item in processor_types)
    missing = sorted(required_types - processor_types)
    if not has_jolt:
        missing.append("JoltTransformJSON")
    if missing:
        raise BootstrapError("HTTP manifest is missing processor types: " + ", ".join(missing))
    if any("Kafka" in value for value in processor_types):
        raise BootstrapError("HTTP manifest must not publish to the legacy Kafka/raw topic")
    processor_ids = set(ids)
    connections = manifest.get("connections")
    if not isinstance(connections, list) or not connections:
        raise BootstrapError("HTTP manifest must define connections")
    for connection in connections:
        if connection.get("source") not in processor_ids or connection.get("destination") not in processor_ids:
            raise BootstrapError("HTTP connections must reference declared processor ids")
        if not connection.get("relationships"):
            raise BootstrapError("HTTP connections must declare relationships")
    names = {item.get("name", "") for item in processors if isinstance(item, dict)}
    for expected in (
        "Duplicate metric route",
        "DLQ metric route",
        "POST canonical alarm to AgenticNOC",
        "RespondToHTTP",
    ):
        if expected not in names:
            raise BootstrapError(f"HTTP manifest missing {expected}")
    services = manifest.get("controller_services", [])
    if not isinstance(services, list):
        raise BootstrapError("HTTP controller_services must be a list")
    service_ids = {item.get("id") for item in services if isinstance(item, dict)}
    if len(service_ids) != len(services) or None in service_ids:
        raise BootstrapError("HTTP controller service ids must be unique and non-empty")
    if {"noc-http-duplicate-cache", "noc-http-duplicate-cache-server", "http-context-map"} - service_ids:
        raise BootstrapError("HTTP manifest must define duplicate cache and HTTP context services")
    duplicate_cache = manifest.get("duplicate_cache")
    if (
        not isinstance(duplicate_cache, dict)
        or duplicate_cache.get("client_service") != "noc-http-duplicate-cache"
        or duplicate_cache.get("server_service") != "noc-http-duplicate-cache-server"
    ):
        raise BootstrapError("HTTP manifest must document its duplicate-cache contract")
    for processor in processors:
        for property_name in ("Record Reader", "Record Writer", "Distributed Cache Service", "HTTP Context Map"):
            reference = processor.get("properties", {}).get(property_name)
            if reference and reference not in service_ids:
                raise BootstrapError(f"HTTP processor references unknown controller service {reference!r}")
    schema_ref = Path(path).parent / str(manifest.get("contract_schema") or "")
    try:
        schema = json.loads(schema_ref.resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"HTTP mapped alarm schema is unavailable: {schema_ref}") from exc
    if schema.get("$id") != "https://cplatform.local/contracts/noc-alarm-mapped.v1.schema.json":
        raise BootstrapError("HTTP mapped alarm schema id is incorrect")
    ingest_url = str(manifest.get("parameters", {}).get("AgenticNOC Ingest URL", ""))
    if "/api/ingestion/v2/alarms/" not in ingest_url:
        raise BootstrapError("HTTP flow must target AgenticNOC's canonical v2 alarm API")
    if (manifest.get("documented_api") or {}).get("path") != "/api/ingestion/v2/alarms/":
        raise BootstrapError("HTTP flow must document AgenticNOC's canonical v2 alarm API")
    return manifest


def load_flow_manifest(path: Path) -> dict[str, Any]:
    """Dispatch validation by flow name without weakening raw-flow checks."""

    try:
        inspected = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"unable to inspect flow manifest {path}: {exc}") from exc
    if not isinstance(inspected, dict):
        raise BootstrapError(f"flow manifest {path} must be a JSON object")
    flow_name = inspected.get("flow_name")
    if flow_name == HTTP_FLOW_NAME:
        return load_http_manifest(path)
    return load_manifest(path)


def resolve_parameters(manifest: dict[str, Any]) -> dict[str, str]:
    """Resolve the portable ``${ENV:-default}`` values in a manifest.

    NiFi's ``#{parameter}`` syntax only works after a Parameter Context has
    been created and attached to the process group.  The bootstrap flow is
    deliberately usable in a freshly imported container, so it resolves the
    small, non-secret demo parameter set before submitting processor configs.
    Secrets are read only from the process environment and are never printed.
    """

    resolved: dict[str, str] = {}
    for name, raw_value in manifest.get("parameters", {}).items():
        value = str(raw_value)
        match = ENV_DEFAULT_REFERENCE.fullmatch(value)
        if match:
            env_name, default = match.groups()
            value = os.environ.get(env_name, default or "")
        resolved[str(name)] = value

    if manifest.get("flow_name") == HTTP_FLOW_NAME:
        if "/api/ingestion/v2/alarms/" not in resolved.get("AgenticNOC Ingest URL", ""):
            raise BootstrapError("AgenticNOC Ingest URL must use /api/ingestion/v2/alarms/")
        avsc_file = Path(__file__).resolve().parents[1] / "contracts/noc_alarm_mapped_v1.avsc"
        if avsc_file.is_file():
            try:
                resolved["Mapped Alarm Schema"] = json.dumps(json.loads(avsc_file.read_text(encoding="utf-8")))
            except Exception:
                pass
        return resolved

    input_mode = os.environ.get("NOC_INPUT_MODE", resolved.get("Input Mode", "local")).strip().lower()
    if input_mode not in {"local", "ftp"}:
        raise BootstrapError("NOC_INPUT_MODE must be either 'local' or 'ftp'")
    resolved["Input Mode"] = input_mode

    cycle_id = os.environ.get("NOC_CYCLE_ID", resolved.get("Cycle ID", "")).strip()
    if not cycle_id:
        cycle_id = "cycle-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    resolved["Cycle ID"] = cycle_id

    try:
        eps = int(os.environ.get("NOC_EVENTS_PER_SECOND", resolved.get("Events Per Second", "100")))
    except ValueError as exc:
        raise BootstrapError("NOC_EVENTS_PER_SECOND must be an integer") from exc
    if not MIN_EPS <= eps <= MAX_EPS:
        raise BootstrapError(f"NOC_EVENTS_PER_SECOND must be between {MIN_EPS} and {MAX_EPS}")
    resolved["Events Per Second"] = str(eps)
    return resolved


def resolve_processor_properties(properties: dict[str, Any], parameters: dict[str, str]) -> dict[str, Any]:
    """Replace exact/embedded NiFi parameter references with safe values."""

    def resolve(value: Any) -> Any:
        if not isinstance(value, str):
            return value

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            return parameters.get(key, match.group(0))

        return PARAMETER_REFERENCE.sub(replace, value)

    return {key: resolve(value) for key, value in properties.items()}


def _api_request(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(base_url.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        detail = getattr(exc, "read", lambda: b"")()
        detail_text = detail.decode("utf-8", errors="replace") if detail else str(exc)
        raise BootstrapError(f"NiFi API {method} {path} failed: {detail_text}") from exc
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BootstrapError(f"NiFi API returned non-JSON for {method} {path}") from exc


def _find_or_create_group(base_url: str, flow_name: str) -> str:
    # NiFi 2.x returns child process groups under the root flow document;
    # the older ``/flow/process-groups/root/process-groups`` endpoint is no
    # longer available.
    existing = _api_request(base_url, "GET", "/nifi-api/flow/process-groups/root")
    flow = existing.get("processGroupFlow", {}).get("flow", {})
    for group in flow.get("processGroups", []):
        component = group.get("component", group)
        if component.get("name") == flow_name:
            group_id = group.get("id") or component.get("id")
            if group_id:
                return str(group_id)
    created = _api_request(
        base_url,
        "POST",
        "/nifi-api/process-groups/root/process-groups",
        {
            "revision": {"version": 0},
            "component": {"name": flow_name, "position": {"x": 0, "y": 0}},
        },
    )
    group_id = created.get("id") or created.get("component", {}).get("id")
    if not group_id:
        raise BootstrapError("NiFi did not return a process-group id")
    return str(group_id)


def _controller_services(base_url: str, group_id: str) -> list[dict[str, Any]]:
    result = _api_request(base_url, "GET", f"/nifi-api/flow/process-groups/{group_id}/controller-services")
    return result.get("controllerServices", [])


def _wait_for_controller_service(base_url: str, service_id: str, timeout: float = 45.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = _api_request(base_url, "GET", f"/nifi-api/controller-services/{service_id}")
        component = last.get("component", {})
        state = component.get("state") or last.get("status", {}).get("runStatus")
        validation = component.get("validationStatus")
        errors = component.get("validationErrors") or []
        if state == "ENABLED":
            if validation == "INVALID" or errors:
                raise BootstrapError(
                    f"controller service {component.get('name', service_id)} is invalid: {'; '.join(errors)}"
                )
            return last
        if state == "DISABLED" and validation == "INVALID" and errors:
            raise BootstrapError(
                f"controller service {component.get('name', service_id)} is invalid: {'; '.join(errors)}"
            )
        time.sleep(0.5)
    component = last.get("component", {})
    raise BootstrapError(
        f"controller service {component.get('name', service_id)} did not become enabled within {timeout:g}s"
    )


def _create_controller_services(
    base_url: str,
    group_id: str,
    manifest: dict[str, Any],
    parameters: dict[str, str],
) -> dict[str, str]:
    """Create and enable the record services used by the NOC flow.

    NiFi processor properties that point at a Controller Service must contain
    the server-side UUID, not the human-readable service name.  The checked-in
    manifest uses stable local IDs so it remains portable between instances;
    this function resolves those IDs to the UUIDs returned by the API.
    """

    service_ids: dict[str, str] = {}
    for service in manifest.get("controller_services", []):
        properties = resolve_processor_properties(service.get("properties", {}), parameters)
        created = _api_request(
            base_url,
            "POST",
            f"/nifi-api/process-groups/{group_id}/controller-services",
            {
                "revision": {"version": 0},
                "component": {
                    "type": service["type"],
                    "name": service["name"],
                    "properties": properties,
                },
            },
        )
        nifi_id = created.get("id") or created.get("component", {}).get("id")
        if not nifi_id:
            raise BootstrapError(f"NiFi did not return an id for controller service {service['name']}")
        service_ids[service["id"]] = str(nifi_id)

    for service_id in service_ids.values():
        current = _api_request(base_url, "GET", f"/nifi-api/controller-services/{service_id}")
        revision = current.get("revision", {"version": 0})
        _api_request(
            base_url,
            "PUT",
            f"/nifi-api/controller-services/{service_id}/run-status",
            {
                "revision": revision,
                "state": "ENABLED",
            },
        )
        _wait_for_controller_service(base_url, service_id)
    return service_ids


def _create_processors(
    base_url: str,
    group_id: str,
    manifest: dict[str, Any],
    controller_service_ids: dict[str, str] | None = None,
    parameters: dict[str, str] | None = None,
    input_mode: str = "local",
) -> dict[str, str]:
    processor_ids: dict[str, str] = {}
    controller_service_ids = controller_service_ids or {}
    parameters = parameters or {}
    for processor in manifest["processors"]:
        if processor.get("input_mode") not in (None, input_mode):
            continue
        properties = resolve_processor_properties({
            key: controller_service_ids.get(str(value), value)
            for key, value in processor.get("properties", {}).items()
        }, parameters)
        config = {
            "properties": properties,
            "schedulingStrategy": "TIMER_DRIVEN",
            "schedulingPeriod": "0 sec",
            "concurrentlySchedulableTaskCount": 2,
            "autoTerminatedRelationships": processor.get("auto_terminated_relationships", []),
        }
        created = _api_request(
            base_url,
            "POST",
            f"/nifi-api/process-groups/{group_id}/processors",
            {
                "revision": {"version": 0},
                "component": {
                    "type": processor["type"],
                    "name": processor["name"],
                    "position": processor.get("position", {"x": 0, "y": 0}),
                    "config": config,
                },
            },
        )
        nifi_id = created.get("id") or created.get("component", {}).get("id")
        if not nifi_id:
            raise BootstrapError(f"NiFi did not return an id for {processor['name']}")
        processor_ids[processor["id"]] = str(nifi_id)
    return processor_ids


def _create_connections(base_url: str, group_id: str, manifest: dict[str, Any], processor_ids: dict[str, str]) -> None:
    for connection in manifest.get("connections", []):
        if connection["source"] not in processor_ids or connection["destination"] not in processor_ids:
            continue
        source = processor_ids[connection["source"]]
        destination = processor_ids[connection["destination"]]
        _api_request(
            base_url,
            "POST",
            f"/nifi-api/process-groups/{group_id}/connections",
            {
                "revision": {"version": 0},
                "component": {
                    "source": {"id": source, "type": "PROCESSOR", "groupId": group_id},
                    "destination": {"id": destination, "type": "PROCESSOR", "groupId": group_id},
                    "selectedRelationships": connection.get("relationships", ["success"]),
                    "backPressureObjectThreshold": 10000,
                    "backPressureDataSizeThreshold": "1 GB",
                },
            },
        )


def _validate_group(base_url: str, group_id: str) -> None:
    flow_response = _api_request(base_url, "GET", f"/nifi-api/flow/process-groups/{group_id}")
    flow = flow_response.get("processGroupFlow", {}).get("flow", {})
    errors: list[str] = []
    for processor in flow.get("processors", []):
        component = processor.get("component", {})
        if component.get("validationStatus") == "INVALID":
            details = "; ".join(component.get("validationErrors") or ["validation failed"])
            errors.append(f"{component.get('name', processor.get('id'))}: {details}")
    if errors:
        raise BootstrapError("flow validation failed: " + " | ".join(errors))


def _start_processors(
    base_url: str,
    group_id: str,
    processor_ids: dict[str, str],
) -> None:
    for processor_key, processor_id in processor_ids.items():
        current = _api_request(base_url, "GET", f"/nifi-api/processors/{processor_id}")
        revision = current.get("revision", {"version": 0})
        _api_request(
            base_url,
            "PUT",
            f"/nifi-api/processors/{processor_id}/run-status",
            {
                "revision": revision,
                "state": "RUNNING",
            },
    )


def _delete_group(base_url: str, group_id: str) -> None:
    """Stop and remove a previously bootstrapped demo group."""

    flow_response = _api_request(base_url, "GET", f"/nifi-api/flow/process-groups/{group_id}")
    flow = flow_response.get("processGroupFlow", {}).get("flow", {})
    for processor in flow.get("processors", []):
        current = _api_request(base_url, "GET", f"/nifi-api/processors/{processor['id']}")
        try:
            _api_request(
                base_url,
                "PUT",
                f"/nifi-api/processors/{processor['id']}/run-status",
                {"revision": current.get("revision", {"version": 0}), "state": "STOPPED"},
            )
        except BootstrapError:
            # A processor can already be stopped or invalid; deletion can still
            # proceed after the best-effort stop request.
            pass
    for service in _controller_services(base_url, group_id):
        service_id = service.get("id")
        if not service_id:
            continue
        current = _api_request(base_url, "GET", f"/nifi-api/controller-services/{service_id}")
        # NiFi may report an invalid service as ENABLING for a short period.
        # It still has to be explicitly disabled before the process group can
        # be deleted, so request DISABLED for every non-disabled service.
        if current.get("component", {}).get("state") != "DISABLED":
            try:
                _api_request(
                    base_url,
                    "PUT",
                    f"/nifi-api/controller-services/{service_id}/run-status",
                    {"revision": current.get("revision", {"version": 0}), "state": "DISABLED"},
                )
            except BootstrapError:
                pass
    # Wait briefly for asynchronous controller-service shutdown.  This keeps
    # edit/rebuild deterministic on NiFi 2.x, where a service can remain
    # active after the run-status request has returned.
    deadline = time.monotonic() + 60.0
    final_states: list[str | None] = []
    while time.monotonic() < deadline:
        services = _controller_services(base_url, group_id)
        states = []
        for service in services:
            service_id = service.get("id")
            if not service_id:
                continue
            current = _api_request(base_url, "GET", f"/nifi-api/controller-services/{service_id}")
            states.append(current.get("component", {}).get("state"))
        final_states = states
        if all(state == "DISABLED" for state in states):
            break
        time.sleep(0.5)
    if any(state != "DISABLED" for state in final_states):
        raise BootstrapError(
            f"controller services did not become disabled before group deletion: {final_states}"
        )
    current = _api_request(base_url, "GET", f"/nifi-api/process-groups/{group_id}")
    revision = current.get("revision", {"version": 0})
    _api_request(
        base_url,
        "DELETE",
        f"/nifi-api/process-groups/{group_id}?version={revision.get('version', 0)}&disconnectedNodeAcknowledged=true",
    )


def bootstrap_manifest(
    base_url: str,
    manifest: dict[str, Any],
    *,
    start: bool = False,
    replace: bool = False,
) -> dict[str, Any]:
    """Import one validated manifest into its own additive process group."""

    parameters = resolve_parameters(manifest)
    group_id = _find_or_create_group(base_url, manifest["flow_name"])
    if replace:
        _delete_group(base_url, group_id)
        group_id = _find_or_create_group(base_url, manifest["flow_name"])
    else:
        existing_flow = _api_request(base_url, "GET", f"/nifi-api/flow/process-groups/{group_id}")
        existing = existing_flow.get("processGroupFlow", {}).get("flow", {})
        if existing.get("processors") or _controller_services(base_url, group_id):
            raise BootstrapError(
                f"process group {manifest['flow_name']} already contains components; rerun with --replace"
            )
    controller_service_ids = _create_controller_services(base_url, group_id, manifest, parameters)
    processor_ids = _create_processors(
        base_url,
        group_id,
        manifest,
        controller_service_ids,
        parameters,
        parameters.get("Input Mode", "local"),
    )
    _create_connections(base_url, group_id, manifest, processor_ids)
    _validate_group(base_url, group_id)
    if start:
        _start_processors(base_url, group_id, processor_ids)
    return {"flow_name": manifest["flow_name"], "group_id": group_id, "started": start}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--http-manifest", type=Path, default=DEFAULT_HTTP_MANIFEST)
    parser.add_argument("--nifi-url", default=os.environ.get("NIFI_URL", "http://localhost:8443"))
    parser.add_argument("--dry-run", action="store_true", help="validate and print the flow without contacting NiFi")
    parser.add_argument("--start", action="store_true", help="start processors after creating the flow")
    parser.add_argument("--replace", action="store_true", help="replace an existing group with the same flow name")
    parser.add_argument(
        "--include-http",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also validate/import the additive HTTP-to-AgenticNOC flow (default: enabled)",
    )
    parser.add_argument("--http-only", action="store_true", help="bootstrap only the additive HTTP flow")
    args = parser.parse_args(argv)

    try:
        manifests: list[dict[str, Any]] = []
        if not args.http_only:
            manifests.append(load_manifest(args.manifest))
        if args.include_http or args.http_only:
            manifests.append(load_http_manifest(args.http_manifest))
        if not manifests:
            raise BootstrapError("at least one flow manifest must be selected")
        for manifest in manifests:
            print(
                f"validated {manifest['flow_name']}"
                + (f" -> {TOPIC}" if manifest.get("topic") == TOPIC else "")
                + f" ({len(manifest['processors'])} processors)"
            )
        if args.dry_run:
            primary = manifests[0]
            primary_parameters = resolve_parameters(primary)
            print(json.dumps({
                "flow_name": primary["flow_name"],
                "topic": primary.get("topic"),
                "input_mode": primary_parameters.get("Input Mode"),
                "events_per_second": int(primary_parameters["Events Per Second"]) if primary_parameters.get("Events Per Second") else None,
                "flows": [
                    {
                        "flow_name": manifest["flow_name"],
                        "topic": manifest.get("topic"),
                        "processors": len(manifest["processors"]),
                    }
                    for manifest in manifests
                ],
                "dry_run": True,
            }, sort_keys=True))
            return 0
        results = [bootstrap_manifest(args.nifi_url, manifest, start=args.start, replace=args.replace) for manifest in manifests]
        print(json.dumps({"flows": results, "started": args.start}, sort_keys=True))
        return 0
    except BootstrapError as exc:
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
