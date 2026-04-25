# Akamai Audit Python Agent

This folder contains a Python migration of the retained Akamai audit flows from the Apps Script project.

Included flows:

- contracts
- groups
- cp codes
- properties
- property criteria matches (Path/IP/Regex/File Extension)
- cloudlets
- traffic

Excluded flows (intentionally):

- WPT
- CrUX
- AppSec
- Alerts
- DNS resolver

## Authentication

The script reads Akamai credentials from `~/.edgerc` using the `edgegrid-python` library.

Expected section format:

```ini
[default]
host = your-base-url.luna.akamaiapis.net
client_token = ...
client_secret = ...
access_token = ...
```

## Install

```bash
cd python_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Rate Limiting

The agent automatically retries on Akamai API 429 (Too Many Requests) errors with exponential backoff.

- Max retries: 5 attempts
- Initial backoff: 1 second, doubles per retry (1s, 2s, 4s, 8s, 16s)
- Inter-request delay: 0.5s between traffic report API calls to reduce rate limit contention

If you see rate limit messages during execution, this is normal behavior—the agent will wait and retry automatically.

## Run

```bash
cd python_agent
PYTHONPATH=src python main.py full_audit \
  --account-switch-key "YOUR_ACCOUNT_SWITCH_KEY" \
  --property "example-property" \
  --inventory-criteria "ALL" \
  --custom-days 30
```

Other actions:

```bash
PYTHONPATH=src python main.py account_summary --account-switch-key "..."
PYTHONPATH=src python main.py property_report --account-switch-key "..." --property "example-property"
PYTHONPATH=src python main.py cloudlets_report --account-switch-key "..."
PYTHONPATH=src python main.py traffic_report --account-switch-key "..." --cpcode "12345" --cpcode "67890"
```

## Output

The runner writes:

- `output/result.json`
- one CSV per result table (for example `output/contracts.csv`, `output/traffic_summary_hits.csv`)

Property reports now also include:

- `property_criteria.csv` with columns: `property_name`, `criteria`, `value`

## AI Agent Entry Point

Use `run_ai_agent_action()` in `src/akamai_audit/agent.py`.

Example payload:

```python
{
  "property_names": ["example-property"],
  "inventory_criteria": "ALL",
  "include_all_properties": False,
  "custom_days": 30,
  "cpcodes": ["12345", "67890"]
}
```
