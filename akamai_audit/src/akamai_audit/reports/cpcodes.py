from __future__ import annotations

from typing import Any

from ..api import AkamaiApi


def cpcodes_report(api: AkamaiApi) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for cpcode in api.get_all_cpcodes():
        contract_id = ""
        for contract in cpcode.get("contracts", []):
            if contract.get("status") == "ongoing":
                contract_id = str(contract.get("contractId", ""))
                break

        products = " | ".join(str(p.get("productName", "")) for p in cpcode.get("products", []))
        rows.append(
            {
                "contract_id": contract_id,
                "cpcode_id": str(cpcode.get("cpcodeId", "")),
                "cpcode_name": str(cpcode.get("cpcodeName", "")),
                "cpcode_products": products,
            }
        )
    return rows


def find_cpcodes_in_property(rule_tree: dict[str, Any]) -> list[str]:
    cpcodes: list[str] = []

    for behavior in _find_by_selector(rule_tree, selector="behaviors", search_key="name", search_value="cpCode"):
        value = behavior.get("options", {}).get("value", {})
        cpcode_id = value.get("id")
        if cpcode_id is not None:
            cpcodes.append(str(cpcode_id))

    for behavior in _find_by_selector(rule_tree, selector="behaviors", search_key="name", search_value="imageManager"):
        options = behavior.get("options", {})
        original = options.get("cpCodeOriginal", {}).get("id")
        transformed = options.get("cpCodeTransformed", {}).get("id")
        if original is not None:
            cpcodes.append(str(original))
        if transformed is not None:
            cpcodes.append(str(transformed))

    seen: set[str] = set()
    unique = []
    for cpcode in cpcodes:
        if cpcode and cpcode not in seen:
            seen.add(cpcode)
            unique.append(cpcode)
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
