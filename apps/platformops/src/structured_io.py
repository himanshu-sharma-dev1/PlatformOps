"""Structured file, timestamp, copy, and diff helpers."""

import contextlib
import copy
import datetime as dt
import difflib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

class MigrationError(Exception):
    pass

def _deepcopy(data: Any) -> Any:
    return copy.deepcopy(data)


def _now_ts() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _load_structured_file(path: Path) -> Tuple[Any, str]:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
        if not isinstance(data, (dict, list)):
            raise MigrationError(f"{path} does not contain a JSON object or array")
        return data, "json"
    except json.JSONDecodeError:
        data = yaml.safe_load(raw)
        if not isinstance(data, (dict, list)):
            raise MigrationError(f"{path} does not contain a YAML mapping or list")
        return data, "yaml"


def _dump_structured(data: Any, file_format: str) -> str:
    if file_format == "json":
        return json.dumps(data, indent=2, sort_keys=True) + "\n"
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


def _normalized_text(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=True, default_flow_style=False)


def _diff_lines_for_value(data: Any) -> List[str]:
    if isinstance(data, str):
        return data.splitlines(keepends=True)
    return _normalized_text(data).splitlines(keepends=True)


def _unified_diff(before: Any, after: Any, before_name: str, after_name: str) -> str:
    return "".join(
        difflib.unified_diff(
            _diff_lines_for_value(before),
            _diff_lines_for_value(after),
            fromfile=before_name,
            tofile=after_name,
        )
    )


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, dict, str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return str(value)


def _write_atomic(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _write_json_report(path: Optional[str], payload: Dict[str, Any]) -> None:
    if not path:
        return
    report_path = Path(path)
    _write_atomic(report_path, json.dumps(payload, indent=2, sort_keys=True, default=_json_ready) + "\n")


__all__ = [
    "_deepcopy",
    "_now_ts",
    "_now_iso",
    "_load_structured_file",
    "_dump_structured",
    "_normalized_text",
    "_diff_lines_for_value",
    "_unified_diff",
    "_json_ready",
    "_write_atomic",
    "_write_json_report",
]
