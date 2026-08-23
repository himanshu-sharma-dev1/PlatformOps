import configparser
import io
from typing import Any, Dict, List, Optional, Tuple
from .base_adapter import BaseFormatAdapter


class IniFormatAdapter(BaseFormatAdapter):
    """
    Adapter for INI and CFG configuration files (e.g. Airflow airflow.cfg).
    """
    format_name: str = "ini"
    file_extensions: List[str] = [".ini", ".cfg", ".conf"]

    def parse(self, text: str) -> Tuple[bool, Optional[Any], str]:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(text)
            data = {sec: dict(parser.items(sec)) for sec in parser.sections()}
            return True, data, ""
        except configparser.Error as e:
            return False, None, f"INI Syntax Error: {str(e)}"
        except Exception as e:
            return False, None, f"INI Parse Error: {str(e)}"

    def dump(self, data: Any) -> Tuple[bool, str, str]:
        if not isinstance(data, dict):
            return False, "", "INI configuration data must be a nested dictionary of sections"
        parser = configparser.ConfigParser(interpolation=None)
        try:
            for sec, options in data.items():
                parser.add_section(sec)
                if isinstance(options, dict):
                    for opt, val in options.items():
                        parser.set(sec, opt, str(val))
            buf = io.StringIO()
            parser.write(buf)
            return True, buf.getvalue(), ""
        except Exception as e:
            return False, "", f"INI Serialization Error: {str(e)}"

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        ok, data, err = self.parse(text)
        if not ok:
            return False, err, {"format": "ini", "valid": False, "error": err}
        return True, "Valid INI configuration", {
            "format": "ini",
            "valid": True,
            "sections_count": len(data or {}),
            "sections": list((data or {}).keys())[:10],
        }
