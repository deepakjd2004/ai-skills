from __future__ import annotations

from ..api import AkamaiApi


def groups_report(api: AkamaiApi) -> list[dict[str, str]]:
    groups = api.get_all_groups()
    group_name_by_id = {str(g.get("groupId", "")): str(g.get("groupName", "")) for g in groups}

    rows: list[dict[str, str]] = []
    for group in groups:
        parent_group_id = str(group.get("parentGroupId", "PARENT"))
        parent_group_name = group_name_by_id.get(parent_group_id, "") if parent_group_id != "PARENT" else ""

        contract_ids = group.get("contractIds", [])
        contract_id = str(contract_ids[0]) if contract_ids else ""

        rows.append(
            {
                "contract_id": contract_id,
                "group_id": str(group.get("groupId", "")),
                "group_name": str(group.get("groupName", "")),
                "parent_group_id": parent_group_id,
                "parent_group_name": parent_group_name,
            }
        )

    return rows
