#!/usr/bin/env python3
"""Create one additional paid listing-backed order for an existing buyer and verify 90d repeat purchase evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_BASE_URL = "http://127.0.0.1:48080"
DEFAULT_TENANT_ID = 1
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"
DEFAULT_BUYER_ID = "internal-buyer:ylf-001"
DEFAULT_LISTING_ID = "e6c26600-11eb-4777-affe-ab9d25729c9c"
DEFAULT_LISTING_OFFER_ID = "d09338db-2f48-4749-bc0a-26d908cf1cfb"
DEFAULT_CANONICAL_SKU_ID = "107e4efe-0411-458d-ac7d-8b4b92e682b1"
DEFAULT_MERCHANT_ID = "d9560649-d2b3-4959-9049-f6eef7094729"
DEFAULT_WAREHOUSE_ID = "72778a33-4015-49b7-b786-5abda7d688ee"
DEFAULT_PRICE_MINOR = 19900
DEFAULT_MERCHANDISE_COST_MINOR = 12000
DEFAULT_QUANTITY = 1
DEFAULT_TIMEOUT_SECONDS = 180


@dataclass
class Config:
    base_url: str
    tenant_id: int
    username: str
    password: str
    buyer_id: str
    listing_id: str
    listing_offer_id: str
    canonical_sku_id: str
    merchant_id: str
    warehouse_id: str
    price_minor: int
    merchandise_cost_minor: int
    quantity: int
    timeout_seconds: int
    run_id: str
    output_root: Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {raw}") from exc
    data = json.loads(raw)
    if data.get("code") != 0:
        raise RuntimeError(f"{method} {url} returned code={data.get('code')}: {raw}")
    return data


def login(config: Config) -> str:
    payload = {"username": config.username, "password": config.password}
    data = http_json(
        "POST",
        f"{config.base_url}/admin-api/system/auth/login",
        headers={"tenant-id": str(config.tenant_id)},
        payload=payload,
    )
    token = data["data"]["accessToken"]
    if not token:
        raise RuntimeError("login succeeded but access token is empty")
    return token


def post_command(
    config: Config,
    token: str,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    data = http_json(
        "POST",
        f"{config.base_url}{path}",
        headers={
            "tenant-id": str(config.tenant_id),
            "Authorization": f"Bearer {token}",
        },
        payload=payload,
    )
    return data["data"]


def starrocks_query(sql: str) -> list[list[str]]:
    import subprocess

    command = [
        "docker",
        "exec",
        "yshopping-starrocks",
        "mysql",
        "-h127.0.0.1",
        "-P9030",
        "-uroot",
        "--batch",
        "--raw",
        "--skip-column-names",
        "-e",
        sql,
    ]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"starrocks query failed: {completed.stderr.strip() or completed.stdout.strip()}")
    rows: list[list[str]] = []
    for line in completed.stdout.splitlines():
        line = line.rstrip("\n")
        if not line:
            continue
        rows.append(line.split("\t"))
    return rows


def current_metrics() -> dict[str, dict[str, str]]:
    rows = starrocks_query(
        """
        SELECT metric_id,
               CAST(metric_value AS STRING),
               COALESCE(evidence_note, ''),
               CAST(data_freshness_at AS STRING)
        FROM yshopping_ads.ads_ecommerce_role_metrics
        WHERE tenant_id = 1
          AND metric_id IN (
            'buyer.repeat_purchase_rate_90d',
            'buyer.order_frequency_90d',
            'commerce.paid_buyer_count',
            'commerce.net_gmv_yuan'
          )
        ORDER BY metric_id
        """
    )
    return {
        row[0]: {"value": row[1], "note": row[2], "freshness": row[3] if len(row) > 3 else ""}
        for row in rows
    }


def query_order_snapshot(order_id: str) -> dict[str, str] | None:
    rows = starrocks_query(
        f"""
        SELECT order_id, buyer_id, current_status, payment_id, CAST(aggregate_version AS STRING), CAST(recorded_at AS STRING)
        FROM yshopping_dim.dim_canonical_order_current
        WHERE tenant_id = 1 AND order_id = '{order_id}'
        """
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "order_id": row[0],
        "buyer_id": row[1],
        "current_status": row[2],
        "payment_id": row[3],
        "order_version": row[4],
        "recorded_at": row[5] if len(row) > 5 else "",
    }


def query_payment_snapshot(payment_id: str) -> dict[str, str] | None:
    rows = starrocks_query(
        f"""
        SELECT payment_id, order_id, current_status,
               CAST(captured_amount_minor AS STRING),
               CAST(refunded_amount_minor AS STRING),
               CAST(aggregate_version AS STRING),
               CAST(recorded_at AS STRING)
        FROM yshopping_dim.dim_canonical_payment_current
        WHERE tenant_id = 1 AND payment_id = '{payment_id}'
        """
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "payment_id": row[0],
        "order_id": row[1],
        "current_status": row[2],
        "captured_amount_minor": row[3],
        "refunded_amount_minor": row[4],
        "payment_version": row[5],
        "recorded_at": row[6] if len(row) > 6 else "",
    }


def query_buyer_rollup(buyer_id: str) -> dict[str, str] | None:
    rows = starrocks_query(
        f"""
        WITH paid_orders AS (
            SELECT
                o.buyer_id,
                o.order_id,
                p.recorded_at
            FROM yshopping_dim.dim_canonical_order_current o
            JOIN yshopping_dim.dim_canonical_payment_current p
              ON p.tenant_id = o.tenant_id
             AND p.payment_id = o.payment_id
            WHERE o.tenant_id = 1
              AND o.buyer_id = '{buyer_id}'
              AND p.current_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
              AND p.captured_amount_minor > 0
        ),
        anchor AS (
            SELECT MAX(recorded_at) AS window_end_at FROM paid_orders
        )
        SELECT
            '{buyer_id}',
            CAST(COUNT(DISTINCT p.order_id) AS STRING),
            CAST(MIN(p.recorded_at) AS STRING),
            CAST(MAX(p.recorded_at) AS STRING)
        FROM paid_orders p
        JOIN anchor a
          ON p.recorded_at >= DATE_SUB(a.window_end_at, INTERVAL 90 DAY)
        """
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "buyer_id": row[0],
        "paid_order_count_90d": row[1],
        "first_paid_at": row[2],
        "last_paid_at": row[3],
    }


def wait_for_evidence(config: Config, order_id: str, payment_id: str, buyer_id: str, before_metrics: dict[str, dict[str, str]]) -> dict[str, Any]:
    deadline = time.time() + config.timeout_seconds
    target_repeat = float(before_metrics["buyer.repeat_purchase_rate_90d"]["value"])
    target_paid_buyers = float(before_metrics["commerce.paid_buyer_count"]["value"])
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        order_snapshot = query_order_snapshot(order_id)
        payment_snapshot = query_payment_snapshot(payment_id)
        buyer_rollup = query_buyer_rollup(buyer_id)
        metrics = current_metrics()
        last_state = {
            "order_snapshot": order_snapshot,
            "payment_snapshot": payment_snapshot,
            "buyer_rollup": buyer_rollup,
            "metrics": metrics,
        }
        repeat_value = float(metrics["buyer.repeat_purchase_rate_90d"]["value"])
        paid_buyer_value = float(metrics["commerce.paid_buyer_count"]["value"])
        buyer_paid_orders = int(buyer_rollup["paid_order_count_90d"]) if buyer_rollup else 0
        if order_snapshot and payment_snapshot and buyer_paid_orders >= 2 and (
            repeat_value > target_repeat or paid_buyer_value >= target_paid_buyers
        ):
            return last_state
        time.sleep(3)
    raise TimeoutError(f"timed out waiting for StarRocks evidence: {json.dumps(last_state, ensure_ascii=False)}")


def make_run_dir(config: Config) -> Path:
    run_dir = config.output_root / config.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("CLOUDMOLD_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--tenant-id", type=int, default=int(os.environ.get("CLOUDMOLD_TENANT_ID", DEFAULT_TENANT_ID)))
    parser.add_argument("--username", default=os.environ.get("CLOUDMOLD_ADMIN_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--password", default=os.environ.get("CLOUDMOLD_ADMIN_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument("--buyer-id", default=DEFAULT_BUYER_ID)
    parser.add_argument("--listing-id", default=DEFAULT_LISTING_ID)
    parser.add_argument("--listing-offer-id", default=DEFAULT_LISTING_OFFER_ID)
    parser.add_argument("--canonical-sku-id", default=DEFAULT_CANONICAL_SKU_ID)
    parser.add_argument("--merchant-id", default=DEFAULT_MERCHANT_ID)
    parser.add_argument("--warehouse-id", default=DEFAULT_WAREHOUSE_ID)
    parser.add_argument("--price-minor", type=int, default=DEFAULT_PRICE_MINOR)
    parser.add_argument(
        "--merchandise-cost-minor",
        type=int,
        default=DEFAULT_MERCHANDISE_COST_MINOR,
        help="Exact merchandise cost snapshot written through the order API for profitability evidence",
    )
    parser.add_argument("--quantity", type=int, default=DEFAULT_QUANTITY)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--run-id", default=f"repeat-purchase-{uuid.uuid4().hex[:12]}")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs"))) / "repeat-purchase",
    )
    args = parser.parse_args()

    config = Config(
        base_url=args.base_url.rstrip("/"),
        tenant_id=args.tenant_id,
        username=args.username,
        password=args.password,
        buyer_id=args.buyer_id,
        listing_id=args.listing_id,
        listing_offer_id=args.listing_offer_id,
        canonical_sku_id=args.canonical_sku_id,
        merchant_id=args.merchant_id,
        warehouse_id=args.warehouse_id,
        price_minor=args.price_minor,
        merchandise_cost_minor=args.merchandise_cost_minor,
        quantity=args.quantity,
        timeout_seconds=args.timeout_seconds,
        run_id=args.run_id,
        output_root=args.output_root,
    )

    run_dir = make_run_dir(config)
    ledger: dict[str, Any] = {
        "scenario": "canonical-repeat-purchase-v1",
        "run_id": config.run_id,
        "environment": "local_test",
        "tenant_id": config.tenant_id,
        "buyer_id": config.buyer_id,
        "listing": {
            "listing_id": config.listing_id,
            "listing_offer_id": config.listing_offer_id,
            "canonical_sku_id": config.canonical_sku_id,
            "merchant_id": config.merchant_id,
            "warehouse_id": config.warehouse_id,
            "price_minor": config.price_minor,
            "merchandise_cost_minor": config.merchandise_cost_minor,
            "quantity": config.quantity,
        },
        "started_at": isoformat(utc_now()),
        "calls": [],
    }

    try:
        token = login(config)
        before_metrics = current_metrics()
        ledger["before_metrics"] = before_metrics

        correlation_id = str(uuid.uuid4())
        order_occurred_at = utc_now() - timedelta(minutes=2)
        reserve_occurred_at = order_occurred_at + timedelta(seconds=15)
        payment_occurred_at = order_occurred_at + timedelta(seconds=30)

        place_payload = {
            "operation": "PLACE_FROM_LISTING",
            "idempotencyKey": f"{config.run_id}:order:place",
            "runId": config.run_id,
            "buyerId": config.buyer_id,
            "items": [
                {
                    "lineKey": "line-1",
                    "canonicalSkuId": config.canonical_sku_id,
                    "quantity": config.quantity,
                    "unitPriceMinor": config.price_minor,
                    "merchandiseCostMinor": config.merchandise_cost_minor,
                    "listingId": config.listing_id,
                    "listingOfferId": config.listing_offer_id,
                }
            ],
            "benefitApplications": [],
            "shippingAmountMinor": 0,
            "discountAmountMinor": 0,
            "currencyCode": "CNY",
            "correlationId": correlation_id,
            "occurredAt": isoformat(order_occurred_at),
        }
        place_result = post_command(config, token, "/admin-api/cloudmold/order/command", place_payload)
        ledger["calls"].append({"path": "/admin-api/cloudmold/order/command", "payload": place_payload, "result": place_result})

        order_id = place_result["orderId"]
        order_no = place_result["orderNo"]
        order_item_id = place_result["items"][0]["orderItemId"]

        reserve_payload = {
            "operation": "RESERVE",
            "idempotencyKey": f"{config.run_id}:inventory:reserve",
            "ownerId": config.merchant_id,
            "canonicalSkuId": config.canonical_sku_id,
            "warehouseId": config.warehouse_id,
            "stockStatus": "SELLABLE",
            "qualityStatus": "QUALIFIED",
            "uomCode": "PCS",
            "quantity": config.quantity,
            "businessType": "TRADE_ORDER",
            "businessId": order_id,
            "businessItemId": order_item_id,
            "businessNo": order_no,
            "sourceEventId": str(uuid.uuid4()),
            "correlationId": correlation_id,
            "causationId": correlation_id,
            "occurredAt": isoformat(reserve_occurred_at),
        }
        reserve_result = post_command(config, token, "/admin-api/cloudmold/inventory/command", reserve_payload)
        ledger["calls"].append({"path": "/admin-api/cloudmold/inventory/command", "payload": reserve_payload, "result": reserve_result})

        confirm_inventory_payload = {
            "operation": "CONFIRM_INVENTORY",
            "idempotencyKey": f"{config.run_id}:order:confirm-inventory",
            "runId": config.run_id,
            "orderId": order_id,
            "expectedVersion": place_result["aggregateVersion"],
            "reservationReferences": [{"orderItemId": order_item_id, "reservationId": reserve_result["reservationId"]}],
            "correlationId": correlation_id,
            "causationId": correlation_id,
            "occurredAt": isoformat(reserve_occurred_at + timedelta(seconds=5)),
        }
        confirm_inventory_result = post_command(
            config, token, "/admin-api/cloudmold/order/command", confirm_inventory_payload
        )
        ledger["calls"].append(
            {"path": "/admin-api/cloudmold/order/command", "payload": confirm_inventory_payload, "result": confirm_inventory_result}
        )

        payment_payload = {
            "operation": "CAPTURE",
            "idempotencyKey": f"{config.run_id}:payment:capture",
            "runId": config.run_id,
            "orderId": order_id,
            "amountMinor": config.price_minor * config.quantity,
            "currencyCode": "CNY",
            "providerCode": "INTERNAL_TEST",
            "providerTransactionId": f"txn-{config.run_id}",
            "reason": "repeat purchase evidence",
            "correlationId": correlation_id,
            "causationId": correlation_id,
            "occurredAt": isoformat(payment_occurred_at),
        }
        payment_result = post_command(config, token, "/admin-api/cloudmold/payment/command", payment_payload)
        ledger["calls"].append({"path": "/admin-api/cloudmold/payment/command", "payload": payment_payload, "result": payment_result})

        confirm_payment_payload = {
            "operation": "CONFIRM_PAYMENT",
            "idempotencyKey": f"{config.run_id}:order:confirm-payment",
            "runId": config.run_id,
            "orderId": order_id,
            "expectedVersion": confirm_inventory_result["aggregateVersion"],
            "paymentId": payment_result["paymentId"],
            "correlationId": correlation_id,
            "causationId": correlation_id,
            "occurredAt": isoformat(payment_occurred_at + timedelta(seconds=5)),
        }
        confirm_payment_result = post_command(
            config, token, "/admin-api/cloudmold/order/command", confirm_payment_payload
        )
        ledger["calls"].append(
            {"path": "/admin-api/cloudmold/order/command", "payload": confirm_payment_payload, "result": confirm_payment_result}
        )

        evidence = wait_for_evidence(config, order_id, payment_result["paymentId"], config.buyer_id, before_metrics)
        ledger["after_metrics"] = evidence["metrics"]
        ledger["order_snapshot"] = evidence["order_snapshot"]
        ledger["payment_snapshot"] = evidence["payment_snapshot"]
        ledger["buyer_rollup"] = evidence["buyer_rollup"]
        ledger["status"] = "SUCCEEDED"
    except Exception as exc:
        ledger["status"] = "FAILED"
        ledger["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        ledger["finished_at"] = isoformat(utc_now())
        ledger_path = run_dir / "ledger.json"
        ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"run_id": config.run_id, "ledger": str(ledger_path), "status": ledger["status"]}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error surface
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
