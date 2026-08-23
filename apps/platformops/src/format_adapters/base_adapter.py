import abc
import difflib
from typing import Any, Dict, List, Optional, Tuple


class BaseFormatAdapter(abc.ABC):
    """
    Abstract Base Class for service configuration format adapters.
    Each adapter provides parsing, serialization, validation, diffing, and merging.
    """

    format_name: str = "raw"
    file_extensions: List[str] = [".txt", ".conf"]

    @abc.abstractmethod
    def parse(self, text: str) -> Tuple[bool, Optional[Any], str]:
        """
        Parse raw configuration text into structured Python object.
        Returns: (success: bool, parsed_data: Any, error_message: str)
        """
        pass

    @abc.abstractmethod
    def dump(self, data: Any) -> Tuple[bool, str, str]:
        """
        Serialize structured Python object into formatted configuration string.
        Returns: (success: bool, text: str, error_message: str)
        """
        pass

    @abc.abstractmethod
    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate syntax and structure of configuration text.
        Returns: (is_valid: bool, error_message: str, details_dict: dict)
        """
        pass

    def diff(self, text1: str, text2: str, label1: str = "before", label2: str = "after") -> Dict[str, Any]:
        """
        Compute unified and semantic diff between two configuration versions.
        """
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)
        unified = "".join(difflib.unified_diff(lines1, lines2, fromfile=label1, tofile=label2))
        identical = (text1.strip() == text2.strip())

        semantic = self.compute_semantic_diff(text1, text2)

        return {
            "unified_diff": unified,
            "semantic_diff": semantic,
            "identical": identical,
        }

    def compute_semantic_diff(self, text1: str, text2: str) -> Dict[str, Any]:
        ok1, data1, _ = self.parse(text1)
        ok2, data2, _ = self.parse(text2)

        if not ok1 or not ok2 or not isinstance(data1, dict) or not isinstance(data2, dict):
            return {"supported": False, "summary": "Semantic comparison unavailable for non-dictionary format"}

        keys1 = set(data1.keys())
        keys2 = set(data2.keys())

        additions = {k: data2[k] for k in keys2 - keys1}
        removals = {k: data1[k] for k in keys1 - keys2}
        changes = {}
        unchanged = []

        for k in keys1 & keys2:
            if data1[k] != data2[k]:
                changes[k] = {"before": data1[k], "after": data2[k]}
            else:
                unchanged.append(k)

        return {
            "supported": True,
            "added_count": len(additions),
            "removed_count": len(removals),
            "changed_count": len(changes),
            "unchanged_count": len(unchanged),
            "additions": additions,
            "removals": removals,
            "changes": changes,
            "unchanged_keys": unchanged,
        }

    def merge(self, base_text: str, patch_data: Dict[str, Any]) -> Tuple[bool, str, str]:
        ok, data, err = self.parse(base_text)
        if not ok or not isinstance(data, dict):
            return False, "", f"Cannot merge into non-dictionary base configuration: {err}"

        data.update(patch_data)
        return self.dump(data)
