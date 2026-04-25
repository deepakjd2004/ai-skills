from __future__ import annotations

from typing import Any


def find_origin_hostnames_in_property(rule_tree: dict[str, Any]) -> list[str]:
    hostnames: list[str] = []
    for behavior in _find_by_selector(rule_tree, selector="behaviors", search_key="name", search_value="origin"):
        options = behavior.get("options", {})
        if options.get("originType") == "CUSTOMER" and options.get("hostname"):
            hostnames.append(str(options["hostname"]))

    seen: set[str] = set()
    unique = []
    for hostname in hostnames:
        if hostname not in seen:
            seen.add(hostname)
            unique.append(hostname)
    return unique


def _find_by_selector(
    obj: Any,
    selector: str,
    search_key: str,
    search_value: str,
    results: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if results is None:
        results = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == selector and isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and entry.get(search_key) == search_value:
                        results.append(entry)
            elif isinstance(value, (dict, list)):
                _find_by_selector(value, selector, search_key, search_value, results)
    elif isinstance(obj, list):
        for item in obj:
            _find_by_selector(item, selector, search_key, search_value, results)

    return results
