#!/usr/bin/env python3
"""Create auditable costed Inventory movements for turnover-days and aged-stock metrics."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request
import uuid


ROUTE = "/admin-api/cloudmold/inventory/v3/command"


def call(base_url: str, tenant: int, token: str | None, path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "tenant-id": str(tenant)}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(base_url.rstrip("/") + path, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc
    if result.get("code") != 0:
        raise RuntimeError(f"API rejected {path}: {result}")
    return result["data"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=1)
    parser.add_argument("--username", default=os.getenv("CLOUDMOLD_ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("CLOUDMOLD_ADMIN_PASSWORD", "admin123"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--owner-id", default="d9560649-d2b3-4959-9049-f6eef7094729")
    parser.add_argument("--sku-id", default="107e4efe-0411-458d-ac7d-8b4b92e682b1")
    parser.add_argument("--warehouse-id", default="72778a33-4015-49b7-b786-5abda7d688ee")
    parser.add_argument("--location-id", default="72b43d20-e2bf-4c7c-9e0b-0eaed5284272")
    args = parser.parse_args()

    login = call(args.base_url, args.tenant, None, "/admin-api/system/auth/login",
                 {"username": args.username, "password": args.password})
    token = login["accessToken"]
    correlation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:inventory-cost:{args.run_id}"))
    common = {
        "ownerType": "MERCHANT", "ownerId": args.owner_id, "canonicalSkuId": args.sku_id,
        "warehouseId": args.warehouse_id, "locationId": args.location_id, "lotId": None,
        "stockStatus": "SELLABLE", "qualityStatus": "QUALIFIED", "baseUomCode": "PIECE",
        "businessId": args.run_id, "businessNo": f"INV-COST-{args.run_id}",
        "correlationId": correlation_id, "currencyCode": "CNY",
        "costSourceSystem": "cloudmold-procurement", "costPolicyVersion": "FIFO-V1",
    }
    receive = {**common, "operation": "RECEIVE", "idempotencyKey": f"{args.run_id}:receive",
               "sourceEventId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{args.run_id}:receive")),
               "quantity": "10.000000", "businessType": "PURCHASE_RECEIPT",
               "businessItemId": f"{args.run_id}:receipt-line", "occurredAt": "2026-04-01T00:00:00Z",
               "unitCostAmountMinor": 12000, "movementCostAmountMinor": 120000,
               "costSourceRef": f"receipt-line:{args.run_id}:001"}
    reserve = {key: value for key, value in common.items()
               if key not in {"currencyCode", "costSourceSystem", "costPolicyVersion"}}
    reserve.update({"operation": "RESERVE", "idempotencyKey": f"{args.run_id}:reserve",
                    "sourceEventId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{args.run_id}:reserve")),
                    "quantity": "4.000000", "businessType": "TRADE_ORDER",
                    "businessItemId": f"{args.run_id}:order-line", "occurredAt": "2026-07-18T04:00:00Z"})

    receive_result = call(args.base_url, args.tenant, token, ROUTE, receive)
    reserve_result = call(args.base_url, args.tenant, token, ROUTE, reserve)
    ship = {**common, "operation": "SHIP", "idempotencyKey": f"{args.run_id}:ship",
            "sourceEventId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{args.run_id}:ship")),
            "quantity": "4.000000", "reservationId": reserve_result["reservationId"],
            "businessType": "TRADE_ORDER", "businessItemId": f"{args.run_id}:order-line",
            "occurredAt": "2026-07-18T04:05:00Z", "unitCostAmountMinor": 12000,
            "movementCostAmountMinor": 48000, "costSourceRef": f"shipment-cogs:{args.run_id}:001"}
    ship_result = call(args.base_url, args.tenant, token, ROUTE, ship)
    replays = [call(args.base_url, args.tenant, token, ROUTE, payload)
               for payload in (receive, reserve, ship)]
    if not all(item.get("duplicate") is True for item in replays):
        raise RuntimeError("immutable replay verification failed")

    ledger = {
        "scenario": "canonical-inventory-cost-aging-v1", "run_id": args.run_id,
        "environment": "local-test", "tenant": args.tenant,
        "dimensions": {"owner_id": args.owner_id, "canonical_sku_id": args.sku_id,
                       "warehouse_id": args.warehouse_id, "location_id": args.location_id, "lot_id": None},
        "semantics": {"cost_policy_version": "FIFO-V1", "currency_code": "CNY",
                      "aged_threshold_days": 90, "turnover_window_days": 90},
        "steps": [{"operation": "RECEIVE", "result": receive_result},
                  {"operation": "RESERVE", "result": reserve_result},
                  {"operation": "SHIP", "result": ship_result}],
        "replay_duplicate": True, "status": "SUCCEEDED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    output = Path.home() / ".cloudmold" / "runs" / "inventory-cost-aging" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "succeeded", "ledger": str(output), "final": ship_result},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
