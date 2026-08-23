from typing import Any, Dict, List, Optional, Tuple
from .base_adapter import BaseFormatAdapter


class PropertiesFormatAdapter(BaseFormatAdapter):
    """
    Adapter for Java-style properties files (e.g. Kafka server.properties, NiFi nifi.properties).
    """
    format_name: str = "properties"
    file_extensions: List[str] = [".properties", ".conf"]

    def parse(self, text: str) -> Tuple[bool, Optional[Any], str]:
        data = {}
        for idx, line in enumerate(text.splitlines(), start=1):
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("!"):
                continue
            if "=" in s:
                k, v = s.split("=", 1)
                data[k.strip()] = v.strip()
            elif ":" in s:
                k, v = s.split(":", 1)
                data[k.strip()] = v.strip()
            else:
                parts = s.split(None, 1)
                data[parts[0].strip()] = parts[1].strip() if len(parts) > 1 else ""
        return True, data, ""

    def dump(self, data: Any) -> Tuple[bool, str, str]:
        if not isinstance(data, dict):
            return False, "", "Properties configuration data must be a dictionary"
        lines = [f"{k}={v}" for k, v in data.items()]
        return True, "\n".join(lines) + "\n", ""

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        ok, data, err = self.parse(text)
        return True, "Valid properties configuration", {
            "format": "properties",
            "valid": True,
            "properties_count": len(data or {}),
        }
