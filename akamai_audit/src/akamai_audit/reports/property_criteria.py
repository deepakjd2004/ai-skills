from __future__ import annotations

from typing import Any

CRITERIA_MAP = {
    "Path Match": "path",
    "IP/CIDR Match": "clientIp",
    "Regex Match": "regularExpression",
    "File Extension Match": "fileExtension",
    "ALL": "ALL",
}


def extract_property_criteria_matches(
    rule_tree: dict[str, Any],
    inventory_criteria: str = "ALL",
) -> dict[str, list[str]]:
    mode = (inventory_criteria or "ALL").strip()
    if mode not in CRITERIA_MAP:
        mode = "ALL"

    criteria_names = ["path", "clientIp", "regularExpression", "fileExtension"]
    if mode != "ALL":
        criteria_names = [CRITERIA_MAP[mode]]

    result: dict[str, list[str]] = {}
    for criteria_name in criteria_names:
        values = _find_matches_in_property(rule_tree, criteria_name)
        result[criteria_name] = values if values else ["No Criteria Found"]

    return result


def flatten_property_criteria(
    property_name: str,
    criteria_matches: dict[str, list[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for criteria_name, values in criteria_matches.items():
        for value in values:
            rows.append(
                {
                    "property_name": property_name,
                    "criteria": criteria_name,
                    "value": str(value),
                }
            )
    return rows


def _find_matches_in_property(rule_tree: dict[str, Any], criteria: str) -> list[str]:
    criteria_objects = _recursive_find(
        rule_tree,
        selector="criteria",
        search_key="name",
        search_value=criteria,
    )

    raw_values: list[Any] = []
    for criteria_obj in criteria_objects:
        options = criteria_obj.get("options", {})
        if criteria in ("path", "fileExtension", "clientIp"):
            raw_values.append(options.get("values", []))
        elif criteria == "regularExpression":
            raw_values.append(options.get("regex", ""))

    flattened: list[str] = []
    for item in raw_values:
        if isinstance(item, list):
            flattened.extend([str(x) for x in item if str(x).strip()])
        elif str(item).strip():
            flattened.append(str(item))

    return flattened


def _recursive_find(
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
                _recursive_find(value, selector, search_key, search_value, results)
    elif isinstance(obj, list):
        for item in obj:
            _recursive_find(item, selector, search_key, search_value, results)

    return results
