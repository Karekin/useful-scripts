#!/usr/bin/env python3
"""Produce controlled advertising and promotion-economics evidence through the real Admin API."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_ORDER_ID = "d1cbe695-6673-4c88-968b-478ca24d3076"
DEFAULT_BUYER_ID = "internal-buyer:ylf-001"
DEFAULT_MERCHANT_ID = "d9560649-d2b3-4959-9049-f6eef7094729"


def iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def http_json(method: str, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=encoded, method=method)
    for key, value in headers.items():
        req.add_header(key, value)
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {body}") from exc
    data = json.loads(body)
    if data.get("code") != 0:
        raise RuntimeError(f"{method} {url} returned {data}")
    return data


def login(base_url: str, tenant_id: int, username: str, password: str) -> str:
    result = http_json(
        "POST",
        f"{base_url}/admin-api/system/auth/login",
        {"tenant-id": str(tenant_id)},
        {"username": username, "password": password},
    )
    return result["data"]["accessToken"]


def execute(base_url: str, tenant_id: int, token: str, command: dict[str, Any]) -> dict[str, Any]:
    result = http_json(
        "POST",
        f"{base_url}/admin-api/cloudmold/promotion/command",
        {"tenant-id": str(tenant_id), "Authorization": f"Bearer {token}"},
        command,
    )
    return result["data"]


def query_starrocks(sql: str) -> list[list[str]]:
    completed = subprocess.run(
        [
            "docker", "exec", "yshopping-starrocks", "mysql", "-h127.0.0.1", "-P9030", "-uroot",
            "--batch", "--raw", "--skip-column-names", "-e", sql,
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return [line.split("\t") for line in completed.stdout.splitlines() if line.strip()]


def wait_for_metrics(tenant_id: int, campaign_id: str, timeout_seconds: int) -> dict[str, str]:
    deadline = time.time() + timeout_seconds
    last: list[list[str]] = []
    while time.time() < deadline:
        last = query_starrocks(
            f"""
            SELECT campaign_id, merchant_id, ad_roas_status, CAST(ad_roas AS STRING),
                   promotion_roi_status, CAST(promotion_roi AS STRING),
                   CAST(ad_spend_amount_minor AS STRING), CAST(attribution_amount_minor AS STRING),
                   CAST(incremental_contribution_profit_minor AS STRING), CAST(promotion_cost_minor AS STRING)
            FROM yshopping_ads.ads_canonical_marketing_campaign_performance
            WHERE tenant_id = {tenant_id} AND campaign_id = '{campaign_id}'
            """
        )
        if last and last[0][2] == "READY" and last[0][4] == "READY":
            row = last[0]
            return {
                "campaign_id": row[0],
                "merchant_id": row[1],
                "ad_roas_status": row[2],
                "ad_roas": row[3],
                "promotion_roi_status": row[4],
                "promotion_roi": row[5],
                "ad_spend_amount_minor": row[6],
                "attribution_amount_minor": row[7],
                "incremental_contribution_profit_minor": row[8],
                "promotion_cost_minor": row[9],
            }
        time.sleep(3)
    raise TimeoutError(f"timed out waiting for marketing metrics; last={last}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("CLOUDMOLD_BASE_URL", "http://127.0.0.1:48083"))
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--order-id", default=DEFAULT_ORDER_ID)
    parser.add_argument("--buyer-id", default=DEFAULT_BUYER_ID)
    parser.add_argument("--merchant-id", default=DEFAULT_MERCHANT_ID)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--run-id", default=f"marketing-economics-{uuid.uuid4().hex[:10]}")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path.home() / ".cloudmold" / "runs" / "marketing-economics",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    campaign_id = str(uuid.uuid4())
    placement_id = str(uuid.uuid4())
    impression_id = str(uuid.uuid4())
    click_id = str(uuid.uuid4())
    attribution_id = str(uuid.uuid4())
    experiment_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    campaign_from = now - timedelta(days=10)
    campaign_to = now + timedelta(days=10)
    measured_from = now - timedelta(days=7)
    measured_to = now - timedelta(hours=1)

    token = login(args.base_url, args.tenant_id, args.username, args.password)
    commands: list[dict[str, Any]] = []

    def command(operation: str, body_name: str, body: dict[str, Any], occurred_at: datetime | None = None) -> None:
        payload = {
            "operation": operation,
            "idempotencyKey": f"{args.run_id}:{operation}:{len(commands) + 1}",
            "correlationId": correlation_id,
            "occurredAt": iso(occurred_at or now),
            body_name: body,
        }
        result = execute(args.base_url, args.tenant_id, token, payload)
        commands.append({"request": payload, "result": result})

    command(
        "CREATE_CAMPAIGN",
        "campaign",
        {
            "campaignId": campaign_id,
            "campaignCode": f"AD-{args.run_id[-18:]}",
            "campaignKind": "ADVERTISING",
            "name": "受控商家广告与促销经济性验证",
            "startsAt": iso(campaign_from),
            "endsAt": iso(campaign_to),
        },
    )
    command("ACTIVATE_CAMPAIGN", "campaign", {"campaignId": campaign_id, "expectedVersion": 1})
    command(
        "CREATE_ADVERTISING_PLACEMENT",
        "advertisingPlacement",
        {
            "placementId": placement_id,
            "placementCode": f"PL-{args.run_id[-18:]}",
            "campaignId": campaign_id,
            "name": "商城首页商家推荐位",
            "channelCode": "YSHOPPING",
            "pageCode": "HOME",
            "slotCode": "MERCHANT_RECOMMEND_01",
            "creativeRef": f"creative:{args.run_id}",
            "validFrom": iso(campaign_from),
            "validTo": iso(campaign_to),
        },
    )
    command("ACTIVATE_ADVERTISING_PLACEMENT", "advertisingPlacement", {"placementId": placement_id, "expectedVersion": 1})
    command(
        "RECORD_IMPRESSION",
        "advertisingInteraction",
        {
            "interactionId": impression_id,
            "deduplicationKey": f"{args.run_id}:impression",
            "placementId": placement_id,
            "principalId": args.buyer_id,
            "sessionId": f"session:{args.run_id}",
        },
    )
    command(
        "RECORD_CLICK",
        "advertisingInteraction",
        {
            "interactionId": click_id,
            "deduplicationKey": f"{args.run_id}:click",
            "placementId": placement_id,
            "principalId": args.buyer_id,
            "sessionId": f"session:{args.run_id}",
            "sourceInteractionId": impression_id,
        },
    )
    command(
        "RECORD_ATTRIBUTION",
        "advertisingInteraction",
        {
            "interactionId": attribution_id,
            "deduplicationKey": f"{args.run_id}:attribution",
            "placementId": placement_id,
            "principalId": args.buyer_id,
            "sessionId": f"session:{args.run_id}",
            "sourceInteractionId": click_id,
            "orderRef": args.order_id,
            "attributionAmountMinor": 19900,
            "currencyCode": "CNY",
        },
    )
    command(
        "RECORD_ADVERTISING_LEDGER_ENTRY",
        "advertisingLedger",
        {
            "ledgerEntryId": str(uuid.uuid4()),
            "ledgerEntryCode": f"{args.run_id}:spend",
            "campaignId": campaign_id,
            "placementId": placement_id,
            "merchantId": args.merchant_id,
            "entryType": "SPEND",
            "chargeModel": "FIXED",
            "amountMinor": 5000,
            "currencyCode": "CNY",
        },
    )
    command(
        "RECORD_ADVERTISING_LEDGER_ENTRY",
        "advertisingLedger",
        {
            "ledgerEntryId": str(uuid.uuid4()),
            "ledgerEntryCode": f"{args.run_id}:revenue",
            "campaignId": campaign_id,
            "placementId": placement_id,
            "merchantId": args.merchant_id,
            "entryType": "REVENUE",
            "chargeModel": "SETTLEMENT",
            "revenueType": "ADVERTISING",
            "sourceInteractionId": attribution_id,
            "orderRef": args.order_id,
            "amountMinor": 1200,
            "currencyCode": "CNY",
        },
    )
    command(
        "UPSERT_PROMOTION_EXPERIMENT_RESULT",
        "promotionExperimentResult",
        {
            "experimentId": experiment_id,
            "experimentCode": f"EXP-{args.run_id[-18:]}",
            "campaignId": campaign_id,
            "merchantId": args.merchant_id,
            "measuredFrom": iso(measured_from),
            "measuredTo": iso(measured_to),
            "baselineContributionProfitMinor": 12000,
            "treatmentContributionProfitMinor": 18000,
            "incrementalContributionProfitMinor": 6000,
            "promotionCostMinor": 8000,
            "eligiblePopulationCount": 1000,
            "treatmentPopulationCount": 500,
            "controlPopulationCount": 500,
            "currencyCode": "CNY",
            "methodologyRef": "randomized-holdout-normalized-baseline-v1",
        },
    )

    metrics = wait_for_metrics(args.tenant_id, campaign_id, args.timeout_seconds)
    run_dir = args.output_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    ledger = {
        "run_id": args.run_id,
        "environment": "LOCAL_TEST",
        "tenant_id": args.tenant_id,
        "base_url": args.base_url,
        "order_id": args.order_id,
        "buyer_id": args.buyer_id,
        "merchant_id": args.merchant_id,
        "campaign_id": campaign_id,
        "placement_id": placement_id,
        "commands": commands,
        "metrics": metrics,
    }
    ledger_path = run_dir / "ledger.json"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ledger": str(ledger_path), "metrics": metrics}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
