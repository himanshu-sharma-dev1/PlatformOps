#!/usr/bin/env python3
"""Container-friendly, row-at-a-time CSV replay source for the HTTP NiFi flow.

The service intentionally has no cPlatform or AgenticNOC dependency.  It
reads the same two-preamble Aviat CSV shape as the supplied row-rate script,
POSTs one header+data row per request, and exposes lifecycle controls for a
container orchestrator or a test harness.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_TARGET_HOST = "localhost"
DEFAULT_TARGET_PORT = 9080
DEFAULT_TARGET_PATH = "aviat"
DEFAULT_BIND_HOST = "0.0.0.0"
DEFAULT_BIND_PORT = 8080
DEFAULT_RATE = 1.0
LIFECYCLE_PATHS = {
    "start": ("/start", "/api/start", "/api/v1/start"),
    "pause": ("/pause", "/api/pause", "/api/v1/pause"),
    "resume": ("/resume", "/api/resume", "/api/v1/resume"),
    "stop": ("/stop", "/api/stop", "/api/v1/stop"),
    "delete": ("/delete", "/api/delete", "/api/v1/delete"),
}
CONFIGURE_PATHS = ("/configure", "/api/configure", "/api/v1/configure")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _csv_payload(header: list[str], row: list[str]) -> bytes:
    """Return a valid two-line CSV document for one request.

    Several vendor ``CURRENT`` reports terminate the header with an unnamed
    column (a trailing comma).  Sending that empty field through a shared
    NiFi CSV reader is ambiguous when requests overlap: some records can be
    materialized as an empty map.  The unnamed value carries no alarm data, so
    remove matching trailing blank header/value pairs before serializing the
    one-row request.  Named vendor-specific columns, including a real
    ``Cleared`` column, are preserved.
    """

    header = list(header)
    row = list(row)
    while (
        len(header) > 1
        and not str(header[-1]).strip()
        and (len(row) < len(header) or not str(row[-1]).strip())
    ):
        header.pop()
        if row:
            row.pop()

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerow(row)
    return output.getvalue().encode("utf-8")


@dataclass
class SimulatorConfig:
    input_dir: Path = Path(os.environ.get("SIMULATOR_INPUT_DIR", "/data/incoming"))
    archive_dir: Path = Path(os.environ.get("SIMULATOR_ARCHIVE_DIR", "/data/sent"))
    target_url: str = os.environ.get(
        "SIMULATOR_NIFI_URL",
        f"http://{DEFAULT_TARGET_HOST}:{DEFAULT_TARGET_PORT}/{DEFAULT_TARGET_PATH}",
    )
    rate: float = float(os.environ.get("SIMULATOR_RATE", str(DEFAULT_RATE)))
    continuous: bool = os.environ.get("SIMULATOR_CONTINUOUS", "true").lower() not in {"0", "false", "no"}
    archive_after_send: bool = os.environ.get("SIMULATOR_MOVE_AFTER_SEND", "false").lower() in {"1", "true", "yes"}
    file_delay_seconds: float = float(os.environ.get("SIMULATOR_FILE_DELAY_SECONDS", "3"))
    idle_delay_seconds: float = float(os.environ.get("SIMULATOR_IDLE_DELAY_SECONDS", "1"))
    request_timeout_seconds: float = float(os.environ.get("SIMULATOR_REQUEST_TIMEOUT_SECONDS", "60"))
    file_pattern: str = os.environ.get("SIMULATOR_FILE_PATTERN", "*.csv")
    cycle_id: str = os.environ.get("SIMULATOR_CYCLE_ID", "")
    stream_id: str = os.environ.get("SIMULATOR_STREAM_ID", "")
    vendor: str = os.environ.get("SIMULATOR_VENDOR", "aviat")
    source_system: str = os.environ.get("SIMULATOR_SOURCE_SYSTEM", "cplatform-http-simulator")

    def validate(self) -> None:
        if self.rate <= 0:
            raise ValueError("rate must be greater than 0")
        if self.file_delay_seconds < 0 or self.idle_delay_seconds < 0:
            raise ValueError("delay values cannot be negative")
        if not self.target_url.startswith(("http://", "https://")):
            raise ValueError("target_url must use http:// or https://")
        if not self.source_system.strip():
            raise ValueError("source_system must not be empty")
        if self.vendor.strip().lower() not in {"aviat", "cambium", "radwin", "ceragon"}:
            raise ValueError("vendor must be aviat, cambium, radwin, or ceragon")


@dataclass
class Metrics:
    state: str = "stopped"
    rows_sent: int = 0
    rows_failed: int = 0
    files_sent: int = 0
    files_seen: int = 0
    cycle: int = 0
    current_file: str = ""
    current_row: int | None = None
    last_error: str = ""
    last_sent_at: str = ""
    started_at: str = ""
    stopped_at: str = ""
    last_status_code: int | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self, config: SimulatorConfig) -> dict:
        with self._lock:
            return {
                "state": self.state,
                "rows_sent": self.rows_sent,
                "rows_failed": self.rows_failed,
                "files_sent": self.files_sent,
                "files_seen": self.files_seen,
                "cycle": self.cycle,
                "current_file": self.current_file,
                "current_row": self.current_row,
                "last_error": self.last_error,
                "last_sent_at": self.last_sent_at,
                "started_at": self.started_at,
                "stopped_at": self.stopped_at,
                "last_status_code": self.last_status_code,
                "rate": config.rate,
                "continuous": config.continuous,
                "archive_after_send": config.archive_after_send,
                "input_dir": str(config.input_dir),
                "archive_dir": str(config.archive_dir),
                "target_url": config.target_url,
                "cycle_id": config.cycle_id,
                "stream_id": config.stream_id,
                "vendor": config.vendor,
                "source_system": config.source_system,
            }


Sender = Callable[[bytes, str, int, str], int]


def post_row(
    target_url: str,
    payload: bytes,
    source_file: str,
    row_number: int,
    timeout: float,
    *,
    cycle_id: str = "",
    stream_id: str = "",
    replay_sequence: int | None = None,
    vendor: str = "aviat",
    source_system: str = "",
) -> int:
    headers = {
        "Content-Type": "text/csv",
        "X-Original-Filename": source_file,
        "X-Row-Number": str(row_number),
    }
    if cycle_id:
        headers["X-Replay-Cycle-ID"] = cycle_id
    if stream_id:
        headers["X-Stream-ID"] = stream_id
    if replay_sequence is not None:
        headers["X-Replay-Sequence"] = str(replay_sequence)
    if vendor:
        headers["X-Vendor"] = vendor
    if source_system:
        headers["X-Source-System"] = source_system
    request = Request(target_url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
            return int(response.status)
    except (HTTPError, URLError, TimeoutError) as exc:
        detail = getattr(exc, "read", lambda: b"")()
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {target_url} failed: {detail or exc}") from exc


class Simulator:
    """Thread-safe lifecycle wrapper around the row replay loop."""

    def __init__(self, config: SimulatorConfig | None = None, sender: Sender | None = None):
        self.config = config or SimulatorConfig()
        self.config.validate()
        self.metrics = Metrics()
        self._sender = sender
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pause_requested = False

    def status(self) -> dict:
        return self.metrics.snapshot(self.config)

    @staticmethod
    def _as_bool(value, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off"}

    def configure(self, payload: Mapping[str, object] | None = None) -> dict:
        """Apply an idempotent replay configuration before the next start.

        Configuration is deliberately rejected while a replay thread is
        active; callers can stop, configure, and start again without racing
        the source loop or changing the cycle headers mid-file.
        """

        values = dict(payload or {})
        with self._condition:
            if self._thread and self._thread.is_alive() and not self._stop.is_set():
                raise RuntimeError("simulator must be stopped before configuration")

            current = self.config
            rate_value = values.get("rate")
            if rate_value is None or rate_value == "":
                rate_value = values.get("events_per_second")
            if rate_value is None or rate_value == "":
                rate_value = current.rate
            candidate = replace(
                current,
                input_dir=Path(str(values.get("input_dir") or values.get("source_path") or current.input_dir)),
                archive_dir=Path(str(values.get("archive_dir") or values.get("archive_path") or current.archive_dir)),
                target_url=str(values.get("target_url") or values.get("nifi_url") or current.target_url),
                rate=float(rate_value),
                continuous=self._as_bool(values.get("continuous"), current.continuous),
                archive_after_send=self._as_bool(
                    values.get("archive_after_send", values.get("move_after_send")),
                    current.archive_after_send,
                ),
                file_pattern=str(values.get("file_pattern") or current.file_pattern),
                cycle_id=str(values.get("cycle_id") or current.cycle_id),
                stream_id=str(values.get("stream_id") or current.stream_id),
                vendor=str(values.get("vendor") or current.vendor).strip().lower(),
                source_system=str(values.get("source_system") or current.source_system),
            )
            candidate.validate()
            self.config = candidate
            result = self.status()
            result["configured"] = True
            return result

    def start(self) -> dict:
        with self._condition:
            if self._thread and self._thread.is_alive():
                if self._pause_requested:
                    self._pause_requested = False
                    self.metrics.state = "running"
                    self._condition.notify_all()
                return self.status()
            self._stop.clear()
            self._pause_requested = False
            self.metrics.state = "running"
            self.metrics.started_at = _utc_now()
            self.metrics.stopped_at = ""
            self._thread = threading.Thread(target=self._run, name="alarm-simulator", daemon=True)
            self._thread.start()
            return self.status()

    def pause(self) -> dict:
        with self._condition:
            if self._thread and self._thread.is_alive() and not self._stop.is_set():
                self._pause_requested = True
                self.metrics.state = "paused"
            return self.status()

    def resume(self) -> dict:
        with self._condition:
            if self._thread and self._thread.is_alive() and not self._stop.is_set():
                self._pause_requested = False
                self.metrics.state = "running"
                self._condition.notify_all()
            return self.status()

    def stop(self) -> dict:
        with self._condition:
            self._stop.set()
            self._pause_requested = False
            self._condition.notify_all()
            self.metrics.state = "stopped"
            self.metrics.stopped_at = _utc_now()
            return self.status()

    def delete(self) -> dict:
        """Stop replay and expose the cPlatform delete terminal state."""

        with self._condition:
            self._stop.set()
            self._pause_requested = False
            self._condition.notify_all()
            self.metrics.state = "deleted"
            self.metrics.stopped_at = _utc_now()
            return self.status()

    def _wait(self, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        with self._condition:
            while not self._stop.is_set():
                if self._pause_requested:
                    self.metrics.state = "paused"
                    self._condition.wait(0.2)
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return True
                self._condition.wait(min(remaining, 0.2))
        return False

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                files = sorted(self.config.input_dir.glob(self.config.file_pattern))
                files = [path for path in files if path.is_file() and "alarm" in path.name.lower()]
                with self.metrics._lock:
                    self.metrics.files_seen = len(files)
                    self.metrics.cycle += 1
                if not files:
                    if not self.config.continuous:
                        break
                    if not self._wait(self.config.idle_delay_seconds):
                        break
                    continue
                for path in files:
                    if self._stop.is_set():
                        break
                    if not self._send_file(path):
                        # Keep the source in place for a later retry and move
                        # to the next file only after a bounded failure.
                        continue
                    if self.config.archive_after_send:
                        self._archive(path)
                    if not self._wait(self.config.file_delay_seconds):
                        break
                if not self.config.continuous:
                    break
        finally:
            with self._condition:
                if self.metrics.state != "stopped":
                    self.metrics.state = "stopped"
                self.metrics.stopped_at = _utc_now()
                self._condition.notify_all()

    def _send_file(self, path: Path) -> bool:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                lines = [line for line in handle.readlines() if line.strip()]
            if not lines:
                raise ValueError("file is empty")
            all_rows = list(csv.reader(lines))
            header_idx = 0
            for idx, r in enumerate(all_rows[:10]):
                columns = {str(c).strip().lower() for c in r if str(c).strip()}
                # A preamble often contains the word "alarm" (for example
                # ``Report type: alarm``), so one keyword is not enough to
                # identify the real CSV header.  Require two semantic column
                # families before treating a row as the header.
                identity_columns = {"site", "site_name", "device", "device_name", "ne_name", "source", "object"}
                event_columns = {"event", "event_id", "eventtext", "message", "alarm_id", "alarmid", "specificproblem"}
                state_columns = {"raised", "raised time", "raise_time", "severity", "state", "alarm status", "alarmstate", "clear_time", "cleared"}
                score = bool(columns & identity_columns) + bool(columns & event_columns) + bool(columns & state_columns)
                if score >= 2:
                    header_idx = idx
                    break
            if header_idx >= len(all_rows) - 1:
                raise ValueError("file contains no data rows after header")
            header = all_rows[header_idx]
            data_rows = all_rows[header_idx + 1:]
            next_due = time.monotonic()
            for row_number, row in enumerate(data_rows, start=1):
                if self._stop.is_set():
                    return False
                if not self._wait(max(0.0, next_due - time.monotonic())):
                    return False
                with self.metrics._lock:
                    self.metrics.current_file = path.name
                    self.metrics.current_row = row_number
                payload = _csv_payload(header, row)
                status = (self._sender or self._default_sender)(payload, path.name, row_number, self.config.target_url)
                with self.metrics._lock:
                    self.metrics.rows_sent += 1
                    self.metrics.last_status_code = status
                    self.metrics.last_sent_at = _utc_now()
                next_due = max(next_due + (1.0 / self.config.rate), time.monotonic())
            with self.metrics._lock:
                self.metrics.files_sent += 1
            return True
        except Exception as exc:  # noqa: BLE001 - one bad row/file never kills the service
            with self.metrics._lock:
                self.metrics.rows_failed += 1
                self.metrics.last_error = str(exc)
            return False

    def _default_sender(self, payload: bytes, source_file: str, row_number: int, target_url: str) -> int:
        return post_row(
            target_url,
            payload,
            source_file,
            row_number,
            self.config.request_timeout_seconds,
            cycle_id=self.config.cycle_id,
            stream_id=self.config.stream_id,
            replay_sequence=row_number,
            vendor=self.config.vendor,
            source_system=self.config.source_system,
        )

    def _archive(self, path: Path) -> None:
        self.config.archive_dir.mkdir(parents=True, exist_ok=True)
        target = self.config.archive_dir / path.name
        if target.exists():
            target = self.config.archive_dir / f"{path.stem}.cycle-{self.metrics.cycle}{path.suffix}"
        shutil.move(str(path), str(target))


class Handler(BaseHTTPRequestHandler):
    simulator: Simulator

    def _respond(self, status: int, payload: object) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path.split("?", 1)[0].rstrip("/") in {"/status", "/api/status", "/api/v1/status"}:
            self._respond(200, self.simulator.status())
            return
        if self.path.rstrip("/") == "/metrics":
            status = self.simulator.status()
            lines = [
                "# HELP noc_simulator_rows_sent Number of rows accepted by NiFi.",
                "# TYPE noc_simulator_rows_sent counter",
                f"noc_simulator_rows_sent {status['rows_sent']}",
                "# TYPE noc_simulator_rows_failed counter",
                f"noc_simulator_rows_failed {status['rows_failed']}",
                "# TYPE noc_simulator_files_sent counter",
                f"noc_simulator_files_sent {status['files_sent']}",
            ]
            body = ("\n".join(lines) + "\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._respond(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        path = self.path.split("?", 1)[0].rstrip("/")
        if path in CONFIGURE_PATHS:
            try:
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                if content_length < 0:
                    raise ValueError("Content-Length must not be negative")
                body = self.rfile.read(content_length) if content_length else b"{}"
                payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("configure body must be a JSON object")
                self._respond(200, self.simulator.configure(payload))
            except RuntimeError as exc:
                self._respond(409, {"error": str(exc)})
            except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._respond(400, {"error": str(exc)})
            return
        action = None
        for name, paths in LIFECYCLE_PATHS.items():
            if path in paths:
                action = getattr(self.simulator, name)
                break
        if action is None:
            self._respond(404, {"error": "not found"})
            return
        self._respond(200, action())

    def log_message(self, format: str, *args: object) -> None:
        return


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=SimulatorConfig.input_dir)
    parser.add_argument("--archive-dir", type=Path, default=SimulatorConfig.archive_dir)
    parser.add_argument("--host", default=DEFAULT_TARGET_HOST, help="NiFi host (same meaning as the supplied row-rate script)")
    parser.add_argument("--port", type=int, default=DEFAULT_TARGET_PORT, help="NiFi port (same meaning as the supplied row-rate script)")
    parser.add_argument("--path", default=DEFAULT_TARGET_PATH, help="NiFi ListenHTTP path")
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE)
    parser.add_argument("--listen-host", default=DEFAULT_BIND_HOST)
    parser.add_argument("--listen-port", type=int, default=DEFAULT_BIND_PORT)
    parser.add_argument("--continuous", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--move-after-send", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--file-delay", type=float, default=3.0)
    parser.add_argument("--idle-delay", type=float, default=1.0)
    parser.add_argument("--autostart", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _args()
    config = SimulatorConfig(
        input_dir=args.input_dir,
        archive_dir=args.archive_dir,
        target_url=f"http://{args.host}:{args.port}/{args.path.strip('/')}",
        rate=args.rate,
        continuous=args.continuous,
        archive_after_send=args.move_after_send,
        file_delay_seconds=args.file_delay,
        idle_delay_seconds=args.idle_delay,
    )
    simulator = Simulator(config)
    if args.autostart:
        simulator.start()
    Handler.simulator = simulator
    server = ThreadingHTTPServer((args.listen_host, args.listen_port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        simulator.stop()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
