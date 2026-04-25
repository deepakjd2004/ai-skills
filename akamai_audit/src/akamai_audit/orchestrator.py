from __future__ import annotations

from typing import Any

from .api import AkamaiApi
from .reports.cloudlets import cloudlets_report
from .reports.contracts import contracts_report
from .reports.cpcodes import cpcodes_report
from .reports.groups import groups_report
from .reports.properties import all_properties_inventory_report, all_properties_report, properties_report
from .reports.traffic import traffic_report


def run_full_audit(
    api: AkamaiApi,
    property_names: list[str],
    include_all_properties: bool,
    custom_days: int | None,
    inventory_criteria: str,
) -> dict[str, Any]:
    contracts = contracts_report(api)
    groups = groups_report(api)
    cpcodes = cpcodes_report(api)
    properties, property_criteria, property_behaviors, property_hostnames = properties_report(
        api,
        property_names,
        inventory_criteria=inventory_criteria,
    )
    cloudlets = cloudlets_report(api)

    cpcode_list = _extract_cpcodes_from_properties(properties)
    traffic = traffic_report(api, cpcode_list, custom_days=custom_days) if cpcode_list else {}

    result: dict[str, Any] = {
        "contracts": contracts,
        "groups": groups,
        "cpcodes": cpcodes,
        "properties": properties,
        "property_criteria": property_criteria,
        "property_behaviors": property_behaviors,
        "property_hostnames": property_hostnames,
        "cloudlets": cloudlets,
    }
    result.update(traffic)

    if include_all_properties:
        result["all_properties"] = all_properties_report(api)

    return result


def run_account_summary(api: AkamaiApi) -> dict[str, Any]:
    return {
        "contracts": contracts_report(api),
        "groups": groups_report(api),
        "cpcodes": cpcodes_report(api),
        "properties": all_properties_inventory_report(api),
    }


def run_property_report(
    api: AkamaiApi,
    property_names: list[str],
    include_all_properties: bool,
    inventory_criteria: str,
) -> dict[str, Any]:
    properties, property_criteria, property_behaviors, property_hostnames = properties_report(
        api,
        property_names,
        inventory_criteria=inventory_criteria,
    )
    output: dict[str, Any] = {
        "properties": properties,
        "property_criteria": property_criteria,
        "property_behaviors": property_behaviors,
        "property_hostnames": property_hostnames,
    }
    if include_all_properties:
        output["all_properties"] = all_properties_report(api)
    return output


def run_cloudlets_report(api: AkamaiApi) -> dict[str, Any]:
    return {"cloudlets": cloudlets_report(api)}


def run_traffic_report(api: AkamaiApi, cpcodes: list[str], custom_days: int | None) -> dict[str, Any]:
    return traffic_report(api, cpcodes, custom_days)


def _extract_cpcodes_from_properties(property_rows: list[dict[str, Any]]) -> list[str]:
    cpcodes: list[str] = []
    for row in property_rows:
        for cpcode in row.get("cpcodes", []):
            cp = str(cpcode).strip()
            if cp:
                cpcodes.append(cp)
    return list(dict.fromkeys(cpcodes))
