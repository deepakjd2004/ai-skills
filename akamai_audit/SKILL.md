---
name: akamai-property-audit
description: Performs comprehensive audits and traffic analysis for Akamai properties. Use this skill when asked to run reports, audit properties, or analyze traffic data on Akamai.
---

# Akamai Property Audit Skill

This skill allows the agent to perform various assessments on Akamai properties, including audits of contracts, groups, CP codes, property behaviors, and traffic analysis. The skill is designed to provide detailed insights into the configuration and traffic data served via. Akamai properties.

## Capabilities

- **Full Audit**: Comprehensive report including contracts, groups, CP codes, property behaviors, and traffic.
- **Traffic Report**: Detailed hits and bytes analysis for specific CP codes over a custom date range.
- **Account Summary**: High-level inventory of all contracts, groups, and properties.
- **Property Report**: Deep dive into specific property configurations, behaviors, and hostnames.
- **Cloudlets Report**: Summary of all Cloudlet policies and their associated properties.

## How to Use

When a user asks for a report, identify the required action and map the inputs to the `run_ai_agent_action` function in `src/akamai_audit/agent.py`.

### Action Mapping

1. **"Run a traffic report for CP code 12345"**
   - Action: `traffic_report`
   - Payload: `{"cpcodes": ["12345"], "custom_days": 30}`
2. **"Audit property www.example.com"**
   - Action: `property_report`
   - Payload: `{"property_names": ["www.example.com"], "inventory_criteria": "ALL"}`
3. **"Give me a full account summary"**
   - Action: `account_summary`
   - Payload: `{}`

## Constraints & Requirements

- **Account Switch Key**: Most actions require an `account_switch_key`. If not provided by the user, ask for it or look for it in environment variables. Account Switch key is not mandatory and if not provided the skill will attempt to run with the default credentials.
- **Output**: The skill generates a JSON result which is then converted into an Excel file (.xlsx) and multiple CSVs in the `output/` directory.

## Examples

# Example 1: Running a Traffic Report for Multiple CP Codes

**User**: "Can you run a traffic report for my CP codes 98765 and 43210 for the last 15 days?"
**Agent**: _Recognizes `traffic_report` action. Calls `run_ai_agent_action(api, "traffic_report", {"cpcodes": ["98765", "43210"], "custom_days": 15})`._

# Example 2: Auditing a Specific Property

**User**: "I want to audit the property www.mysite.com for all its configurations and traffic."
**Agent**: \_Recognizes `property_report` action. Calls `run_ai_agent_action

# Example 3: Requesting an Account Summary

**User**: "Please provide a summary of all my Akamai contracts, groups, and properties."
**Agent**: \_Recognizes `account_summary` action. Calls `run_ai_agent_action
