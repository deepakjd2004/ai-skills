# Web Performance Auditor

A Gemini skill that audits websites for performance, Core Web Vitals, and technical health — then generates a PowerPoint presentation from the results.

## What It Does

1. Runs a headless Chrome audit + network checks against a target URL
2. Fetches real-world Core Web Vitals from the Chrome UX Report (CrUX) API
3. Outputs a structured JSON report
4. Generates a PowerPoint deck from the JSON, optionally using a custom template

## Project Structure

```
web-auditor/
├── SKILL.md                        # Gemini skill definition
├── scripts/
│   ├── web_performance_audit_v2.py # Main auditor script
│   └── generate_audit_deck.py      # PowerPoint generation script (template optional)
├── template/
│   └── Performance_Review_of_example_com.pptx  # Sample PPTX template (may need modifications)
└── output/                         # Generated JSON reports and decks
```

## Audit Script Capabilities

`web_performance_audit_v2.py` runs up to 10 checks in a single pass:

| #   | Check                                  | What it measures                                                                                                                      |
| --- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **CrUX data**                          | Real-world LCP, INP, CLS, FCP, TTFB from the Chrome UX Report API (URL-level, falling back to origin-level)                           |
| 2   | **DNS configuration**                  | DNS TTL values and IPv6 (`AAAA` record) support                                                                                       |
| 3   | **CDN detection**                      | Identifies CDN provider via IP-based lookup                                                                                           |
| 4   | **HTML parsing & resource extraction** | Fetches and parses the page statically or via headless Chrome for JS-rendered content                                                 |
| 5   | **First-party asset compression**      | Checks whether first-party CSS/JS is served with gzip or Brotli compression                                                           |
| 6   | **Render-blocking resource analysis**  | Identifies parser-blocking `<script>` and `<link>` tags in `<head>`                                                                   |
| 7   | **Additional resource analysis**       | Evaluates resource hints (`preload`, `prefetch`, `preconnect`), image formats, font loading, HTTP protocol version, and cache headers |
| 8   | **Slow resource detection**            | Flags resources with high response times using browser network timings (browser mode only)                                            |
| 9   | **Heavy payload analysis**             | Identifies large resources by transfer size using browser network timings (browser mode only)                                         |
| 10  | **Per-domain HTTP protocol breakdown** | Reports HTTP/1.1 / HTTP/2 / HTTP/3 usage for each third-party domain                                                                  |

### Rendering Modes

| Mode              | Flag        | Best for                                         |
| ----------------- | ----------- | ------------------------------------------------ |
| Static            | _(none)_    | Fast audits                                      |
| Browser (default) | `--browser` | SPAs and JS-rendered pages; enables checks 8 & 9 |

### Audit Modes

| Mode       | Description                                                      |
| ---------- | ---------------------------------------------------------------- |
| Full audit | All 10 checks (default)                                          |
| DNS-only   | Runs only DNS TTL, IPv6, and CDN checks — no page fetch required |

## Prerequisites

```bash
pip install requests dnspython beautifulsoup4 python-pptx lxml

# Optional — enables JavaScript rendering for SPAs:
pip install selenium
# Also requires Chrome or Chromium installed
```

A [CrUX API key](https://developer.chrome.com/docs/crux/api/) is required for real-world Core Web Vitals data. Set it as an environment variable:

```bash
export CRUX_API_KEY=your_api_key_here
```

## Usage

### Step 1 — Run the audit

```bash
python scripts/web_performance_audit_v2.py <URL> --crux-key $CRUX_API_KEY
```

Example:

```bash
python scripts/web_performance_audit_v2.py www.example.com --crux-key $CRUX_API_KEY
```

This produces a timestamped JSON file in `output/`, e.g. `output/performance_audit_www_example_com_20260424_153606.json`.

### Step 2 — Generate the PowerPoint deck

Generate a standard deck (no template required):

```bash
python scripts/generate_audit_deck.py \
	--json-file output/performance_audit_www_example_com_20260424_153606.json
```

Generate with a template (optional):

```bash
python scripts/generate_audit_deck.py \
	--json-file output/performance_audit_www_example_com_20260424_153606.json \
	--template-file template/Performance_Review_of_example_com.pptx
```

The deck is saved to the `output/` folder.

## Output

### JSON Report

The JSON contains the following top-level sections:

| Field              | Description                                                     |
| ------------------ | --------------------------------------------------------------- |
| `crux_data`        | Real-world Core Web Vitals (LCP, INP, CLS, FCP, TTFB) from CrUX |
| `technical_checks` | HTTP/3, IPv6 support, caching policy, resource protocols        |
| `recommendations`  | Prioritised, actionable fixes                                   |

### PowerPoint Deck

A slide deck built from the template containing:

- Cover slide with the audited URL and date
- Core Web Vitals summary with Good / Needs Improvement / Poor ratings
- Technical findings (HTTP version, protocols, caching)
- Top recommendations colour-coded by severity (Critical / High / Medium)

## Severity Colours

| Severity | Colour |
| -------- | ------ |
| CRITICAL | Red    |
| HIGH     | Orange |
| MEDIUM   | Amber  |
| Default  | Cyan   |

## Notes

- Protocol detection uses both `technical_checks.http_version` (main document) and `technical_checks.resource_protocols` (per-domain) to accurately report HTTP/3 support.
- Pass `--no-browser` to skip Selenium and use static HTML fetching only (faster, but misses JS-rendered content).
- `template/Performance_Review_of_example_com.pptx` is a sample file and may need modifications for your own layout and branding.
- If `--template-file` is omitted, the script automatically creates a standard PPT and skips template-specific formatting.
