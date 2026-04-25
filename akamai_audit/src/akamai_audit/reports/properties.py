from __future__ import annotations

from typing import Any

from ..api import AkamaiApi
from .property_behaviors import behavior_audit
from .cpcodes import find_cpcodes_in_property
from .origins import find_origin_hostnames_in_property
from .property_criteria import extract_property_criteria_matches, flatten_property_criteria


def properties_report(
    api: AkamaiApi,
    property_names: list[str],
    inventory_criteria: str = "ALL",
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    rows: list[dict[str, Any]] = []
    criteria_rows: list[dict[str, str]] = []
    behavior_rows: list[dict[str, Any]] = []
    hostname_rows: list[dict[str, Any]] = []

    for name in [p.strip() for p in property_names if p and p.strip()]:
        activations = api.search_for_property(name)
        if not activations:
            rows.append(
                {
                    "property_name": name,
                    "error": "Property not found",
                }
            )
            continue

        selected = _choose_activation(activations)
        rule_tree = api.get_property_rule_tree(
            property_id=str(selected.get("propertyId")),
            property_version=int(selected.get("propertyVersion")),
            contract_id=str(selected.get("contractId")),
            group_id=str(selected.get("groupId")),
        )

        cpcodes = find_cpcodes_in_property(rule_tree)
        origins = find_origin_hostnames_in_property(rule_tree)
        criteria_matches = extract_property_criteria_matches(rule_tree, inventory_criteria)
        criteria_rows.extend(flatten_property_criteria(str(selected.get("propertyName", name)), criteria_matches))

        papi_hostnames = api.get_property_hostnames(
            property_id=str(selected.get("propertyId")),
            property_version=int(selected.get("propertyVersion")),
            contract_id=str(selected.get("contractId")),
            group_id=str(selected.get("groupId")),
        )
        property_hostnames = [
            str(item.get("cnameFrom", ""))
            for item in papi_hostnames
            if str(item.get("cnameFrom", "")).strip()
        ]
        max_rows = max(len(property_hostnames), len(origins), 1)
        for i in range(max_rows):
            hostname_rows.append(
                {
                    "Hostnames DNS Resolution": property_hostnames[i] if i < len(property_hostnames) else "",
                    "Origin Hostnames DNS Resolution": origins[i] if i < len(origins) else "",
                }
            )

        available_behaviors = api.get_all_available_behaviors(
            property_id=str(selected.get("propertyId")),
            property_version=int(selected.get("propertyVersion")),
        )
        behavior_rows.extend(
            behavior_audit(
                property_name=str(selected.get("propertyName", name)),
                property_version=int(selected.get("propertyVersion", 0)),
                available_behaviors=available_behaviors,
                rule_tree=rule_tree,
            )
        )

        rows.append(
            {
                "property_id": str(selected.get("propertyId", "")),
                "property_name": str(selected.get("propertyName", name)),
                "group_id": str(selected.get("groupId", "")),
                "contract_id": str(selected.get("contractId", "")),
                "production_status": str(selected.get("productionStatus", "")),
                "staging_status": str(selected.get("stagingStatus", "")),
                "property_version": int(selected.get("propertyVersion", 0)),
                "updated_date": str(selected.get("updatedDate", "")),
                "updated_by_user": str(selected.get("updatedByUser", "")),
                "note": str(selected.get("note", "")),
                "cpcodes": cpcodes,
                "origin_hostnames": origins,
                "criteria_matches": criteria_matches,
            }
        )

    return rows, criteria_rows, behavior_rows, hostname_rows


def all_properties_report(api: AkamaiApi) -> list[dict[str, Any]]:
    all_items = api.find_all_properties()
    property_names = _extract_unique_property_names(all_items)
    rows, _, _, _ = properties_report(api, property_names, inventory_criteria="ALL")
    return rows


def all_properties_inventory_report(api: AkamaiApi) -> list[dict[str, Any]]:
    """Return account-wide properties via contract/group traversal.

    This path fetches properties from each contract/group pair so account summary
    includes properties across multi-contract, multi-group account layouts.
    """
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    groups = api.get_all_groups()

    for group in groups or []:
        group_id = str(group.get("groupId", "")).strip()
        contract_ids = [str(c).strip() for c in (group.get("contractIds", []) or []) if str(c).strip()]
        if not group_id or not contract_ids:
            continue

        for contract_id in contract_ids:
            for item in api.get_properties_for_contract_group(contract_id=contract_id, group_id=group_id):
                property_id = str(item.get("propertyId", item.get("id", ""))).strip()
                key = (contract_id, group_id, property_id)
                if property_id and key in seen:
                    continue
                seen.add(key)

                # Derive activation status from version numbers (list endpoint doesn't return status strings)
                prod_version = item.get("productionVersion")
                staging_version = item.get("stagingVersion")
                latest_version = int(item.get("latestVersion", 0) or 0)
                active_version = int(prod_version or staging_version or latest_version or 0)

                production_status = "ACTIVE" if prod_version is not None else "INACTIVE"
                staging_status = "ACTIVE" if staging_version is not None else "INACTIVE"

                # Fetch version detail to get updatedDate, updatedByUser, note
                updated_date = ""
                updated_by_user = ""
                note = ""
                if active_version:
                    version_detail = api.get_property_version_detail(
                        property_id=property_id,
                        property_version=active_version,
                        contract_id=contract_id,
                        group_id=group_id,
                    )
                    updated_date = str(version_detail.get("updatedDate", ""))
                    updated_by_user = str(version_detail.get("updatedByUser", ""))
                    note = str(version_detail.get("note", ""))

                rows.append(
                    {
                        "property_id": property_id,
                        "property_name": str(item.get("propertyName", item.get("name", ""))),
                        "group_id": group_id,
                        "contract_id": contract_id,
                        "production_status": production_status,
                        "staging_status": staging_status,
                        "property_version": active_version,
                        "updated_date": updated_date,
                        "updated_by_user": updated_by_user,
                        "note": note,
                        "cpcodes": [],
                        "origin_hostnames": [],
                        "criteria_matches": {},
                    }
                )

    rows.sort(key=lambda r: (str(r.get("contract_id", "")), str(r.get("group_id", "")), str(r.get("property_name", ""))))
    return rows


def _choose_activation(activations: list[dict[str, Any]]) -> dict[str, Any]:
    for item in activations:
        if item.get("productionStatus") == "ACTIVE":
            return item
    for item in activations:
        if item.get("stagingStatus") == "ACTIVE":
            return item
    return activations[0]


def _extract_unique_property_names(items: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for item in items:
        name = str(item.get("propertyName", "")).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names
