from typing import Any, Dict, List, Optional, Tuple
from .base_adapter import BaseFormatAdapter


class RedisConfFormatAdapter(BaseFormatAdapter):
    """
    Adapter for Redis configuration files (key-value directives with space syntax).
    """
    format_name: str = "redis-conf"
    file_extensions: List[str] = [".conf"]

    def parse(self, text: str) -> Tuple[bool, Optional[Any], str]:
        data = {}
        for idx, line in enumerate(text.splitlines(), start=1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split(None, 1)
            if len(parts) == 1:
                data[parts[0]] = ""
            else:
                data[parts[0]] = parts[1].strip("'\"")
        return True, data, ""

    def dump(self, data: Any) -> Tuple[bool, str, str]:
        if not isinstance(data, dict):
            return False, "", "Redis configuration data must be a dictionary"
        lines = []
        for k, v in data.items():
            if str(v).strip():
                lines.append(f"{k} {v}")
            else:
                lines.append(str(k))
        return True, "\n".join(lines) + "\n", ""

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        for idx, line in enumerate(text.splitlines(), start=1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split(None, 1)
            if not parts[0].replace("-", "_").replace(".", "_").isalnum():
                return False, f"Invalid Redis directive on line {idx}: {parts[0]}", {
                    "format": "redis-conf",
                    "valid": False,
                    "line": idx,
                }
        ok, data, err = self.parse(text)
        return True, "Valid Redis configuration", {
            "format": "redis-conf",
            "valid": True,
            "directives_count": len(data or {}),
        }
