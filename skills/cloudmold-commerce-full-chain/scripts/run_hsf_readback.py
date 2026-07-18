#!/usr/bin/env python3
"""Extract terminal identities from a commerce run and verify every read port through Dubbo."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def load_succeeded(path: Path, label: str) -> dict:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    catalog_complete = (label == "catalog"
                        and (value.get("final") or {}).get("catalog_status") == "ACTIVE")
    if value.get("status") != "SUCCEEDED" and not catalog_complete:
        raise RuntimeError(f"{label} ledger is not SUCCEEDED: {path}")
    return value


def successful_step(ledger: dict, operation: str) -> dict:
    for attempt in reversed(ledger.get("attempts") or []):
        for step in reversed(attempt.get("steps") or []):
            if (step.get("operation") == operation and step.get("status") == "SUCCEEDED"
                    and not str(step.get("domain", "")).startswith("replay:")):
                result = step.get("response") or step.get("result")
                if isinstance(result, dict):
                    return result
    raise RuntimeError(f"commerce ledger has no successful {operation} result")


def build_input(commerce: dict, catalog: dict, master: dict) -> dict:
    catalog_final = catalog.get("final") or {}
    master_final = master.get("final") or {}
    terminal = commerce.get("final") or {}
    listing = terminal.get("listing") or successful_step(commerce, "PUBLISH")
    order = successful_step(commerce, "COMPLETE_AFTER_DELIVERY")
    payment = successful_step(commerce, "CAPTURE")
    fulfillment = terminal.get("forward_fulfillment") or successful_step(commerce, "DELIVER")
    aftersale = terminal.get("aftersales") or successful_step(commerce, "ACCEPT_INSPECTION")
    offers = [item for item in listing.get("offers") or [] if item.get("enabled") is True]
    items = order.get("items") or []
    if len(offers) != 1 or len(items) != 1:
        raise RuntimeError("readback requires one enabled Listing Offer and one exact Order item")
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "authority": {
            "reference": {"merchantId": master_final["merchant_id"], "shopId": master_final["shop_id"]},
            "operator": {
                "merchantId": master_final["merchant_id"], "shopId": master_final["shop_id"],
                "principalId": master_final["principal_id"], "roleCode": "OWNER"
            }
        },
        "product": {"skuId": items[0]["canonicalSkuId"], "spuId": catalog_final["spu_id"]},
        "listing": {"validation": {
            "listingId": listing["listingId"], "listingOfferId": offers[0]["listingOfferId"],
            "canonicalSkuId": offers[0]["canonicalSkuId"],
            "expectedPriceMinor": offers[0]["priceMinor"], "currencyCode": offers[0]["currencyCode"]
        }},
        "order": {"orderId": order["orderId"], "orderItemId": items[0]["orderItemId"]},
        "payment": {"paymentId": payment["paymentId"],
                    "amountMinor": aftersale["approvedAmountMinor"], "currencyCode": aftersale["currencyCode"]},
        "fulfillment": {"fulfillmentId": fulfillment["fulfillmentId"],
                        "shipmentId": fulfillment["shipmentId"]},
        "aftersale": {"afterSaleId": aftersale["afterSaleId"],
                      "returnFulfillmentId": aftersale["returnFulfillmentId"]},
        "warehouse": {
            "warehouseId": master_final["warehouse_id"], "locationId": master_final["location_id"],
            "source": {"sourceSystem": "ERP", "sourceType": "WAREHOUSE",
                       "sourceId": master_final["warehouse_source"]["source_id"]},
            "eligibilityAt": now
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commerce-ledger", required=True, type=Path)
    parser.add_argument("--catalog-ledger", required=True, type=Path)
    parser.add_argument("--master-ledger", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument("--operator-id", type=int, default=1)
    parser.add_argument("--operator-type", type=int, default=1)
    args = parser.parse_args()
    commerce = load_succeeded(args.commerce_ledger, "commerce")
    catalog = load_succeeded(args.catalog_ledger, "catalog")
    master = load_succeeded(args.master_ledger, "master")
    payload = build_input(commerce, catalog, master)
    skill_dir = Path(__file__).resolve().parent.parent
    useful_scripts = skill_dir.parents[1]
    with tempfile.TemporaryDirectory(prefix="cloudmold-hsf-readback-") as directory:
        input_path = Path(directory) / "input.json"
        input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        command = [
            sys.executable, str(useful_scripts / "scripts/yudao_dubbo_flow.py"), "execute",
            "--scenario", str(skill_dir / "references/readback-scenario.json"),
            "--input-json", str(input_path), "--tenant-id", str(args.tenant_id),
            "--operator-id", str(args.operator_id), "--operator-type", str(args.operator_type),
            "--skill-id", "skill.cloudmold.commerce.full-chain-hsf.v1", "--run-id", args.run_id,
            "--evidence-root", str(Path.home() / ".cloudmold/runs/commerce-readback"),
        ]
        return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
