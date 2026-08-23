from typing import Any, Dict, List, Optional, Tuple
from .base_adapter import BaseFormatAdapter


class RawFormatAdapter(BaseFormatAdapter):
    format_name: str = "raw"
    file_extensions: List[str] = [".txt", ".raw"]

    def parse(self, text: str) -> Tuple[bool, Optional[Any], str]:
        return True, text, ""

    def dump(self, data: Any) -> Tuple[bool, str, str]:
        return True, str(data), ""

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        return True, "Raw text configuration", {"format": "raw", "valid": True, "lines": len(text.splitlines())}

    def compute_semantic_diff(self, text1: str, text2: str) -> Dict[str, Any]:
        return {"supported": False, "summary": "Semantic comparison unavailable for raw unformatted text"}
