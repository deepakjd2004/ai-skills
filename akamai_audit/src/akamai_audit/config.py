from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class AppConfig:
    account_switch_key: str
    section: str = "default"
    edgerc_path: Path = Path.home() / ".edgerc"
    output_dir: Path = Path("output")

    @staticmethod
    def from_env(account_switch_key: str | None = None) -> "AppConfig":
        key = account_switch_key or os.getenv("AKAMAI_ACCOUNT_SWITCH_KEY", "").strip()
        if not key:
            raise ValueError(
                "Missing account switch key. Pass --account-switch-key or set AKAMAI_ACCOUNT_SWITCH_KEY."
            )

        section = os.getenv("AKAMAI_EDGERC_SECTION", "default").strip() or "default"
        edgerc = Path(os.getenv("AKAMAI_EDGERC", str(Path.home() / ".edgerc"))).expanduser()
        output = Path(os.getenv("AKAMAI_AUDIT_OUTPUT", "output"))
        return AppConfig(account_switch_key=key, section=section, edgerc_path=edgerc, output_dir=output)
