# AI-SKILLS

This repository contains reusable AI-focused automation skills for audit and reporting workflows. These can be used with Claude, gemini-cli or other similar ai-tools skill.

## Projects

### 1. `web-auditor`

Performs web performance audits and generates a PowerPoint report.

Main components:

- `scripts/web_performance_audit_v2.py`: runs technical checks and writes JSON output.
- `scripts/generate_audit_deck.py`: converts audit JSON into a `.pptx` deck.

Important notes:

- The file in `template/` is a sample template and may require modifications for your branding/layout.
- You can still pass a template explicitly with `--template-file`.
- If no template is provided, `generate_audit_deck.py` now creates a standard PowerPoint automatically and ignores template-based formatting.

Quick flow:

```bash
cd web-auditor
python scripts/web_performance_audit_v2.py www.example.com --crux-key "$CRUX_API_KEY"
python scripts/generate_audit_deck.py --json-file output/<your_audit_file>.json
```

Template-based flow (optional):

```bash
python scripts/generate_audit_deck.py \
  --json-file output/<your_audit_file>.json \
  --template-file template/Performance_Review_of_example_com.pptx
```

### 2. `akamai_audit`

Python agent for Akamai inventory and traffic reporting.

Main components:

- `main.py`: CLI entry point for report actions.
- `src/akamai_audit/`: API client, report builders, and orchestration logic.
- `output/`: generated JSON and CSV artifacts.

## General Setup

Each skill directory has its own dependencies and README. Start in the target project folder and follow that folder's setup instructions.

## Output Convention

Both skills write generated artifacts to a local `output/` directory in their respective project folder.
