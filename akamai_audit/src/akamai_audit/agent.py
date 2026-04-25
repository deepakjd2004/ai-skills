from __future__ import annotations

from typing import Any

from .orchestrator import (
    run_account_summary,
    run_cloudlets_report,
    run_full_audit,
    run_property_report,
    run_traffic_report,
)
from .api import AkamaiApi


def run_ai_agent_action(api: AkamaiApi, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = action.strip().lower()

    if normalized == "full_audit":
        return run_full_audit(
            api=api,
            property_names=payload.get("property_names", []),
            include_all_properties=bool(payload.get("include_all_properties", False)),
            custom_days=payload.get("custom_days"),
            inventory_criteria=str(payload.get("inventory_criteria", "ALL")),
        )

    if normalized == "account_summary":
        return run_account_summary(api)

    if normalized == "property_report":
        return run_property_report(
            api=api,
            property_names=payload.get("property_names", []),
            include_all_properties=bool(payload.get("include_all_properties", False)),
            inventory_criteria=str(payload.get("inventory_criteria", "ALL")),
        )

    if normalized == "cloudlets_report":
        return run_cloudlets_report(api)

    if normalized == "traffic_report":
        return run_traffic_report(
            api=api,
            cpcodes=[str(x) for x in payload.get("cpcodes", [])],
            custom_days=payload.get("custom_days"),
        )

    raise ValueError(f"Unsupported action: {action}")
