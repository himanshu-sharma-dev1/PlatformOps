import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from .base_adapter import BaseFormatAdapter


class XmlFormatAdapter(BaseFormatAdapter):
    """
    Adapter for XML configuration files (e.g. ClickHouse config.xml).
    """
    format_name: str = "xml"
    file_extensions: List[str] = [".xml"]

    def parse(self, text: str) -> Tuple[bool, Optional[Any], str]:
        if not text or not text.strip():
            return True, {}, ""
        try:
            root = ET.fromstring(text)
            return True, {"tag": root.tag, "attrib": root.attrib}, ""
        except ET.ParseError as e:
            return False, None, f"XML Parse Error: {str(e)}"
        except Exception as e:
            return False, None, f"XML Error: {str(e)}"

    def dump(self, data: Any) -> Tuple[bool, str, str]:
        return False, "", "Direct structural serialization for XML is disabled; please submit formatted XML text"

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        if not text or not text.strip():
            return True, "Empty XML document", {"format": "xml", "valid": True}
        try:
            root = ET.fromstring(text)
            return True, f"Valid XML configuration (<{root.tag}>)", {
                "format": "xml",
                "valid": True,
                "root_tag": root.tag,
            }
        except ET.ParseError as e:
            return False, f"XML Syntax Error: {str(e)}", {"format": "xml", "valid": False, "error": str(e)}

    def compute_semantic_diff(self, text1: str, text2: str) -> Dict[str, Any]:
        return {"supported": False, "summary": "Semantic XML comparison requires custom DTD schema; unified diff is provided."}
