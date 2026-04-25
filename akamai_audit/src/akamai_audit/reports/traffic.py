from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from ..api import AkamaiApi


def build_date_range(custom_days: int | None = None) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    if custom_days and custom_days > 0:
        start = (now - timedelta(days=custom_days + 1)).strftime("%Y-%m-%dT00:00:00.00Z")
        end = (now - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.00Z")
        return start, end

    first_of_prev_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_of_prev_month = now.replace(day=1) - timedelta(days=1)
    return (
        first_of_prev_month.strftime("%Y-%m-%dT00:00:00.00Z"),
        last_of_prev_month.strftime("%Y-%m-%dT00:00:00.00Z"),
    )


def traffic_report(
    api: AkamaiApi,
    cpcodes: list[str],
    custom_days: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    unique_cpcodes = list(dict.fromkeys([str(c).strip() for c in cpcodes if str(c).strip()]))
    start, end = build_date_range(custom_days)
    group_size = 1000
    api_limit = _calculate_api_limit(len(unique_cpcodes), group_size)

    all_cpcodes = api.get_all_cpcodes()

    hits_data = api.get_hits_by_cpcode_v2(unique_cpcodes, start, end)
    bytes_data = api.get_bytes_by_cpcode_v2(unique_cpcodes, start, end)
    response_data = api.get_traffic_by_response_v2(unique_cpcodes, start, end)

    hits = _cpcode_hits_rows(all_cpcodes, unique_cpcodes, hits_data)
    bytes_ = _cpcode_bytes_rows(all_cpcodes, unique_cpcodes, bytes_data)
    response_codes = _response_rows(response_data)
    url_hits_rows = _url_hits_rows(api, unique_cpcodes, group_size, start, end, api_limit)
    url_extension_summary = _url_extension_summary_rows(url_hits_rows)
    url_302_rows = _url_responses_by_code_rows(
        api,
        unique_cpcodes,
        group_size,
        start,
        end,
        metric="302EdgeHits",
        error_class="3XX",
        api_limit=api_limit,
    )
    url_304_rows = _url_responses_by_code_rows(
        api,
        unique_cpcodes,
        group_size,
        start,
        end,
        metric="304EdgeHits",
        error_class="3XX",
        api_limit=api_limit,
    )
    url_404_rows = _url_responses_by_code_rows(
        api,
        unique_cpcodes,
        group_size,
        start,
        end,
        metric="404EdgeHits",
        error_class="4XX",
        api_limit=api_limit,
    )

    return {
        "date_range": [{"start": start, "end": end}],
        "traffic_summary_hits": hits,
        "traffic_summary_bytes": bytes_,
        "url_traffic_hits": url_hits_rows,
        "url_traffic_extension_summary": url_extension_summary,
        "response_codes": response_codes,
        "url_302": url_302_rows,
        "url_304": url_304_rows,
        "url_404": url_404_rows,
    }


def _calculate_api_limit(cpcode_count: int, group_size: int) -> int:
    if cpcode_count <= 0:
        return 5000
    if cpcode_count > group_size:
        return int(5000 / (cpcode_count / group_size))
    return 5000


def _url_hits_rows(
    api: AkamaiApi,
    cpcodes: list[str],
    group_size: int,
    start: str,
    end: str,
    api_limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pattern = re.compile(r"\.([\w]{2,})(\?|$)")

    for i in range(0, len(cpcodes), group_size):
        group = cpcodes[i : i + group_size]
        response = api.get_url_hits_by_url(group, start, end, api_limit)
        time.sleep(0.5)
        for item in response.get("data", []) or []:
            url = str(item.get("hostname.url", ""))
            ext_match = pattern.search(url)
            ext = ext_match.group(1) if ext_match else "No Ext"
            rows.append(
                {
                    "url": url,
                    "edge_hits": float(item.get("allEdgeHits", 0) or 0),
                    "offload_percent": float(item.get("allHitsOffload", 0) or 0),
                    "origin_hits": float(item.get("allOriginHits", 0) or 0),
                    "file_extension": ext,
                }
            )

    return rows


def _url_responses_by_code_rows(
    api: AkamaiApi,
    cpcodes: list[str],
    group_size: int,
    start: str,
    end: str,
    metric: str,
    error_class: str,
    api_limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for i in range(0, len(cpcodes), group_size):
        group = cpcodes[i : i + group_size]
        response = api.get_responses_by_url(
            group,
            error_class=error_class,
            metric=metric,
            start=start,
            end=end,
            api_limit=api_limit,
        )
        time.sleep(0.5)
        for item in response.get("data", []) or []:
            rows.append(
                {
                    "url": str(item.get("hostname.url", "")),
                    "hits": float(item.get(metric, 0) or 0),
                    "metric": metric,
                }
            )

    return rows


def _url_extension_summary_rows(url_hits_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, float]] = {}

    for row in url_hits_rows:
        ext = str(row.get("file_extension", "No Ext") or "No Ext")
        edge_hits = float(row.get("edge_hits", 0) or 0)
        origin_hits = float(row.get("origin_hits", 0) or 0)

        if ext not in grouped:
            grouped[ext] = {"edge_hits_sum": 0.0, "origin_hits_sum": 0.0}

        grouped[ext]["edge_hits_sum"] += edge_hits
        grouped[ext]["origin_hits_sum"] += origin_hits

    total_edge_hits = sum(values["edge_hits_sum"] for values in grouped.values())

    rows: list[dict[str, Any]] = []
    for extension, values in grouped.items():
        edge_hits_sum = values["edge_hits_sum"]
        origin_hits_sum = values["origin_hits_sum"]
        edge_hits_percent = (edge_hits_sum / total_edge_hits * 100.0) if total_edge_hits else 0.0
        offload_percent = ((edge_hits_sum - origin_hits_sum) / edge_hits_sum * 100.0) if edge_hits_sum else 0.0

        rows.append(
            {
                "file_extension": extension,
                "edge_hits_sum": edge_hits_sum,
                "edge_hits_percent": edge_hits_percent,
                "origin_hits_sum": origin_hits_sum,
                "offload_percent": offload_percent,
            }
        )

    rows.sort(key=lambda x: float(x["edge_hits_sum"]), reverse=True)
    return rows


def _cpcode_hits_rows(
    all_cpcodes: list[dict[str, Any]],
    requested_cpcodes: list[str],
    response: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in response.get("data", []) or []:
        cpcode = str(item.get("cpcode", ""))
        rows.append(
            {
                "cpcode_id": cpcode,
                "cpcode_name": _cpcode_name(all_cpcodes, cpcode),
                "offload_percent": float(item.get("offloadedHitsPercentage", 0) or 0),
                "edge_hits": float(item.get("edgeHitsSum", 0) or 0),
                "origin_hits": float(item.get("originHitsSum", 0) or 0),
            }
        )
        seen.add(cpcode)

    for cpcode in requested_cpcodes:
        if cpcode not in seen:
            rows.append(
                {
                    "cpcode_id": cpcode,
                    "cpcode_name": _cpcode_name(all_cpcodes, cpcode),
                    "offload_percent": 0.0,
                    "edge_hits": 0.0,
                    "origin_hits": 0.0,
                }
            )

    return rows


def _cpcode_bytes_rows(
    all_cpcodes: list[dict[str, Any]],
    requested_cpcodes: list[str],
    response: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in response.get("data", []) or []:
        cpcode = str(item.get("cpcode", ""))
        rows.append(
            {
                "cpcode_id": cpcode,
                "cpcode_name": _cpcode_name(all_cpcodes, cpcode),
                "offload_percent": float(item.get("offloadedBytesPercentage", 0) or 0),
                "edge_bytes": float(item.get("edgeBytesSum", 0) or 0),
                "origin_bytes": float(item.get("originBytesSum", 0) or 0),
            }
        )
        seen.add(cpcode)

    for cpcode in requested_cpcodes:
        if cpcode not in seen:
            rows.append(
                {
                    "cpcode_id": cpcode,
                    "cpcode_name": _cpcode_name(all_cpcodes, cpcode),
                    "offload_percent": 0.0,
                    "edge_bytes": 0.0,
                    "origin_bytes": 0.0,
                }
            )

    return rows


def _response_rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    items = response.get("data", []) or []
    total_edge = sum(float(x.get("edgeHitsSum", 0) or 0) for x in items)
    total_origin = sum(float(x.get("originHitsSum", 0) or 0) for x in items)

    rows: list[dict[str, Any]] = []
    for item in items:
        edge_hits = float(item.get("edgeHitsSum", 0) or 0)
        origin_hits = float(item.get("originHitsSum", 0) or 0)
        rows.append(
            {
                "response_code": int(item.get("responseCode", 0) or 0),
                "edge_hits": edge_hits,
                "edge_hits_percent": (edge_hits / total_edge * 100.0) if total_edge else 0.0,
                "origin_hits": origin_hits,
                "origin_hits_percent": (origin_hits / total_origin * 100.0) if total_origin else 0.0,
            }
        )
    return rows


def _cpcode_name(all_cpcodes: list[dict[str, Any]], cpcode_id: str) -> str:
    for cpcode in all_cpcodes:
        if str(cpcode.get("cpcodeId", "")) == str(cpcode_id):
            return str(cpcode.get("cpcodeName", "NA"))
    return "NA"
