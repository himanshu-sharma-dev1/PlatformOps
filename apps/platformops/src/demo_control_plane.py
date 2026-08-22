"""Small, deterministic control-plane contract for the AgenticNOC alarm stream.

The production cPlatform has a large collection of data-flow integrations.  The
MVP needs a deliberately smaller surface: a file source (FTP or a local path),
a single HTTP-v2 AgenticNOC pipeline, and a replay loop that emits rows to
NiFi.  Keeping the contract here (without importing Django, Celery, or a Kafka
client) makes it usable by the API, bootstrap scripts, and offline acceptance
tests alike.

The HTTP-v2 path owns canonicalization at the NiFi/AgenticNOC boundary and
publishes the normalized event through the PostgreSQL outbox.  The raw topic is
retained as legacy metadata for the separate local/FTP Kafka flow.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Optional
from urllib.parse import urlparse


RAW_ALARM_TOPIC = "noc.alarm.raw.v1"
NORMALIZED_ALARM_TOPIC = "noc.alarm.normalized.v1"
CANDIDATE_INCIDENT_TOPIC = "noc.incident.candidate.v1"
ALARM_DLQ_TOPIC = "noc.alarm.dlq.v1"
V2_EVENT_TOPIC = "noc.alarm.events.v2"
CONTRACT_VERSION = "noc-alarm-stream.v1"
LEGACY_CONTRACT_VERSION = "noc-alarm-demo.v1"
DEFAULT_EPS = 100
MIN_EPS = 1
MAX_EPS = 1000
DEFAULT_KAFKA_BOOTSTRAP = "kafka:9092"
DEFAULT_METRICS_LINK = "/PlatformIO/Monitoring/Performance/"
SIMULATOR_KIND = "cplatform-replay"
CONTROL_ACTIONS = ("start", "pause", "resume", "stop", "delete")
HTTP_FLOW_NAME = "noc-alarm-http-to-agenticnoc-v1"
LEGACY_FLOW_NAME = "noc-alarm-ftp-local-to-kafka"
UI_DEMO_FLOW_NAME = "aviat_ui_demo_2-noc-alarm"
UI_DEMO_FLOW_FILE = "aviat_ui_demo_2-noc-alarm.json"
HTTP_LISTEN_PORT = 9080
HTTP_BASE_PATH = "aviat"
AGENTICNOC_INGEST_PATH = "/api/ingestion/v2/alarms/"
SUPPORTED_NOC_VENDORS = ("aviat", "cambium", "radwin", "ceragon")
# The local demo simulator is a registered cPlatform-network peer, not a
# second user-facing service.  Keep this fallback explicit so a stream created
# from the UI contains a usable controller URL even when the cPlatform
# container was started without the optional environment variable.
DEFAULT_SIMULATOR_URL = "http://180.75.0.80:8080"

DEMO_KAFKA_TOPICS = (
    {"name": RAW_ALARM_TOPIC, "partitions": 3, "retention_ms": 86_400_000},
    {"name": NORMALIZED_ALARM_TOPIC, "partitions": 3, "retention_ms": 86_400_000},
    {"name": CANDIDATE_INCIDENT_TOPIC, "partitions": 3, "retention_ms": 86_400_000},
    {"name": ALARM_DLQ_TOPIC, "partitions": 3, "retention_ms": 604_800_000},
    {"name": V2_EVENT_TOPIC, "partitions": 3, "retention_ms": 86_400_000},
)


class ContractValidationError(ValueError):
    """Raised when a control-plane request cannot be represented safely."""

    def __init__(self, message: str, *, field: str = "") -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class ReplayRecord:
    """One raw Kafka value plus metadata that belongs in Kafka headers."""

    stream_id: str
    cycle_id: str
    row_index: int
    value: str
    source: str = "cplatform_control_plane"
    source_file: str = ""

    @property
    def headers(self) -> dict[str, str]:
        return {
            "stream_id": self.stream_id,
            "cycle_id": self.cycle_id,
            "row_index": str(self.row_index),
            "content_type": "application/json",
            "source": self.source,
            "source_file": self.source_file,
        }

    def as_dict(self) -> dict[str, Any]:
        """Return a serializer-friendly representation for API/tests."""

        return {
            "stream_id": self.stream_id,
            "cycle_id": self.cycle_id,
            "row_index": self.row_index,
            "value": self.value,
            "source": self.source,
            "source_file": self.source_file,
            "headers": self.headers,
        }


def _first(payload: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None and value != "":
            return value
    return default


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ContractValidationError("must be a boolean", field="continuous")


def _eps(value: Any) -> int:
    if value is None or value == "":
        return DEFAULT_EPS
    if isinstance(value, bool):
        raise ContractValidationError("must be an integer from 1 to 1000", field="eps")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("must be an integer from 1 to 1000", field="eps") from exc
    if parsed < MIN_EPS or parsed > MAX_EPS:
        raise ContractValidationError("must be between 1 and 1000", field="eps")
    return parsed


def _slug(value: Any) -> str:
    result = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip()).strip("-")
    return result.lower() or "stream"


def _normalize_simulator_url(value: Any) -> str:
    """Normalize a simulator base URL while accepting status-URL env values."""

    value = str(value or "").strip().rstrip("/")
    for suffix in ("/api/v1/status", "/api/status", "/status"):
        if value.endswith(suffix):
            return value[: -len(suffix)].rstrip("/")
    return value


def _source_type(payload: Mapping[str, Any]) -> str:
    source = _first(payload, "source_type", "source", "conn_type", "connection_type", default="LOCAL")
    normalized = str(source).strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"ftp", "ftp_server"}:
        return "ftp"
    if normalized in {"local", "local_path", "filesystem", "file", "path"}:
        return "local_path"
    if normalized in {"endpoint", "http_endpoint", "http", "listen_http", "websocket", "sse"}:
        return "endpoint"
    raise ContractValidationError("must be FTP, LOCAL, or ENDPOINT", field="source_type")


def _source_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    source_type = _source_type(payload)
    conn_info = payload.get("conn_info")
    if not isinstance(conn_info, Mapping):
        conn_info = {}

    def value(*keys: str, default: Any = None) -> Any:
        direct = _first(payload, *keys)
        return direct if direct is not None else _first(conn_info, *keys, default=default)

    if source_type == "ftp":
        url = value("url", "ftp_url", "ftpUrl")
        remote_path = value("remote_path", "ftp_remote_path", "ftpRemotePath", "path")
        if not url:
            raise ContractValidationError("is required for FTP sources", field="url")
        parsed = urlparse(str(url))
        if parsed.scheme.lower() not in {"ftp", "ftps"} or not parsed.hostname:
            raise ContractValidationError("must be an ftp:// or ftps:// URL", field="url")
        if not remote_path:
            remote_path = parsed.path or "/"
        return {
            "type": "ftp",
            "url": str(url),
            "host": parsed.hostname,
            "port": parsed.port or (990 if parsed.scheme.lower() == "ftps" else 21),
            "secure": parsed.scheme.lower() == "ftps",
            "username": value("username", "user_name", "ftp_username", "ftpUsername", default=""),
            "password": value("password", "ftp_password", "ftpPassword", default=""),
            "remote_path": str(remote_path),
            "file_pattern": str(value("file_pattern", "filename", "ftp_file_name", "ftpFileName", default="*")),
        }

    if source_type == "endpoint":
        endpoint_url = value("endpoint_url", "endpointUrl", "url", default="")
        listen_port = value("nifi_listen_port", "listen_port", "nifiListenPort", default=HTTP_LISTEN_PORT)
        base_path = str(value("nifi_base_path", "base_path", "nifiBasePath", default=HTTP_BASE_PATH)).strip().strip("/")
        if not base_path:
            raise ContractValidationError("is required for endpoint sources", field="base_path")
        try:
            listen_port = int(listen_port)
        except (TypeError, ValueError) as exc:
            raise ContractValidationError("must be a valid TCP port", field="listen_port") from exc
        if listen_port < 1 or listen_port > 65535:
            raise ContractValidationError("must be between 1 and 65535", field="listen_port")
        return {
            "type": "endpoint",
            "endpoint_url": str(endpoint_url),
            "protocol": str(value("endpoint_protocol", "endpointProtocol", "protocol", default="http")).strip() or "http",
            "listen_port": listen_port,
            "base_path": base_path,
        }

    path = value("path", "local_path", "localPath", "source_path", "ftpDestPath")
    if not path:
        raise ContractValidationError("is required for local path sources", field="path")
    return {
        "type": "local_path",
        "path": str(path),
        "file_pattern": str(value("file_pattern", "filename", "file_name", "localFilePattern", default="*")),
    }


def _vendor(payload: Mapping[str, Any]) -> str:
    """Return the canonical vendor for a NOC alarm stream.

    The transport is vendor-neutral, but the adapter selected by AgenticNOC
    is not.  Keeping this small allow-list in the control-plane contract makes
    the selected adapter visible to the simulator/NiFi flow and prevents a
    typo from silently classifying every row as ``unknown``.
    """

    value = _first(payload, "vendor", "vendor_name", "alarm_vendor", default="aviat")
    normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "aviat_networks": "aviat",
        "cambium_networks": "cambium",
        "radwin_networks": "radwin",
        "ceragon_networks": "ceragon",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_NOC_VENDORS:
        raise ContractValidationError(
            f"must be one of {', '.join(SUPPORTED_NOC_VENDORS)}", field="vendor"
        )
    return normalized


def new_cycle_id(stream_id: str, cycle_number: int) -> str:
    """Build a unique, sortable cycle ID without embedding row data.

    The monotonic component is useful to operators, but NiFi's distributed
    duplicate cache outlives a cPlatform process and can contain entries from
    an earlier runtime/database state that used the same counter.  The short
    run token makes the cache namespace unique for every start while keeping
    the human-readable counter intact.
    """

    if cycle_number < 1:
        raise ValueError("cycle_number must be positive")
    run_token = uuid.uuid4().hex[:12]
    return f"{_slug(stream_id)}-cycle-{cycle_number:06d}-{run_token}"


def _metrics_contract(payload: Mapping[str, Any], base_url: str = "") -> dict[str, str]:
    explicit = _first(payload, "metrics_link", "metrics_url", "metricsUrl")
    if explicit:
        link = str(explicit)
    else:
        configured = os.environ.get("CPLATFORM_METRICS_URL", "").strip()
        link = configured or DEFAULT_METRICS_LINK
    if base_url and link.startswith("/"):
        link = base_url.rstrip("/") + link
    return {"link": link, "kind": "prometheus-compatible", "relation": "stream"}


def build_stream_contract(payload: Mapping[str, Any], *, base_url: str = "") -> dict[str, Any]:
    """Validate and normalize a demo stream request.

    ``payload`` accepts both the clean API names and the existing StreamIngress
    form names (for example ``ftpUrl`` and ``ftpRemotePath``).  Passwords are
    retained only in the source config because the legacy form already uses
    them; API callers should prefer a secret reference via ``password_ref``.
    """

    if not isinstance(payload, Mapping):
        raise ContractValidationError("request body must be an object")
    # A persisted dataflow edit carries both the database id and the human
    # stream name.  Prefer the explicit stream/name fields so an internal id
    # such as ``SDF10023`` does not accidentally become the replay identity.
    stream_id = _first(payload, "stream_id", "dataflow_name", "stream_name", "dataflow_id")
    if not stream_id:
        raise ContractValidationError("is required", field="stream_id")
    stream_id = _slug(stream_id)

    source = _source_contract(payload)
    vendor = _vendor(payload)
    eps = _eps(_first(payload, "eps", "events_per_second", "eventsPerSecond"))
    requested_mode = _first(payload, "replay_mode", "replayMode", "mode")
    if requested_mode not in (None, ""):
        replay_mode = str(requested_mode).strip().lower().replace("-", "_")
        if replay_mode not in {"one_shot", "continuous"}:
            raise ContractValidationError("must be one_shot or continuous", field="replay_mode")
        continuous = replay_mode == "continuous"
    else:
        continuous = _as_bool(_first(payload, "continuous", "continuous_replay", "continuousReplay"), default=True)
        replay_mode = "continuous" if continuous else "one_shot"
    requested_topic = str(_first(payload, "topic", "kafka_topic", "kafkaTopic", default="")).strip()
    if requested_topic and requested_topic not in {RAW_ALARM_TOPIC, NORMALIZED_ALARM_TOPIC}:
        raise ContractValidationError(
            f"must be {NORMALIZED_ALARM_TOPIC} for the HTTP-v2 flow",
            field="topic",
        )

    bootstrap_servers = str(
        _first(
            payload,
            "bootstrap_servers",
            "bootstrapServers",
            default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", DEFAULT_KAFKA_BOOTSTRAP),
        )
    ).strip()
    if not bootstrap_servers:
        raise ContractValidationError("must not be empty", field="bootstrap_servers")

    metrics = _metrics_contract(payload, base_url=base_url)
    # New AgenticNOC stream registrations use the UI-exported Aviat NiFi flow
    # when present. The reviewed HTTP flow remains the stable fallback and
    # legacy FTP/local Kafka groups remain addressable for persisted contracts.
    flow_name = str(
        _first(
            payload,
            "nifi_flow_name",
            "nifiFlowName",
            default=os.environ.get("NOC_NIFI_FLOW_NAME", UI_DEMO_FLOW_NAME),
        )
    ).strip() or HTTP_FLOW_NAME
    flow_file = str(
        _first(
            payload,
            "nifi_flow_file",
            "nifiFlowFile",
            default=os.environ.get("NOC_NIFI_FLOW_FILE", UI_DEMO_FLOW_FILE),
        )
    ).strip()
    simulator_url = _normalize_simulator_url(
        _first(
            payload,
            "simulator_url",
            "simulatorUrl",
            default=(
                os.environ.get("NOC_SIMULATOR_URL")
                or os.environ.get("NOC_SIMULATOR_BASE_URL")
                or os.environ.get("SIMULATOR_URL")
                or DEFAULT_SIMULATOR_URL
            ),
        )
    )
    agenticnoc_ingest_url = str(
        _first(
            payload,
            "agenticnoc_ingest_url",
            "agenticnocIngestUrl",
            default=os.environ.get("AGENTICNOC_INGEST_URL", ""),
        )
        or ""
    ).strip()
    if not agenticnoc_ingest_url:
        agenticnoc_ingest_url = f"http://180.75.0.7:8000{AGENTICNOC_INGEST_PATH}"
    headers = [
        "stream_id",
        "cycle_id",
        "row_index",
        "content_type",
        "source",
        "source_file",
        "replay_mode",
    ]
    return {
        "contract_version": CONTRACT_VERSION,
        "stream_id": stream_id,
        "vendor": vendor,
        "source": source,
        "replay": {
            "events_per_second": eps,
            "continuous": continuous,
            "mode": replay_mode,
            "cycle_id_header": "cycle_id",
            "cycle_id_strategy": "monotonic",
            "start_cycle": 1,
        },
        "kafka": {
            "bootstrap_servers": bootstrap_servers,
            # The primary topic is the one whose watermark and lag represent
            # this HTTP-v2 flow.  Keep raw_topic for legacy-flow diagnostics.
            "topic": NORMALIZED_ALARM_TOPIC,
            "raw_topic": RAW_ALARM_TOPIC,
            "normalized_topic": NORMALIZED_ALARM_TOPIC,
            "candidate_topic": CANDIDATE_INCIDENT_TOPIC,
            "dlq_topic": ALARM_DLQ_TOPIC,
            "v2_topic": V2_EVENT_TOPIC,
            "value_format": "canonical-v2-json-after-outbox",
            "acks": "all",
        },
        "nifi": {
            "vendor": vendor,
            "controller": "cplatform",
            "transport": "http",
            "flow_version": "1",
            "flow_name": flow_name,
            "flow_file": flow_file,
            "legacy_flow_name": LEGACY_FLOW_NAME,
            "listen_port": int(source.get("listen_port") or HTTP_LISTEN_PORT),
            # NiFi exposes one shared compatibility endpoint.  Vendor choice
            # is carried by X-Vendor and the canonical envelope, so a new
            # Cambium/Radwin/Ceragon stream must not invent a path that the
            # single ListenHTTP processor does not serve.
            "base_path": str(source.get("base_path") or HTTP_BASE_PATH).strip("/"),
            "agenticnoc_ingest_url": agenticnoc_ingest_url,
            "raw_topic": RAW_ALARM_TOPIC,
            "normalized_topic": NORMALIZED_ALARM_TOPIC,
            "candidate_topic": CANDIDATE_INCIDENT_TOPIC,
            "dlq_topic": ALARM_DLQ_TOPIC,
            "outbox": "postgresql_transactional",
            "publishes_raw_row_json": False,
            "publishes_canonical_alarm_json": True,
            "metadata_headers": headers,
            "control_actions": list(CONTROL_ACTIONS),
        },
        "simulator": {
            "kind": SIMULATOR_KIND,
            "controller": "cplatform",
            "stream_id": stream_id,
            "vendor": vendor,
            "url": simulator_url,
            "lifecycle": {
                "start": "/start",
                "pause": "/pause",
                "resume": "/resume",
                "stop": "/stop",
                "delete": "/delete",
            },
            "source_type": source["type"],
            "events_per_second": eps,
            "continuous": continuous,
            "mode": replay_mode,
            "publishes_raw_row_json": True,
            "metadata_headers": headers,
            "control_actions": list(CONTROL_ACTIONS),
        },
        "metrics": metrics,
    }


def kafka_catalog(*, bootstrap_servers: str = DEFAULT_KAFKA_BOOTSTRAP) -> dict[str, Any]:
    """Return the catalog entry used by the single-node KRaft demo broker."""

    return {
        "service_type": "InfraKafkaCore",
        "display_name": "Kafka Core (single-node KRaft)",
        "category": "stream",
        "mode": "single-node",
        "controller": "KRaft",
        "version": "3.8.1",
        "bootstrap_servers": bootstrap_servers,
        "advertised_listener": bootstrap_servers,
        "listeners": {"client": 9092, "controller": 9093},
        "topics": [
            {
                "name": topic["name"],
                "partitions": topic["partitions"],
                "replication_factor": 1,
                "retention_ms": topic["retention_ms"],
            }
            for topic in DEMO_KAFKA_TOPICS
        ],
        "contract": {
            "key_format": "stream_id",
            "v2_topic": V2_EVENT_TOPIC,
            "value_format": "raw-row-json",
            "required_headers": [
                "stream_id",
                "cycle_id",
                "row_index",
                "content_type",
                "source",
                "source_file",
            ],
        },
    }


def encode_raw_row(row: Any) -> str:
    """Serialize one source row as compact JSON without a platform envelope."""

    if isinstance(row, str):
        try:
            decoded = json.loads(row)
        except json.JSONDecodeError:
            decoded = row
    else:
        decoded = row
    try:
        return json.dumps(decoded, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"row is not JSON serializable: {exc}", field="row") from exc


def iter_replay_records(
    rows: Iterable[Any],
    stream_id: str,
    *,
    continuous: bool = True,
    cycles: Optional[int] = None,
    start_cycle: int = 1,
    source: str = "cplatform_control_plane",
    source_file: str = "",
) -> Iterator[ReplayRecord]:
    """Yield raw row records, replaying the source continuously when requested.

    Set ``cycles`` in tests or one-shot jobs to bound the iterator.  A
    continuous request without ``cycles`` intentionally remains open for the
    caller's scheduler to stop.
    """

    materialized = list(rows)
    if not materialized:
        raise ContractValidationError("must contain at least one row", field="rows")
    if start_cycle < 1:
        raise ContractValidationError("must be positive", field="start_cycle")
    if cycles is not None and cycles < 1:
        raise ContractValidationError("must be positive", field="cycles")
    if not continuous and cycles is None:
        cycles = 1

    cycle_number = start_cycle
    while cycles is None or cycle_number < start_cycle + cycles:
        cycle_id = new_cycle_id(stream_id, cycle_number)
        for row_index, row in enumerate(materialized):
            row_source_file = source_file
            if not row_source_file and isinstance(row, Mapping):
                row_source_file = str(row.get("source_file") or row.get("filename") or "")
            yield ReplayRecord(
                stream_id=_slug(stream_id),
                cycle_id=cycle_id,
                row_index=row_index,
                value=encode_raw_row(row),
                source=str(source),
                source_file=str(row_source_file),
            )
        cycle_number += 1


def replay_cycle(
    rows: Iterable[Any],
    stream_id: str,
    cycle_number: int = 1,
    *,
    source: str = "cplatform_control_plane",
    source_file: str = "",
) -> list[ReplayRecord]:
    """Convenience helper for a bounded cycle used by bootstrap smoke tests."""

    return list(
        iter_replay_records(
            rows,
            stream_id,
            continuous=False,
            cycles=1,
            start_cycle=cycle_number,
            source=source,
            source_file=source_file,
        )
    )


__all__ = [
    "CONTRACT_VERSION",
    "LEGACY_CONTRACT_VERSION",
    "ContractValidationError",
    "DEFAULT_EPS",
    "CONTROL_ACTIONS",
    "AGENTICNOC_INGEST_PATH",
    "HTTP_BASE_PATH",
    "HTTP_FLOW_NAME",
    "HTTP_LISTEN_PORT",
    "UI_DEMO_FLOW_FILE",
    "UI_DEMO_FLOW_NAME",
    "SUPPORTED_NOC_VENDORS",
    "LEGACY_FLOW_NAME",
    "MAX_EPS",
    "MIN_EPS",
    "RAW_ALARM_TOPIC",
    "NORMALIZED_ALARM_TOPIC",
    "ReplayRecord",
    "SIMULATOR_KIND",
    "build_stream_contract",
    "encode_raw_row",
    "iter_replay_records",
    "kafka_catalog",
    "new_cycle_id",
    "replay_cycle",
]
