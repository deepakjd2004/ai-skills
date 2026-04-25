from __future__ import annotations

from typing import Any


def behavior_audit(
    property_name: str,
    property_version: int,
    available_behaviors: dict[str, Any],
    rule_tree: dict[str, Any],
) -> list[dict[str, Any]]:
    behavior_names = [
        str(item.get("name", ""))
        for item in available_behaviors.get("behaviors", {}).get("items", [])
        if str(item.get("name", "")).strip()
    ]

    product_id = str(available_behaviors.get("productId", ""))
    rule_format = str(available_behaviors.get("ruleFormat", ""))
    details = f"{property_name} | v{property_version} | {rule_format} | {product_id}"

    in_use_behaviors = _recursive_collect_behavior_names(rule_tree)
    counts: dict[str, int] = {}
    for name in in_use_behaviors:
        counts[name] = counts.get(name, 0) + 1

    rows: list[dict[str, Any]] = []
    for behavior_name in behavior_names:
        count = counts.get(behavior_name, 0)
        rows.append(
            {
                "Configuration | Version | Format | Product": details,
                "Behavior": behavior_name,
                "In Use?": "✓" if count > 0 else "",
                "Count": count if count > 0 else "",
            }
        )

    return rows


def _recursive_collect_behavior_names(obj: Any, names: list[str] | None = None) -> list[str]:
    if names is None:
        names = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "behaviors" and isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        n = str(entry.get("name", ""))
                        if n:
                            names.append(n)
            elif isinstance(value, (dict, list)):
                _recursive_collect_behavior_names(value, names)
    elif isinstance(obj, list):
        for item in obj:
            _recursive_collect_behavior_names(item, names)

    return names
