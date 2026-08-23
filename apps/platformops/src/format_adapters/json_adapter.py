import json
from typing import Any, Dict, List, Optional, Tuple
from .base_adapter import BaseFormatAdapter


class JsonFormatAdapter(BaseFormatAdapter):
    format_name: str = "json"
    file_extensions: List[str] = [".json", ".conf"]

    def parse(self, text: str) -> Tuple[bool, Optional[Any], str]:
        if not text or not text.strip():
            return True, {}, ""
        try:
            parsed = json.loads(text)
            return True, parsed, ""
        except json.JSONDecodeError as e:
            return False, None, f"JSON Syntax Error on line {e.lineno} col {e.colno}: {e.msg}"
        except Exception as e:
            return False, None, f"JSON Parse Error: {str(e)}"

    def dump(self, data: Any) -> Tuple[bool, str, str]:
        try:
            rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            return True, rendered, ""
        except Exception as e:
            return False, "", f"JSON Serialization Error: {str(e)}"

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        ok, data, err = self.parse(text)
        if not ok:
            return False, err, {"format": "json", "valid": False, "error": err}
        keys = list(data.keys()) if isinstance(data, dict) else []
        return True, "Valid JSON configuration", {
            "format": "json",
            "valid": True,
            "keys_count": len(keys),
            "keys": keys[:20],
        }
