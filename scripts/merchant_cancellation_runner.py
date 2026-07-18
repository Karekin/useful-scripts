#!/usr/bin/env python3
"""Create a real merchant-responsible paid cancellation and wait for lakehouse metrics."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from repeat_purchase_runner import http_json, isoformat, post_command, starrocks_query, utc_now


@dataclass
class Config:
    base_url: str
    tenant_id: int
    username: str
    password: str
    run_id: str
    paid_order_ledger: Path
    output_root: Path
    variable_fulfillment_cost_minor: int
    timeout_seconds: int


def login(config: Config) -> str:
    response = http_json(
        "POST",
        f"{config.base_url}/admin-api/system/auth/login",
        headers={"tenant-id": str(config.tenant_id)},
        payload={"username": config.username, "password": config.password},
    )
    return response["data"]["accessToken"]


def get_saga(config: Config, token: str, saga_id: str) -> dict[str, Any]:
    response = http_json(
        "GET",
        f"{config.base_url}/admin-api/cloudmold/order-cancellation-saga/get?{urlencode({'sagaId': saga_id})}",
        headers={"tenant-id": str(config.tenant_id), "Authorization": f"Bearer {token}"},
    )
    return response["data"]


def paid_order_facts(path: Path) -> dict[str, Any]:
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("status") != "SUCCEEDED":
        raise ValueError("paid-order ledger is not successful")
    results = [entry["result"] for entry in ledger["calls"]]
    place = next(result for result in results if result.get("currentStatus") == "PLACED")
    reserve = next(result for result in results if result.get("reservationId"))
    payment = next(result for result in results if result.get("currentStatus") == "CAPTURED")
    confirmed = next(result for result in results if result.get("currentStatus") == "PAYMENT_CONFIRMED")
    listing = ledger["listing"]
    item = confirmed["items"][0]
    return {
        "paid_order_run_id": ledger["run_id"],
        "order_id": confirmed["orderId"],
        "order_no": confirmed["orderNo"],
        "order_version": confirmed["aggregateVersion"],
        "order_item_id": item["orderItemId"],
        "canonical_sku_id": item["canonicalSkuId"],
        "quantity": item["quantity"],
        "reservation_id": reserve["reservationId"],
        "payment_id": payment["paymentId"],
        "payable_amount_minor": confirmed["payableAmountMinor"],
        "merchant_id": listing["merchant_id"],
        "warehouse_id": listing["warehouse_id"],
        "listing_offer_id": item["listingOfferId"],
        "place_operation_id": place["operationId"],
    }


def metric_evidence(config: Config, saga_id: str, order_id: str) -> dict[str, Any] | None:
    cancellation_rows = starrocks_query(
        f"""
        SELECT saga_id, order_id, order_status_at_request, responsibility_party,
               responsibility_code, CAST(counts_toward_paid_cancellation_rate AS STRING),
               saga_status, order_status, CAST(data_freshness_at AS STRING)
        FROM yshopping_dws.dws_canonical_merchant_cancellation_current
        WHERE tenant_id = {config.tenant_id} AND saga_id = '{saga_id}'
        """
    )
    metric_rows = starrocks_query(
        f"""
        SELECT metric_id, CAST(metric_value AS STRING), CAST(numerator AS STRING),
               CAST(denominator AS STRING), CAST(source_row_count AS STRING),
               CAST(data_freshness_at AS STRING)
        FROM yshopping_ads.ads_canonical_merchant_cancellation_metrics
        WHERE tenant_id = {config.tenant_id}
        """
    )
    sales_rows = starrocks_query(
        f"""
        SELECT metric_id, merchant_id, CAST(metric_value AS STRING),
               CAST(numerator AS STRING), CAST(source_row_count AS STRING),
               CAST(data_freshness_at AS STRING)
        FROM yshopping_ads.ads_canonical_merchant_sales_metrics
        WHERE tenant_id = {config.tenant_id}
        """
    )
    item_rows = starrocks_query(
        f"""
        SELECT order_id, order_item_id, merchant_id,
               CAST(merchant_booked_sales_amount_minor AS STRING),
               CAST(merchant_refund_deduction_amount_minor AS STRING),
               CAST(merchant_cancellation_deduction_amount_minor AS STRING),
               CAST(merchant_net_sales_amount_minor AS STRING),
               COALESCE(merchant_cancellation_saga_id, '')
        FROM yshopping_dws.dws_canonical_merchant_order_item_sales_current
        WHERE tenant_id = {config.tenant_id} AND order_id = '{order_id}'
        """
    )
    if not cancellation_rows or not metric_rows or not sales_rows or not item_rows:
        return None
    metric = metric_rows[0]
    cancellation = cancellation_rows[0]
    item = item_rows[0]
    if (
        cancellation[2] != "PAYMENT_CONFIRMED"
        or cancellation[3] != "MERCHANT"
        or cancellation[4] != "MERCHANT_STOCKOUT"
        or cancellation[5].lower() not in {"true", "1"}
        or cancellation[6] != "COMPLETED"
        or cancellation[7] != "CANCELLED"
        or float(metric[2]) < 1
        or item[7] != saga_id
        or int(item[6]) != 0
    ):
        return None
    return {
        "merchant_cancellation": cancellation_rows,
        "merchant_cancellation_metric": metric_rows,
        "merchant_sales_metric": sales_rows,
        "cancelled_order_item_sales": item_rows,
    }


def wait_for_completion(config: Config, token: str, saga_id: str, order_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.time() + config.timeout_seconds
    last_saga: dict[str, Any] = {}
    while time.time() < deadline:
        last_saga = get_saga(config, token, saga_id)
        if last_saga.get("status") == "COMPLETED":
            break
        if last_saga.get("status") == "MANUAL_REVIEW":
            raise RuntimeError(f"cancellation Saga requires manual review: {last_saga}")
        time.sleep(2)
    else:
        raise TimeoutError(f"timed out waiting for cancellation Saga: {last_saga}")

    while time.time() < deadline:
        evidence = metric_evidence(config, saga_id, order_id)
        if evidence is not None:
            return last_saga, evidence
        time.sleep(3)
    raise TimeoutError("timed out waiting for merchant cancellation lakehouse evidence")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("CLOUDMOLD_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant-id", type=int, default=int(os.environ.get("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--username", default=os.environ.get("CLOUDMOLD_ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("CLOUDMOLD_ADMIN_PASSWORD", "admin123"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--paid-order-ledger", type=Path, required=True)
    parser.add_argument("--variable-fulfillment-cost-minor", type=int, default=1200)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Resume evidence polling from this runner's existing failed ledger without issuing commands again",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path.home() / ".cloudmold" / "runs" / "merchant-cancellation",
    )
    args = parser.parse_args()
    config = Config(
        base_url=args.base_url.rstrip("/"), tenant_id=args.tenant_id,
        username=args.username, password=args.password, run_id=args.run_id,
        paid_order_ledger=args.paid_order_ledger, output_root=args.output_root,
        variable_fulfillment_cost_minor=args.variable_fulfillment_cost_minor,
        timeout_seconds=args.timeout_seconds,
    )
    run_dir = config.output_root / config.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = run_dir / "ledger.json"
    if ledger_path.exists() and not args.resume_existing:
        raise FileExistsError(f"run ledger already exists: {ledger_path}")

    if args.resume_existing:
        if not ledger_path.exists():
            raise FileNotFoundError(f"run ledger does not exist: {ledger_path}")
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        if (
            ledger.get("scenario") != "canonical-merchant-responsible-paid-cancellation-v1"
            or ledger.get("tenant_id") != config.tenant_id
            or ledger.get("run_id") != config.run_id
            or ledger.get("paid_order_ledger") != str(config.paid_order_ledger)
        ):
            raise ValueError("existing ledger does not match the requested cancellation evidence run")
        ledger["resumed_at"] = isoformat(utc_now())
    else:
        ledger = {
            "scenario": "canonical-merchant-responsible-paid-cancellation-v1",
            "environment": "local_test",
            "tenant_id": config.tenant_id,
            "run_id": config.run_id,
            "paid_order_ledger": str(config.paid_order_ledger),
            "started_at": isoformat(utc_now()),
            "calls": [],
        }
    try:
        facts = paid_order_facts(config.paid_order_ledger)
        if facts["paid_order_run_id"] != config.run_id:
            raise ValueError(
                "run-id must equal the paid-order run_id so the governed Payment refund remains in the same run"
            )
        ledger["paid_order"] = facts
        token = login(config)
        if args.resume_existing:
            saga_call = next(
                call
                for call in ledger["calls"]
                if call.get("path") == "/admin-api/cloudmold/order-cancellation-saga/command"
            )
            saga_id = saga_call["result"]["sagaId"]
            terminal, evidence = wait_for_completion(config, token, saga_id, facts["order_id"])
            ledger["terminal_saga"] = terminal
            ledger["lakehouse_evidence"] = evidence
            ledger["status"] = "SUCCEEDED"
            ledger.pop("error", None)
            return 0
        correlation_id = str(uuid.uuid4())
        occurred_at = utc_now()
        fulfillment_payload = {
            "operation": "CREATE",
            "idempotencyKey": f"{config.run_id}:fulfillment:create",
            "runId": config.run_id,
            "orderId": facts["order_id"],
            "sellerId": facts["merchant_id"],
            "warehouseId": facts["warehouse_id"],
            "items": [{
                "orderItemId": facts["order_item_id"],
                "canonicalSkuId": facts["canonical_sku_id"],
                "quantity": facts["quantity"],
                "reservationId": facts["reservation_id"],
                "variableFulfillmentCostMinor": config.variable_fulfillment_cost_minor,
            }],
            "reason": "merchant cancellation metric evidence",
            "correlationId": correlation_id,
            "causationId": correlation_id,
            "occurredAt": isoformat(occurred_at),
        }
        fulfillment = post_command(config, token, "/admin-api/cloudmold/fulfillment/command", fulfillment_payload)
        ledger["calls"].append({"path": "/admin-api/cloudmold/fulfillment/command", "payload": fulfillment_payload, "result": fulfillment})

        saga_payload = {
            "operation": "START",
            "cancellationMode": "PAID_UNSHIPPED",
            "responsibilityParty": "MERCHANT",
            "responsibilityCode": "MERCHANT_STOCKOUT",
            "idempotencyKey": f"{config.run_id}:cancellation:start",
            "runId": config.run_id,
            "orderId": facts["order_id"],
            "reason": "merchant stockout local-test evidence",
            "correlationId": correlation_id,
            "causationId": correlation_id,
            "occurredAt": isoformat(occurred_at + timedelta(seconds=5)),
        }
        saga = post_command(config, token, "/admin-api/cloudmold/order-cancellation-saga/command", saga_payload)
        ledger["calls"].append({"path": "/admin-api/cloudmold/order-cancellation-saga/command", "payload": saga_payload, "result": saga})
        terminal, evidence = wait_for_completion(config, token, saga["sagaId"], facts["order_id"])
        ledger["terminal_saga"] = terminal
        ledger["lakehouse_evidence"] = evidence
        ledger["status"] = "SUCCEEDED"
    except Exception as exc:
        ledger["status"] = "FAILED"
        ledger["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        ledger["finished_at"] = isoformat(utc_now())
        ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"run_id": config.run_id, "ledger": str(ledger_path), "status": ledger["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
