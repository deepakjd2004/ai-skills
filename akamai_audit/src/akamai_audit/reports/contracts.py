from __future__ import annotations

from ..api import AkamaiApi


def contracts_report(api: AkamaiApi) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for contract_id in api.get_all_contracts():
        products = api.get_all_products_per_contract(contract_id)
        for product in products:
            rows.append(
                {
                    "contract_id": contract_id,
                    "product_id": str(product.get("marketingProductId", "")),
                    "product_name": str(product.get("marketingProductName", "")),
                }
            )
    return rows
