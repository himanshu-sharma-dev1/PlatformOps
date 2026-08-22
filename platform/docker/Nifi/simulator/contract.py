"""Small, dependency-free helpers for the mapped alarm v1 contract.

The simulator does not replace AgenticNOC's vendor adapter.  It only provides
the deterministic field mapping needed by the HTTP replay path and by local
contract tests.  NiFi performs the same mapping in production; keeping this
copy here makes the simulator useful without a NiFi or Django dependency.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping


CONTRACT = "noc-alarm-mapped.v1"
SCHEMA_VERSION = 1
SEVERITIES = {"critical", "major", "minor", "warning", "indeterminate", "cleared"}
STATES = {"active", "cleared", "acknowledged"}
EVENT_TYPES = {"raise", "update", "clear"}


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def _clean(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text in {"", "-", "--", "null", "None"} else text


def _value(row: Mapping[str, object], *names: str) -> str:
    normalized = {_key(name): _clean(value) for name, value in row.items()}
    for name in names:
        value = normalized.get(_key(name), "")
        if value:
            return value
    return ""


def _header(headers: Mapping[str, object] | None, *names: str) -> str:
    """Read HTTP metadata case-insensitively, including NiFi's prefix."""

    if not headers:
        return ""
    wanted = {_key(name) for name in names}
    for name, value in headers.items():
        normalized = _key(name)
        if normalized.startswith("httpheaders"):
            normalized = normalized[len("httpheaders"):]
        if normalized in wanted:
            return _clean(value)
    return ""


def _timestamp(value: object) -> str | None:
    text = _clean(value)
    if not text:
        return None
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        for fmt in (
            "%d-%B-%Y %H:%M:%S",
            "%d-%b-%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _category(description: str, probable_cause: str) -> str:
    text = f"{description} {probable_cause}".lower()
    for keyword, category in (
        ("link down", "LINK_DOWN"),
        ("device is offline", "LINK_DOWN"),
        ("session dropped", "LINK_DOWN"),
        ("radio link failure", "LINK_DOWN"),
        ("loss of signal", "LINK_DOWN"),
        ("loss of comms", "LINK_DOWN"),
        ("rsl low", "RF_DEGRADED"),
        ("low rssi", "RF_DEGRADED"),
        ("poor snr", "RF_DEGRADED"),
        ("fade margin", "RF_DEGRADED"),
        ("demodulator not locked", "RF_DEGRADED"),
        ("high retransmission", "PERFORMANCE_DEGRADED"),
        ("error seconds", "PERFORMANCE_DEGRADED"),
        ("hardware failure", "HW_FAULT"),
        ("power fail", "POWER_FAULT"),
        ("loss of sync", "SYNC_LOSS"),
        ("temperature high", "ENVIRONMENTAL"),
    ):
        if keyword in text:
            return category
    # UNKNOWN is intentional.  AgenticNOC remains the authoritative taxonomy
    # owner and can classify new vendor phrases after this request arrives.
    return "UNKNOWN"


def map_aviat_row(
    row: Mapping[str, object],
    *,
    headers: Mapping[str, object] | None = None,
    source_file: str = "",
    source_row: int = 1,
    source_system: str = "cplatform-http-simulator",
    ingested_at: str | None = None,
    replay_cycle_id: str = "",
    replay_sequence: int | None = None,
    stream_id: str = "",
) -> dict[str, Any]:
    """Map one CSV row to the v1 HTTP request contract.

    ``ingested_at`` is injectable so fixtures and replay checks remain
    deterministic.  Delivery details are excluded from ``alarm_key`` but are
    included in ``event_id`` only through the source transition identity; a
    retried request for the same row therefore has the same id.
    """

    source_file = source_file or _header(headers, "X-Original-Filename", "source_file", "filename")
    if source_row == 1:
        source_row_text = _header(headers, "X-Row-Number", "source_row", "row_number")
        if source_row_text:
            try:
                source_row = int(source_row_text)
            except ValueError:
                source_row = 1
    source_system = _header(headers, "X-Source-System", "source_system") or source_system
    replay_cycle_id = replay_cycle_id or _header(headers, "X-Replay-Cycle-ID", "cycle_id", "replay_cycle_id")
    stream_id = stream_id or _header(headers, "X-Stream-ID", "stream_id")
    if replay_sequence is None:
        replay_sequence_text = _header(headers, "X-Replay-Sequence", "replay_sequence", "row_index")
        if replay_sequence_text:
            try:
                replay_sequence = int(replay_sequence_text)
            except ValueError:
                replay_sequence = None

    vendor = _header(headers, "X-Vendor", "vendor") or "aviat"
    vendor = vendor.lower()
    site = _value(row, "Site", "Site ID", "site_id", "Site_Name", "Source", "NEName")
    event_id = _value(row, "Event ID", "AlarmID", "Alarm ID", "Alarm_ID", "event_id")
    description = _value(
        row,
        "Event",
        "Message",
        "EventText",
        "AlarmName",
        "Alarm Name",
        "event_description",
        "SpecificProblem",
    )
    obj = _value(row, "Object", "Slot_Port", "Link_Name", "object")
    raised = _timestamp(_value(row, "Raised", "Raised At", "Raise_Time", "Raised Time", "source_event_time"))
    cleared = _timestamp(_value(row, "Cleared", "Clear_Time", "ClearDate", "Cleared At"))
    state_raw = _value(row, "State", "Alarm Status", "AlarmState", "Status", "state")
    is_clear = bool(cleared) or "clear" in state_raw.lower()
    state = "cleared" if is_clear else ("acknowledged" if "ack" in state_raw.lower() else "active")
    event_type = "clear" if is_clear else ("update" if "update" in state_raw.lower() else "raise")
    severity = _value(row, "Severity", "severity").lower()
    if is_clear:
        severity = "cleared"
    if severity not in SEVERITIES:
        severity = "indeterminate"
    probable = _value(row, "ProbableCause", "Probable Cause", "Event") or description
    external_id = event_id or vendor + "-" + hashlib.sha256(
        "|".join((site, description, _value(row, "Object", "object"), _value(row, "Raised", "raised"))).encode()
    ).hexdigest()[:24]
    alarm_key = f"{vendor}:{site}:{external_id}" if site else f"{vendor}:{external_id}"
    identity = {
        "alarm_key": alarm_key,
        "event_type": event_type,
        "state": state,
        "severity": severity,
        "raised": raised,
        "cleared": cleared,
        "description": description,
        "object": obj,
    }
    stable_event_id = "sha256:" + hashlib.sha256(
        json.dumps(identity, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    now = ingested_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    effective = cleared if is_clear else raised
    mapped: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "vendor": vendor,
        "source_system": source_system,
        "source_file": source_file,
        "source_row": int(source_row),
        "event_id": stable_event_id,
        "alarm_key": alarm_key,
        "external_alarm_id": external_id,
        "event_description": description,
        "object": obj,
        "site_id": site,
        "node_id": site or None,
        "severity": severity,
        "state": state,
        "event_type": event_type,
        "canonical_category": _category(description, probable),
        "probable_cause_raw": probable,
        "specific_problem": _value(row, "SpecificProblem", "Specific Problem"),
        "source_event_time": raised,
        "effective_event_time": effective,
        "device_raised_at": _timestamp(_value(row, "Device Raised", "DeviceRaised")),
        "device_cleared_at": _timestamp(_value(row, "Device Cleared", "DeviceCleared")),
        "nms_cleared_at": cleared,
        "ingested_at": now,
        "trace_id": f"http:{source_file}:{int(source_row)}" if source_file else f"http:row:{int(source_row)}",
        "replay_cycle_id": replay_cycle_id,
        "stream_id": stream_id,
        "replay_sequence": replay_sequence,
        # Native aliases keep the existing AgenticNOC webhook adapter
        # compatible while canonical fields remain the primary contract.
        "Circle": site[:2],
        "Cleared": cleared,
        "SpecificProblem": _value(row, "SpecificProblem", "Specific Problem"),
        "ProbableCause": probable,
        "AlarmID": external_id,
        "Site": site,
        "Severity": severity.title(),
        "State": "Cleared by network" if is_clear else (state.title()),
        "AlarmName": description,
        "Raised": raised,
    }
    return mapped


def validate_mapped_event(value: object) -> list[str]:
    """Return bounded, human-readable contract errors (empty means valid)."""

    if not isinstance(value, dict):
        return ["mapped event must be a JSON object"]
    required = (
        "schema_version", "contract", "vendor", "source_file", "source_row",
        "event_id", "alarm_key", "external_alarm_id", "event_description",
        "site_id", "severity", "state", "event_type", "canonical_category",
        "source_event_time", "ingested_at", "AlarmID", "Site", "Severity",
        "State", "AlarmName", "Raised",
    )
    errors = [f"missing required field: {name}" for name in required if name not in value]
    allowed = {
        "schema_version", "contract", "vendor", "source_system", "source_file", "source_row",
        "event_id", "alarm_key", "external_alarm_id", "event_description", "object", "site_id", "node_id",
        "severity", "state", "event_type", "canonical_category", "probable_cause_raw", "specific_problem",
        "source_event_time", "effective_event_time", "device_raised_at", "device_cleared_at", "nms_cleared_at",
        "ingested_at", "trace_id", "stream_id", "replay_cycle_id", "replay_sequence", "Circle", "Cleared",
        "SpecificProblem", "ProbableCause", "AlarmID", "Site", "Severity", "State", "AlarmName", "Raised",
    }
    errors.extend(f"unexpected field: {name}" for name in sorted(set(value) - allowed))
    if value.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if value.get("contract") != CONTRACT:
        errors.append(f"contract must be {CONTRACT}")
    if value.get("vendor") != "aviat":
        errors.append("vendor must be aviat")
    for name, allowed in (("severity", SEVERITIES), ("state", STATES), ("event_type", EVENT_TYPES)):
        if name in value and value[name] not in allowed:
            errors.append(f"{name} must be one of {sorted(allowed)}")
    for name in ("source_row",):
        if name in value and (not isinstance(value[name], int) or isinstance(value[name], bool) or value[name] < 1):
            errors.append(f"{name} must be a positive integer")
    for name in ("event_id", "alarm_key", "external_alarm_id", "AlarmID", "Site", "AlarmName"):
        if name in value and not isinstance(value[name], str):
            errors.append(f"{name} must be a string")
    for name in ("source_system", "source_file", "event_description", "site_id", "canonical_category"):
        if name in value and not isinstance(value[name], str):
            errors.append(f"{name} must be a string")
    for name in (
        "source_event_time", "effective_event_time", "device_raised_at", "device_cleared_at",
        "nms_cleared_at", "Cleared", "Raised",
    ):
        if name in value and value[name] is not None and not isinstance(value[name], str):
            errors.append(f"{name} must be a string or null")
        if name in value and isinstance(value[name], str) and value[name] and _timestamp(value[name]) is None:
            errors.append(f"{name} must be an ISO-8601 date-time")
    if "ingested_at" in value and (not isinstance(value["ingested_at"], str) or _timestamp(value["ingested_at"]) is None):
        errors.append("ingested_at must be an ISO-8601 date-time string")
    if "source_system" in value and not _clean(value["source_system"]):
        errors.append("source_system must not be empty")
    return errors
