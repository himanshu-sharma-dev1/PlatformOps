"""NiFi 2.x native Python processor: normalize one raw alarm CSV row
from ANY supported vendor, auto-detected from the row's column names.

No vendor name is ever hardcoded per-row -- it is detected dynamically
from which raw columns are present (see `_VENDOR_SIGNATURES` /
`detect_vendor()`). Adding a new vendor = add a signature + alias table,
no branching logic needed elsewhere.

Drop this file in: <NIFI_HOME>/python/extensions/NormalizeAlarm.py
then restart NiFi. It will appear in the processor palette as
"NormalizeAlarm".
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone as dt_timezone
from typing import Mapping

from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, StandardValidators


# ---------------------------------------------------------------------------
# Alarm-text -> canonical category (shared across vendors; matches against
# whatever raw fault-description text each vendor supplies)
# ---------------------------------------------------------------------------

ALARM_CODE_MAP: dict[str, str] = {
    "Loss of Comms": "Device Connectivity Failure",
    "One or more L1LA partner devices are not reachable": "Device Connectivity Failure",
    "Device is Offline": "Device Connectivity Failure",
    "Configuration Update Failed Due to Device Timeout": "Configuration Failure",
    "Ethernet port link down": "Ethernet Link Down",
    "Bit error rate (BER) threshold of 10^-6 has been exceeded": "High BER",
    "Bit error rate (BER) threshold of 10^-8 has been exceeded": "High BER",
    "Error Second (ES) Alarm": "Error Seconds Threshold Exceeded",
    "Error Seconds (ES) Ratio Threshold Exceeded": "Error Seconds Threshold Exceeded",
    "Severely Error Seconds (SES) Ratio Threshold Exceeded": "Severe Error Seconds Threshold Exceeded",
    "Demodulator not locked": "Demodulator Failure",
    "Module is missing": "Hardware Failure",
    "One or more L1LA member links are down": "Link Aggregation Failure",
    "Remote Fade Margin Low": "Radio Link Degradation",
    "System clock may be inaccurate": "Time Synchronization Issue",
}


def categorize(*texts: str | None) -> str:
    haystack = " ".join(t for t in texts if t).lower()
    if not haystack:
        return "UNKNOWN"
    for keyword, category in ALARM_CODE_MAP.items():
        if keyword.lower() in haystack:
            return category
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Per-vendor raw-column -> canonical-field alias tables.
#
# Canonical fields produced:
#   site, event, object, vendor_alarm_id, severity, state, raised, cleared
# ---------------------------------------------------------------------------

_AVIAT_FIELD_ALIASES = {
    "event": "event",
    "alarm": "event",
    "alarmname": "event",
    "eventdescription": "event",
    "object": "object",
    "site": "site",
    "siteid": "site",
    "raised": "raised",
    "raisedat": "raised",
    "severity": "severity",
    "state": "state",
    "cleared": "cleared",
    "clearedat": "cleared",
    "eventid": "vendor_alarm_id",
    "alarmid": "vendor_alarm_id",
    "deviceraised": "device_raised",
    "devicecleared": "device_cleared",
    "probablecause": "probable_cause",
    "specificproblem": "specific_problem",
}

_CAMBIUM_FIELD_ALIASES = {
    "source": "site",              # "Source" (Site Code) -> site
    "message": "event",            # "Message" -> event
    "sourcetype": "object",        # "Source Type" -> object
    "name": "vendor_alarm_id",     # "Name" (e.g. STATUS, RADIO) -> vendor_alarm_id
    "severity": "severity",
    "alarmstatus": "state",        # "Alarm Status" -> state
    "raisedtime": "raised",        # "Raised Time" -> raised
    "cleartime": "cleared",        # "Clear Time" -> cleared
    "durationsec": "duration_seconds",
    "ipaddress": "ip_address",
    "mac": "mac_address",
}

_FIELD_ALIASES_BY_VENDOR: dict[str, dict[str, str]] = {
    "aviat": _AVIAT_FIELD_ALIASES,
    "cambium": _CAMBIUM_FIELD_ALIASES,
}


# ---------------------------------------------------------------------------
# Vendor auto-detection: match the row's raw column names against each
# vendor's distinctive signature columns. Highest overlap wins. Nothing
# here is a per-row hardcoded vendor string -- it is computed from the
# data itself.
# ---------------------------------------------------------------------------

_VENDOR_SIGNATURES: dict[str, set[str]] = {
    "aviat": {"Event", "Object", "Site", "Raised", "Event ID", "Device Raised"},
    "cambium": {"Source", "Message", "Source Type", "Name", "Raised Time", "Duration (Sec.)"},
}


def detect_vendor(row: Mapping[str, object]) -> str:
    raw_keys = {str(k).strip() for k in row.keys() if str(k).strip()}
    best_vendor, best_score = "unknown", 0
    for vendor, signature_cols in _VENDOR_SIGNATURES.items():
        score = len(signature_cols & raw_keys)
        if score > best_score:
            best_vendor, best_score = vendor, score
    return best_vendor


# ---------------------------------------------------------------------------
# Shared parsing helpers
# ---------------------------------------------------------------------------

_SEVERITIES = {
    "critical": "critical",
    "major": "major",
    "minor": "minor",
    "warning": "warning",
    "indeterminate": "indeterminate",
    "cleared": "cleared",
}

_CLEARED_STATES = {
    "cleared",
    "clearedbynetwork",
    "clearedbyuser",
    "clear",
    "clearedbyalarmmanager",
}


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def _clean(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text in {"", "-", "--", "null", "None"} else text


def parse_timestamp(value: object) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
        for fmt in (
            "%d-%B-%Y %H:%M:%S",
            "%d-%b-%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%y %H:%M",
            "%m/%d/%Y %H:%M",
            "%d/%m/%y %H:%M",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed.astimezone(dt_timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _normal_fields(row: Mapping[str, object], aliases: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_name, raw_value in row.items():
        alias = aliases.get(_key(raw_name))
        if alias:
            normalized[alias] = _clean(raw_value)
    return normalized


def _stable_vendor_alarm_id(fields: Mapping[str, str]) -> str:
    supplied = fields.get("vendor_alarm_id")
    if supplied:
        return supplied
    # NOTE: "raised" intentionally excluded from the basis -- this is an
    # identity hash and must not change just because a timestamp changes.
    basis = "|".join(
        fields.get(name, "")
        for name in ("site", "event", "object")
    )
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
    return digest


# unique_id hashing intentionally excludes raised_at/cleared_at so the
# identifier does not change merely because those timestamps change.
def _event_digest(value: Mapping[str, object]) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Core normalize function -- vendor is detected, never passed in as a
# literal by the caller.
# ---------------------------------------------------------------------------

_VENDOR_NODE_PREFIXES: dict[str, str] = {
    "aviat": "AVT",
    "cambium": "CAM",
    "radwin": "RAD",
}

def normalize_alarm_row(
    row: Mapping[str, object],
    *,
    replay_cycle_id: str = "live",
    source_file: str = "",
    source_row: int | None = None,
    source: str = "alarm_csv",
) -> dict:
    """Return one JSON-safe normalized alarm envelope. Vendor is
    auto-detected from `row`'s column names -- never hardcoded."""

    vendor = detect_vendor(row)
    aliases = _FIELD_ALIASES_BY_VENDOR.get(vendor, {})

    fields = _normal_fields(row, aliases)
    site_id = fields.get("site", "")
    vendor_prefix = _VENDOR_NODE_PREFIXES.get(vendor, vendor.upper())
    node_id = f"{vendor_prefix}_{site_id}" if site_id else ""
    alarm_name = fields.get("event", "")
    state_raw = fields.get("state", "")
    state_key = _key(state_raw)
    cleared_at = parse_timestamp(fields.get("cleared"))
    raised_at = parse_timestamp(fields.get("raised"))
    event_type = "clear" if state_key in _CLEARED_STATES or cleared_at else "raise"
    state = "cleared" if event_type == "clear" else "active"
    severity_raw = fields.get("severity", "").lower()
    severity = "cleared" if event_type == "clear" else _SEVERITIES.get(severity_raw, "indeterminate")
    probable_cause = fields.get("probable_cause") or alarm_name
    category = categorize(alarm_name, probable_cause, fields.get("specific_problem"))
    vendor_alarm_id = _stable_vendor_alarm_id(fields)
    alarm_key = f"{vendor}:{vendor_alarm_id}"

    # identity_fields intentionally excludes raised_at/cleared_at -- the
    # unique_id must not change just because a timestamp changes.
    identity_fields = {
        "cycle": replay_cycle_id,
        "alarm_key": alarm_key,
        "event_type": event_type,
        "state": state,
        "severity": severity,
        "event": alarm_name,
        "object": fields.get("object", ""),
    }
    unique_id = f"{vendor}-{_event_digest(identity_fields)}"
    effective_at = cleared_at if event_type == "clear" and cleared_at else raised_at

    return {
        "schema_version": 1,
        "unique_id": unique_id,
        "alarm_key": alarm_key,
        "replay_cycle_id": replay_cycle_id or "live",
        "vendor": vendor,
        "external_alarm_id": vendor_alarm_id,
        "site_id": site_id,
        "node_id": node_id,
        "canonical_category": category,
        "probable_cause_raw": probable_cause,
        "severity": severity,
        "event_type": event_type,
        "state": state,
        "raised_at": _iso(raised_at),
        "cleared_at": _iso(cleared_at),
        "effective_at": _iso(effective_at),
        "payload": {"vendor_native": dict(row), "normalized_fields": fields},
    }


def normalize_raw_message(raw: Mapping[str, object], **kwargs) -> dict:
    if not isinstance(raw, Mapping):
        raise TypeError("raw alarm message must be an object")
    row: Mapping[str, object] = raw
    metadata = dict(kwargs)
    for wrapper in ("data", "record", "alarm"):
        candidate = raw.get(wrapper)
        if isinstance(candidate, Mapping):
            row = candidate
            break
    for key in ("replay_cycle_id", "source_file", "source_row", "source"):
        if key in raw and raw[key] not in (None, ""):
            metadata[key] = raw[key]
    envelope = normalize_alarm_row(row, **metadata)
    stream_id = raw.get("stream_id")
    if stream_id not in (None, ""):
        envelope["stream_id"] = str(stream_id)
    return envelope


# ---------------------------------------------------------------------------
# NiFi processor wrapper
# ---------------------------------------------------------------------------

class NormalizeAlarm(FlowFileTransform):
    """Normalize one raw alarm CSV row (JSON) from any supported vendor.

    Vendor is auto-detected per-row from the raw column names present
    (see `detect_vendor`) -- no per-processor or per-property vendor
    configuration is needed. Adding a new vendor requires only a new
    entry in `_VENDOR_SIGNATURES` and `_FIELD_ALIASES_BY_VENDOR`.

    Does NOT persist to Postgres -- that stays in the downstream Django
    worker/service. This processor only normalizes.
    """

    def __init__(self, jvm=None, **kwargs):
        super().__init__()

    class Java:
        implements = ["org.apache.nifi.python.processor.FlowFileTransform"]

    class ProcessorDetails:
        version = "1.0.0"
        description = (
            "Normalizes one raw alarm CSV row (JSON) into the AgenticNOC "
            "normalized alarm envelope. Vendor is auto-detected from the "
            "row's column names -- supports Aviat and Cambium out of the "
            "box. Persistence is NOT done here."
        )
        tags = ["agenticnoc", "alarm", "normalize", "telecom", "multi-vendor"]
        dependencies = []

    REPLAY_CYCLE_ID = PropertyDescriptor(
        name="Replay Cycle ID",
        description=(
            "Value for replay_cycle_id when not present as a FlowFile "
            "attribute named 'cycle_id'."
        ),
        default_value="live",
        required=False,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR],
    )

    def getPropertyDescriptors(self):
        return [self.REPLAY_CYCLE_ID]

    def transform(self, context, flowfile):
        raw_bytes = flowfile.getContentsAsBytes()
        row = json.loads(raw_bytes.decode("utf-8"))
        attributes = flowfile.getAttributes()
        replay_cycle_id = (
            attributes.get("cycle_id")
            or context.getProperty(self.REPLAY_CYCLE_ID).getValue()
            or "live"
        )
        source_file = attributes.get("source_file", "")
        source_row_raw = attributes.get("row_index")
        source_row = (
            int(source_row_raw)
            if source_row_raw is not None and str(source_row_raw).isdigit()
            else None
        )
        source = attributes.get("source", "nifi_python_processor")

        envelope = normalize_raw_message(
            row,
            replay_cycle_id=replay_cycle_id,
            source_file=source_file,
            source_row=source_row,
            source=source,
        )

        output_content = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
        output_attributes = {
            "unique_id": envelope["unique_id"],
            "alarm_key": envelope["alarm_key"],
            "vendor": envelope["vendor"],
            "site_id": envelope["site_id"],
            "severity": envelope["severity"],
            "event_type": envelope["event_type"],
            "canonical_category": envelope["canonical_category"],
            "mime.type": "application/json",
        }
        return FlowFileTransformResult(
            relationship="success",
            contents=output_content,
            attributes=output_attributes,
        )