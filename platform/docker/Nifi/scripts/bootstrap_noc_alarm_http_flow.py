#!/usr/bin/env python3
"""Validate the additive ListenHTTP alarm flow before a NiFi import.

This intentionally does not modify or replace the existing local/FTP flow.
Deployment automation can call this check before importing the XML template;
the manifest has no credentials and no Kafka/raw-topic side effects.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "flows/noc_alarm_http_to_agenticnoc_v1.flow.json"
DEFAULT_SCHEMA = ROOT / "contracts/noc_alarm_mapped_v1.schema.json"
DEFAULT_TEMPLATE = ROOT / "templates/noc_alarm_http_to_agenticnoc_v1.xml"


class FlowContractError(ValueError):
    """The checked-in flow does not satisfy the HTTP ingress contract."""


def validate_template(path: Path = DEFAULT_TEMPLATE) -> None:
    """Ensure the portable XML artifact matches the JSON source contract."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FlowContractError(f"unable to read NiFi template {path}: {exc}") from exc
    if "org.apache.nifi.processors.jolt.JoltTransformJSON" not in text:
        raise FlowContractError("NiFi template must use the NiFi 2.x JoltTransformJSON class")
    for obsolete in ("<key>Remote URL</key>", "<key>Send Message Body</key>", "Response Retry Attribute Name"):
        if obsolete in text:
            raise FlowContractError(f"NiFi template contains obsolete property: {obsolete}")
    if "<key>HTTP URL</key>" not in text or "<key>Request Body Enabled</key>" not in text:
        raise FlowContractError("NiFi template must use current InvokeHTTP URL/body properties")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowContractError(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FlowContractError(f"JSON document {path} must be an object")
    return value


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _load_json(path)
    if manifest.get("flow_name") != "noc-alarm-http-to-agenticnoc-v1":
        raise FlowContractError("unexpected HTTP flow name")
    if manifest.get("flow_version") != "1":
        raise FlowContractError("HTTP flow must be version 1")
    if manifest.get("contract") != "noc-alarm-mapped.v1":
        raise FlowContractError("HTTP flow must use noc-alarm-mapped.v1")
    input_contract = manifest.get("input")
    if not isinstance(input_contract, dict) or input_contract.get("processor") != "ListenHTTP":
        raise FlowContractError("HTTP flow must declare a ListenHTTP input")
    if input_contract.get("port") != 9080 or input_contract.get("base_path") != "aviat":
        raise FlowContractError("ListenHTTP compatibility endpoint must be port 9080/path aviat")
    lineage = input_contract.get("source_lineage_headers")
    if (
        not isinstance(lineage, dict)
        or lineage.get("source_file") != "X-Original-Filename"
        or lineage.get("source_row") != "X-Row-Number"
        or lineage.get("vendor") != "X-Vendor"
    ):
        raise FlowContractError("HTTP input must map source filename, row, and vendor headers")
    if input_contract.get("one_row_per_request") is not True:
        raise FlowContractError("HTTP input must declare one_row_per_request=true")

    processors = manifest.get("processors")
    if not isinstance(processors, list) or not processors:
        raise FlowContractError("HTTP flow must define processors")
    ids = [item.get("id") for item in processors if isinstance(item, dict)]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        raise FlowContractError("HTTP processor ids must be unique and non-empty")
    processor_types = {item.get("type", "") for item in processors if isinstance(item, dict)}
    invoke_http = [
        item for item in processors
        if isinstance(item, dict)
        and item.get("type") == "org.apache.nifi.processors.standard.InvokeHTTP"
    ]
    if any("Response Retry Attribute Name" in (item.get("properties") or {}) for item in invoke_http):
        raise FlowContractError(
            "HTTP InvokeHTTP must not declare the removed NiFi 1.x Response Retry Attribute Name property"
        )
    listen_processors = [
        item for item in processors
        if isinstance(item, dict) and item.get("type") == "org.apache.nifi.processors.standard.ListenHTTP"
    ]
    header_pattern = listen_processors[0].get("properties", {}).get("HTTP Headers for Attributes", "") if listen_processors else ""
    if "X-Original-Filename" not in header_pattern or "X-Vendor" not in header_pattern:
        raise FlowContractError("ListenHTTP must retain source lineage and vendor headers")
    if any("PublishKafka" in value or "Kafka" in value for value in processor_types):
        raise FlowContractError("HTTP flow must not publish to the legacy Kafka/raw topic")
    required_types = {
        "org.apache.nifi.processors.standard.ListenHTTP",
        "org.apache.nifi.processors.standard.ConvertRecord",
        "org.apache.nifi.processors.standard.ValidateRecord",
        "org.apache.nifi.processors.standard.DetectDuplicate",
        "org.apache.nifi.processors.standard.InvokeHTTP",
        "org.apache.nifi.processors.standard.PutFile",
        "org.apache.nifi.processors.standard.HandleHttpResponse",
    }
    has_jolt = any(
        "JoltTransformJSON" in t for t in processor_types
    )
    missing = sorted(required_types - processor_types)
    if missing or not has_jolt:
        if not has_jolt:
            missing.append("JoltTransformJSON")
        raise FlowContractError(f"HTTP flow is missing required processor types: {', '.join(missing)}")
    processor_ids = set(ids)
    connections = manifest.get("connections")
    if not isinstance(connections, list) or not connections:
        raise FlowContractError("HTTP flow must define connections")
    for connection in connections:
        if connection.get("source") not in processor_ids or connection.get("destination") not in processor_ids:
            raise FlowContractError("HTTP connections must reference declared processors")
        if not connection.get("relationships"):
            raise FlowContractError("HTTP connections must declare relationships")
    names = {item.get("name", "") for item in processors if isinstance(item, dict)}
    for expected in ("Duplicate metric route", "DLQ metric route", "POST canonical alarm to AgenticNOC"):
        if expected not in names:
            raise FlowContractError(f"HTTP flow missing {expected}")
    if "RespondToHTTP" not in names:
        raise FlowContractError("HTTP flow missing RespondToHTTP")
    services = manifest.get("controller_services")
    service_ids = {item.get("id") for item in services if isinstance(item, dict)} if isinstance(services, list) else set()
    if len(service_ids) != len(services or []) or None in service_ids:
        raise FlowContractError("HTTP controller service ids must be unique and non-empty")
    if {"noc-http-duplicate-cache", "noc-http-duplicate-cache-server", "http-context-map"} - service_ids:
        raise FlowContractError("HTTP flow must define duplicate cache and HTTP context services")
    duplicate_cache = manifest.get("duplicate_cache")
    if (
        not isinstance(duplicate_cache, dict)
        or duplicate_cache.get("client_service") != "noc-http-duplicate-cache"
        or duplicate_cache.get("server_service") != "noc-http-duplicate-cache-server"
    ):
        raise FlowContractError("HTTP flow must document its duplicate-cache contract")
    for processor in processors:
        for property_name in ("Record Reader", "Record Writer", "Distributed Cache Service", "HTTP Context Map"):
            reference = processor.get("properties", {}).get(property_name)
            if reference and reference not in service_ids:
                raise FlowContractError(f"HTTP processor references unknown controller service {reference!r}")
    schema_ref = Path(path).parent / manifest.get("contract_schema", "")
    schema_path = schema_ref.resolve()
    if schema_path != DEFAULT_SCHEMA.resolve():
        raise FlowContractError(f"HTTP flow schema must be {DEFAULT_SCHEMA}")
    schema = _load_json(schema_path)
    if schema.get("$id", "").endswith("noc-alarm-mapped.v1.schema.json") is not True:
        raise FlowContractError("mapped schema id is incorrect")
    api_path = manifest.get("documented_api", {}).get("path")
    if api_path != "/api/ingestion/v2/alarms/":
        raise FlowContractError("HTTP flow must document AgenticNOC's canonical v2 alarm API")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--nifi-url", default="http://localhost:8443")
    parser.add_argument("--start", action="store_true", help="start processors after importing the flow")
    parser.add_argument("--replace", action="store_true", help="replace an existing HTTP process group")
    parser.add_argument("--apply", action="store_true", help="import the validated manifest through the NiFi REST API")
    parser.add_argument("--dry-run", action="store_true", help="validate and print the import plan")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        if not args.template.is_file():
            raise FlowContractError(f"NiFi template does not exist: {args.template}")
        validate_template(args.template)
        if args.apply:
            sys.path.insert(0, str(ROOT / "scripts"))
            import bootstrap_noc_alarm_flow

            result = bootstrap_noc_alarm_flow.bootstrap_manifest(
                args.nifi_url,
                manifest,
                start=args.start,
                replace=args.replace,
            )
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.dry_run:
            print(json.dumps({
                "flow_name": manifest["flow_name"],
                "flow_version": manifest["flow_version"],
                "contract": manifest["contract"],
                "listen": "/" + manifest["input"]["base_path"],
                "processors": len(manifest["processors"]),
                "connections": len(manifest["connections"]),
                "legacy_kafka_publish": False,
                "agenticnoc_api": manifest["documented_api"]["path"],
                "template": str(args.template),
            }, sort_keys=True))
        else:
            print(f"validated {manifest['flow_name']} ({len(manifest['processors'])} processors)")
        return 0
    except FlowContractError as exc:
        print(f"HTTP flow validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
