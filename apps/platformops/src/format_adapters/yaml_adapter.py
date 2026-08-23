import yaml
from typing import Any, Dict, List, Optional, Tuple
from .base_adapter import BaseFormatAdapter


class YamlFormatAdapter(BaseFormatAdapter):
    format_name: str = "yaml"
    file_extensions: List[str] = [".yaml", ".yml"]

    def parse(self, text: str) -> Tuple[bool, Optional[Any], str]:
        if not text or not text.strip():
            return True, {}, ""
        try:
            parsed = yaml.safe_load(text)
            return True, parsed if parsed is not None else {}, ""
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            loc = f" on line {mark.line + 1} col {mark.column + 1}" if mark else ""
            return False, None, f"YAML Syntax Error{loc}: {str(e)}"
        except Exception as e:
            return False, None, f"YAML Parse Error: {str(e)}"

    def dump(self, data: Any) -> Tuple[bool, str, str]:
        try:
            rendered = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
            return True, rendered, ""
        except Exception as e:
            return False, "", f"YAML Serialization Error: {str(e)}"

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        ok, data, err = self.parse(text)
        if not ok:
            return False, err, {"format": "yaml", "valid": False, "error": err}
        keys = list(data.keys()) if isinstance(data, dict) else []
        return True, "Valid YAML configuration", {
            "format": "yaml",
            "valid": True,
            "keys_count": len(keys),
            "keys": keys[:20],
        }
