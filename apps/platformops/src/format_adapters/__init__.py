from typing import Dict
from .base_adapter import BaseFormatAdapter
from .json_adapter import JsonFormatAdapter
from .yaml_adapter import YamlFormatAdapter
from .redis_conf_adapter import RedisConfFormatAdapter
from .ini_adapter import IniFormatAdapter
from .properties_adapter import PropertiesFormatAdapter
from .xml_adapter import XmlFormatAdapter
from .raw_adapter import RawFormatAdapter

_ADAPTERS: Dict[str, BaseFormatAdapter] = {
    "json": JsonFormatAdapter(),
    "yaml": YamlFormatAdapter(),
    "yml": YamlFormatAdapter(),
    "redis-conf": RedisConfFormatAdapter(),
    "redis": RedisConfFormatAdapter(),
    "ini": IniFormatAdapter(),
    "cfg": IniFormatAdapter(),
    "properties": PropertiesFormatAdapter(),
    "props": PropertiesFormatAdapter(),
    "xml": XmlFormatAdapter(),
    "raw": RawFormatAdapter(),
}


def get_adapter(format_name: str) -> BaseFormatAdapter:
    """
    Retrieve the appropriate format adapter for a given format string.
    Falls back to RawFormatAdapter if format is unknown.
    """
    norm = str(format_name or "raw").strip().lower()
    return _ADAPTERS.get(norm, _ADAPTERS["raw"])


__all__ = [
    "BaseFormatAdapter",
    "JsonFormatAdapter",
    "YamlFormatAdapter",
    "RedisConfFormatAdapter",
    "IniFormatAdapter",
    "PropertiesFormatAdapter",
    "XmlFormatAdapter",
    "RawFormatAdapter",
    "get_adapter",
]
