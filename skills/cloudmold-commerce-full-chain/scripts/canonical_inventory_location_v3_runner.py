#!/usr/bin/env python3
"""Run the location-aware Inventory v3 first slice on canonical master data."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_inventory_runner import Client, ScenarioError, decimal, request_hash  # noqa: E402


ROUTE = "/admin-api/cloudmold/inventory/v3/command"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,31}$")
STEPS = (
    ("RECEIVE", "10.000000", ("10.000000", "0.000000", "0.000000", "10.000000", 1)),
    ("RESERVE", "3.000000", ("10.000000", "3.000000", "0.000000", "7.000000", 2)),
    ("SHIP", "3.000000", ("7.000000", "0.000000", "0.000000", "7.000000", 3)),
    ("RETURN", "1.000000", ("8.000000", "0.000000", "0.000000", "8.000000", 4)),
    ("RESERVE", "2.000000", ("8.000000", "2.000000", "0.000000", "6.000000", 5)),
    ("RELEASE", "2.000000", ("8.000000", "0.000000", "0.000000", "8.000000", 6)),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def load_master(path_value: str | None, tenant: int) -> dict:
    require(bool(path_value), "execute requires --master-ledger from a SUCCEEDED canonical master run")
    path = Path(path_value).expanduser().resolve()
    require(path.is_file(), f"master ledger does not exist: {path}")
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read master ledger: {exc}") from exc
    require(ledger.get("scenario") == "canonical-merchant-warehouse-first-slice-v1",
            "master ledger has an unexpected scenario")
    require(ledger.get("status") == "SUCCEEDED", "master ledger is not SUCCEEDED")
    require(ledger.get("tenant") == tenant, "master ledger tenant does not match")
    final = ledger.get("final") or {}
    require(final.get("merchant_status") == "ACTIVE", "master Merchant is not ACTIVE")
    require(final.get("warehouse_status") == "ACTIVE", "master Warehouse is not ACTIVE")
    fields = ("merchant_id", "canonical_sku_id", "warehouse_id", "location_id")
    require(all(isinstance(final.get(field), str) and final.get(field) for field in fields),
            "master ledger is missing canonical Inventory v3 dimensions")
    return {"path": str(path), **{field: final[field] for field in fields}}


def build_payloads(run_id: str, master: dict, costed: bool = False) -> list[dict]:
    seed = int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16) % (365 * 24 * 60 * 60)
    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seed)
    costed_times = (
        dt.datetime(2026, 3, 1, 8, 0, 0, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 7, 10, 8, 0, 0, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 7, 10, 8, 1, 0, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 7, 11, 8, 0, 0, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 7, 11, 8, 1, 0, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 7, 11, 8, 2, 0, tzinfo=dt.timezone.utc),
    )
    correlation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:inventory-v3:{run_id}"))
    business_types = ("PURCHASE_RECEIPT", "TRADE_ORDER", "SHIPMENT", "SALE_RETURN", "TRADE_ORDER", "CANCEL")
    payloads = []
    for index, ((operation, quantity, _), business_type) in enumerate(zip(STEPS, business_types), 1):
        payload = {
            "operation": operation,
            "idempotencyKey": f"{run_id}-{index:02d}-{operation.lower()}",
            "sourceEventId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:inventory-v3:{run_id}:{index}")),
            "ownerType": "MERCHANT", "ownerId": master["merchant_id"],
            "canonicalSkuId": master["canonical_sku_id"], "warehouseId": master["warehouse_id"],
            "locationId": master["location_id"], "lotId": None,
            "stockStatus": "SELLABLE", "qualityStatus": "QUALIFIED", "baseUomCode": "PCS",
            "quantity": quantity, "businessType": business_type, "businessId": run_id,
            "businessItemId": f"line-{index}", "businessNo": f"CINV3-{run_id}",
            "correlationId": correlation_id,
            "occurredAt": (
                costed_times[index - 1] if costed else start + dt.timedelta(seconds=index)
            ).isoformat().replace("+00:00", "Z"),
        }
        if costed and operation in {"RECEIVE", "SHIP", "RETURN"}:
            unit_cost = 12000
            payload.update({
                "unitCostAmountMinor": unit_cost,
                "movementCostAmountMinor": int(Decimal(quantity) * unit_cost),
                "currencyCode": "CNY",
                "costSourceSystem": "CLOUDMOLD_PROCUREMENT_LOCAL_TEST",
                "costSourceRef": f"{run_id}:{index:02d}:{operation.lower()}",
                "costPolicyVersion": "FIFO_COST_V1",
            })
        if operation == "SHIP":
            payload["reservationId"] = "__FIRST_RESERVATION__"
        elif operation == "RELEASE":
            payload["reservationId"] = "__SECOND_RESERVATION__"
        payloads.append(payload)
    return payloads


def validate_result(result: dict, expected: tuple[str, str, str, str, int], operation: str) -> None:
    actual = (decimal(result["onHandQuantity"]), decimal(result["reservedQuantity"]),
              decimal(result["inTransitQuantity"]), decimal(result["availableQuantity"]),
              result["aggregateVersion"])
    require(actual == expected, f"{operation} invariant mismatch: expected={expected} actual={actual}")


def execute(args: argparse.Namespace) -> dict:
    master = load_master(args.master_ledger, args.tenant)
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        require(bool(args.username) and bool(args.password),
                "set token or username/password through environment variables")
        client.login(args.username, args.password)
    payloads = build_payloads(args.run_id, master, args.costed)
    reservations: list[str] = []
    issued: list[tuple[dict, dict]] = []
    ledger = {"scenario": "canonical-inventory-location-v3-first-slice", "run_id": args.run_id,
              "environment": args.environment, "tenant": args.tenant, "master_ledger": master["path"],
              "costed": args.costed,
              "dimensions": {"owner_type": "MERCHANT", "owner_id": master["merchant_id"],
                             "canonical_sku_id": master["canonical_sku_id"],
                             "warehouse_id": master["warehouse_id"], "location_id": master["location_id"],
                             "lot_id": None}, "steps": [], "status": "STARTED"}
    for index, (payload, (operation, _, expected)) in enumerate(zip(payloads, STEPS), 1):
        if payload.get("reservationId") == "__FIRST_RESERVATION__":
            payload["reservationId"] = reservations[0]
        elif payload.get("reservationId") == "__SECOND_RESERVATION__":
            payload["reservationId"] = reservations[1]
        result = client.request("POST", ROUTE, payload)
        validate_result(result, expected, operation)
        if operation == "RESERVE":
            reservations.append(result["reservationId"])
        ledger["steps"].append({"step": index, "operation": operation,
                                "request_hash": request_hash(payload), "result": result})
        issued.append((payload, result))
    replay = []
    for payload, first in issued:
        result = client.request("POST", ROUTE, payload)
        require(result.get("duplicate") is True, f"{payload['operation']} replay was not duplicate")
        require({key: value for key, value in result.items() if key != "duplicate"}
                == {key: value for key, value in first.items() if key != "duplicate"},
                f"{payload['operation']} replay changed immutable result")
        replay.append({"operation": payload["operation"], "duplicate": True})
    ledger["replay"] = replay
    ledger["final"] = ledger["steps"][-1]["result"]
    ledger["status"] = "SUCCEEDED"
    root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    directory = root / "inventory-v3" / args.run_id
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "ledger.json"
    if output.exists():
        output = directory / ("replay-ledger-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output),
            "final": ledger["final"], "all_replay_duplicate": True}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--token", default=os.getenv("CLOUDMOLD_ADMIN_TOKEN"))
    parser.add_argument("--username", default=os.getenv("CLOUDMOLD_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("CLOUDMOLD_ADMIN_PASSWORD"))
    parser.add_argument("--master-ledger", default=os.getenv("CLOUDMOLD_MASTER_LEDGER"))
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--costed", action="store_true",
                        help="emit complete LOCAL_TEST FIFO cost evidence on RECEIVE/SHIP/RETURN")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)), "unsafe run_id")
        require(args.environment in {"local", "demo", "test"}, "runner is restricted to local/demo/test")
        if args.mode == "plan":
            result = {"scenario": "canonical-inventory-location-v3-first-slice", "run_id": args.run_id,
                      "steps": [step[0] for step in STEPS], "lot_id": None,
                      "costed": args.costed,
                      "final_expected": ["8.000000", "0.000000", "0.000000", "8.000000"],
                      "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            require(ROUTE in paths and "post" in paths[ROUTE], f"live OpenAPI is missing {ROUTE}")
            result = {"status": "ready", "route": ROUTE, "side_effects": False}
        else:
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
