"""Helpers for values interpolated into PromQL and LogQL selectors."""

from __future__ import annotations

import json


# ``re.escape`` is not suitable for Prometheus/LogQL selectors: recent Python
# versions escape punctuation such as ``-`` as ``\-``, while RE2 rejects that
# escape in a query string.  Keep this list to characters that have meaning in
# an RE2 expression.  The JSON encoding below adds the second layer of
# escaping required by PromQL/LogQL double-quoted string literals.
_RE2_META = frozenset(r"\.^$*+?{}[]|()")


def escape_query_regex_literal(value: object) -> str:
    """Return *value* as a literal for a PromQL/LogQL regex string.

    The returned text is intended to be interpolated between the double
    quotes of a selector, for example ``instance=~".*{value}.*"``.  It does
    not escape hyphens or other ordinary RE2 characters, but it does encode
    the query-string layer (quotes, backslashes, and control characters).
    """

    regex_literal = "".join(
        f"\\{character}" if character in _RE2_META else character for character in str(value)
    )
    return json.dumps(regex_literal, ensure_ascii=False)[1:-1]
