from __future__ import annotations

from typing import Any

from .edgegrid_client import EdgeGridClient


class AkamaiApi:
    def __init__(self, client: EdgeGridClient):
        self.client = client

    def get_all_contracts(self) -> list[str]:
        return self.client.get("/contract-api/v1/contracts/identifiers")

    def get_all_products_per_contract(self, contract_id: str) -> list[dict[str, Any]]:
        data = self.client.get(f"/contract-api/v1/contracts/{contract_id}/products/summaries")
        return data.get("products", {}).get("marketing-products", [])

    def get_all_groups(self) -> list[dict[str, Any]]:
        data = self.client.get("/papi/v1/groups")
        return data.get("groups", {}).get("items", [])

    def get_all_cpcodes(self) -> list[dict[str, Any]]:
        data = self.client.get("/cprg/v1/cpcodes")
        return data.get("cpcodes", [])

    def find_all_properties(self) -> list[dict[str, Any]]:
        payload = {"bulkSearchQuery": {"syntax": "JSONPATH", "match": "$.name"}}
        data = self.client.post("/papi/v1/bulk/rules-search-requests-synch", payload)
        return data.get("results", [])

    def get_properties_for_contract_group(self, contract_id: str, group_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        offset = 0
        limit = 1000

        while True:
            data = self.client.get(
                "/papi/v1/properties",
                params={
                    "contractId": contract_id,
                    "groupId": group_id,
                    "offset": offset,
                    "limit": limit,
                },
            )
            page_items = data.get("properties", {}).get("items", []) or []
            items.extend(page_items)

            total_items = int(data.get("properties", {}).get("totalItems", len(items)) or len(items))
            if len(items) >= total_items or not page_items:
                break
            offset += limit

        return items

    def get_property_version_detail(
        self,
        property_id: str,
        property_version: int,
        contract_id: str,
        group_id: str,
    ) -> dict[str, Any]:
        path = f"/papi/v1/properties/{property_id}/versions/{property_version}"
        data = self.client.get(path, params={"contractId": contract_id, "groupId": group_id})
        items = data.get("versions", {}).get("items", [])
        return items[0] if items else {}

    def search_for_property(self, property_name: str) -> list[dict[str, Any]]:
        data = self.client.post("/papi/v1/search/find-by-value", {"propertyName": property_name})
        return data.get("versions", {}).get("items", [])

    def get_property_rule_tree(
        self,
        property_id: str,
        property_version: int,
        contract_id: str,
        group_id: str,
    ) -> dict[str, Any]:
        path = f"/papi/v1/properties/{property_id}/versions/{property_version}/rules"
        data = self.client.get(path, params={"contractId": contract_id, "groupId": group_id})
        return data.get("rules", {})

    def get_property_hostnames(
        self,
        property_id: str,
        property_version: int,
        contract_id: str,
        group_id: str,
    ) -> list[dict[str, Any]]:
        path = f"/papi/v1/properties/{property_id}/versions/{property_version}/hostnames"
        data = self.client.get(path, params={"contractId": contract_id, "groupId": group_id})
        return data.get("hostnames", {}).get("items", [])

    def get_all_available_behaviors(
        self,
        property_id: str,
        property_version: int,
    ) -> dict[str, Any]:
        path = f"/papi/v1/properties/{property_id}/versions/{property_version}/available-behaviors"
        return self.client.get(path)

    def get_cloudlets_info(self, endpoint: str) -> Any:
        return self.client.get(endpoint)

    def get_hits_by_cpcode_v2(self, cpcodes: list[str], start: str, end: str) -> dict[str, Any]:
        payload = {
            "dimensions": ["cpcode"],
            "metrics": ["edgeHitsSum", "originHitsSum", "offloadedHitsPercentage"],
            "filters": [
                {
                    "dimensionName": "cpcode",
                    "operator": "IN_LIST",
                    "expressions": [str(x) for x in cpcodes],
                }
            ],
            "sortBys": [{"name": "edgeHitsSum", "sortOrder": "DESCENDING"}],
        }
        return self.client.post(
            "/reporting-api/v2/reports/delivery/traffic/current/data",
            payload,
            params={"start": start, "end": end},
        )

    def get_bytes_by_cpcode_v2(self, cpcodes: list[str], start: str, end: str) -> dict[str, Any]:
        payload = {
            "dimensions": ["cpcode"],
            "metrics": ["edgeBytesSum", "originBytesSum", "offloadedBytesPercentage"],
            "filters": [
                {
                    "dimensionName": "cpcode",
                    "operator": "IN_LIST",
                    "expressions": [str(x) for x in cpcodes],
                }
            ],
            "sortBys": [{"name": "edgeBytesSum", "sortOrder": "DESCENDING"}],
        }
        return self.client.post(
            "/reporting-api/v2/reports/delivery/traffic/current/data",
            payload,
            params={"start": start, "end": end},
        )

    def get_traffic_by_response_v2(self, cpcodes: list[str], start: str, end: str) -> dict[str, Any]:
        payload = {
            "dimensions": ["responseCode"],
            "metrics": ["edgeHitsSum", "originHitsSum"],
            "filters": [
                {
                    "dimensionName": "cpcode",
                    "operator": "IN_LIST",
                    "expressions": [str(x) for x in cpcodes],
                }
            ],
            "sortBys": [{"name": "responseCode", "sortOrder": "ASCENDING"}],
        }
        return self.client.post(
            "/reporting-api/v2/reports/delivery/traffic/current/data",
            payload,
            params={"start": start, "end": end},
        )

    def get_url_hits_by_url(
        self,
        cpcodes: list[str],
        start: str,
        end: str,
        api_limit: int,
    ) -> dict[str, Any]:
        payload = {
            "objectType": "cpcode",
            "objectIds": [str(x) for x in cpcodes],
            "metrics": ["allEdgeHits", "allOriginHits", "allHitsOffload"],
            "limit": api_limit,
        }
        return self.client.post(
            "/reporting-api/v1/reports/urlhits-by-url/versions/1/report-data",
            payload,
            params={"start": start, "end": end, "interval": "DAY", "trace": "true"},
        )

    def get_responses_by_url(
        self,
        cpcodes: list[str],
        error_class: str,
        metric: str,
        start: str,
        end: str,
        api_limit: int,
    ) -> dict[str, Any]:
        payload = {
            "objectType": "cpcode",
            "objectIds": [str(x) for x in cpcodes],
            "metrics": [metric],
            "limit": api_limit,
        }
        return self.client.post(
            f"/reporting-api/v1/reports/url{error_class}responses-by-url/versions/1/report-data",
            payload,
            params={"start": start, "end": end, "interval": "DAY", "trace": "true"},
        )
