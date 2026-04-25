from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from akamai_audit.agent import run_ai_agent_action
from akamai_audit.api import AkamaiApi
from akamai_audit.config import AppConfig
from akamai_audit.edgegrid_client import EdgeGridClient
from akamai_audit.output import write_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Akamai audit Python runner")
    parser.add_argument("action", choices=["full_audit", "account_summary", "property_report", "cloudlets_report", "traffic_report"])
    parser.add_argument("--account-switch-key", required=False)
    parser.add_argument("--property", action="append", default=[])
    parser.add_argument("--cpcode", action="append", default=[])
    parser.add_argument("--custom-days", type=int, default=None)
    parser.add_argument(
        "--inventory-criteria",
        choices=["Path Match", "IP/CIDR Match", "Regex Match", "File Extension Match", "ALL"],
        default="ALL",
    )
    parser.add_argument("--include-all-properties", action="store_true")
    parser.add_argument("--edgerc", default=str(Path.home() / ".edgerc"))
    parser.add_argument("--section", default="default")
    parser.add_argument("--output-dir", default="output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    cfg = AppConfig.from_env(account_switch_key=args.account_switch_key)
    # CLI flags override env defaults.
    cfg = AppConfig(
        account_switch_key=cfg.account_switch_key,
        section=args.section or cfg.section,
        edgerc_path=Path(args.edgerc).expanduser(),
        output_dir=Path(args.output_dir),
    )

    client = EdgeGridClient.from_edgerc(
        edgerc_path=str(cfg.edgerc_path),
        section=cfg.section,
        account_switch_key=cfg.account_switch_key,
    )
    api = AkamaiApi(client)

    payload = {
        "property_names": args.property,
        "cpcodes": args.cpcode,
        "custom_days": args.custom_days,
        "inventory_criteria": args.inventory_criteria,
        "include_all_properties": args.include_all_properties,
    }

    result = run_ai_agent_action(api=api, action=args.action, payload=payload)
    first_property = args.property[0].strip() if args.property else args.action
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base_name = f"{first_property}_{timestamp}"

    write_outputs(result, cfg.output_dir, base_name=output_base_name)
    print(f"Completed {args.action}. Output written to: {cfg.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
