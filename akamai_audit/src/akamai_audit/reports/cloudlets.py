from __future__ import annotations

from ..api import AkamaiApi


def cloudlets_report(api: AkamaiApi) -> list[dict[str, str | int]]:
    non_shared = api.get_cloudlets_info("/cloudlets/api/v2/policies")
    shared = api.get_cloudlets_info("/cloudlets/v3/policies")
    assignments = api.get_cloudlets_info("/cloudlets/api/v2/properties")

    non_shared_rows = [
        {
            "policy_id": str(item.get("policyId", "")),
            "policy_name": str(item.get("name", "")),
            "policy_type": "NON-SHARED",
            "cloudlet_type": str(item.get("cloudletCode", "")),
        }
        for item in (non_shared or [])
    ]

    shared_rows = [
        {
            "policy_id": str(item.get("id", "")),
            "policy_name": str(item.get("name", "")),
            "policy_type": str(item.get("policyType", "")),
            "cloudlet_type": str(item.get("cloudletType", "")),
        }
        for item in (shared or {}).get("content", [])
    ]

    rows = []
    for row in [*shared_rows, *non_shared_rows]:
        matching_properties: list[str] = []
        for assignment in assignments or []:
            prod = (assignment.get("production") or {}).get("referencedPolicies", [])
            stag = (assignment.get("staging") or {}).get("referencedPolicies", [])
            if row["policy_name"] in prod or row["policy_name"] in stag:
                matching_properties.append(str(assignment.get("name", "")))

        rows.append(
            {
                **row,
                "associated_properties": ", ".join([p for p in matching_properties if p]),
                "property_count": len([p for p in matching_properties if p]),
            }
        )

    return rows
