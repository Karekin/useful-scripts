#!/usr/bin/env python3
"""Validate and summarize a retained canonical commerce E2E ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(path: Path) -> dict:
    require(path.is_file(), f"missing ledger: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate(run_root: Path, run_id: str) -> dict:
    parent_path = run_root / "yshopping-aftersales" / run_id / "ledger.json"
    parent = load(parent_path)
    require(parent.get("run_id") == run_id, "parent run_id mismatch")
    require(parent.get("status") == "SUCCEEDED", "canonical parent ledger is not SUCCEEDED")

    child_ids = parent.get("child_run_ids", {})
    required_children = {"catalog", "projection", "master", "aftersales"}
    require(required_children <= child_ids.keys(), "canonical parent ledger is missing child run IDs")
    child_paths = {
        "catalog": run_root / "catalog" / child_ids["catalog"] / "ledger.json",
        "projection": run_root / "projection" / child_ids["projection"] / "ledger.json",
        "master": run_root / "merchant-warehouse" / child_ids["master"] / "ledger.json",
        "aftersales": run_root / "aftersales" / child_ids["aftersales"] / "ledger.json",
    }
    children = {name: load(path) for name, path in child_paths.items()}
    catalog = children["catalog"].get("final", {})
    projection = children["projection"].get("final", {})
    master = children["master"].get("final", {})
    aftersales_ledger = children["aftersales"]
    aftersales = aftersales_ledger.get("final", {})
    case = aftersales.get("aftersales", {})

    require(catalog.get("catalog_status") == "ACTIVE", "catalog is not ACTIVE")
    require(catalog.get("sku_count", 0) > 0, "catalog contains no SKU")
    require(projection.get("projection_count") == catalog.get("sku_count") * 3,
            "Mall/ERP/WMS projection count does not cover every SKU")
    require(children["master"].get("status") == "SUCCEEDED", "merchant master ledger failed")
    require(master.get("merchant_status") == "ACTIVE", "merchant is not ACTIVE")
    require(master.get("shop_status") == "ACTIVE", "shop is not ACTIVE")
    require(master.get("warehouse_status") == "ACTIVE", "warehouse is not ACTIVE")
    require(aftersales_ledger.get("status") == "SUCCEEDED", "after-sales child ledger failed")
    require(aftersales.get("all_replay_duplicate") is True, "command replay is not fully idempotent")
    require(case.get("caseStatus") == "COMPLETED", "after-sales case is not COMPLETED")
    require(case.get("refundStatus") == "SUCCEEDED", "refund did not succeed")
    require(case.get("resolutionSagaStatus") == "COMPLETED", "resolution Saga did not complete")

    listing = aftersales.get("listing", {})
    fulfillment = aftersales.get("forward_fulfillment", {})
    return {
        "schema_version": "cloudmold.canonical-evidence-gate/v1",
        "status": "SUCCEEDED",
        "run_id": run_id,
        "source_commit": parent.get("source_commit"),
        "ledgers": {name: str(path) for name, path in {"parent": parent_path, **child_paths}.items()},
        "product_view": {
            "style_code": catalog.get("style_code"),
            "canonical_spu_id": catalog.get("spu_id"),
            "canonical_sku_id": case.get("canonicalSkuId"),
            "catalog_status": catalog.get("catalog_status"),
            "sku_count": catalog.get("sku_count"),
            "color_count": catalog.get("color_count"),
            "size_count": catalog.get("size_count"),
            "compatibility_projection_count": projection.get("projection_count"),
            "merchant_id": master.get("merchant_id"),
            "shop_id": master.get("shop_id"),
            "warehouse_id": master.get("warehouse_id"),
            "listing_status": listing.get("currentStatus"),
            "listing_version": listing.get("aggregateVersion"),
            "sale_quantity": fulfillment.get("items", [{}])[0].get("quantity"),
            "fulfillment_status": fulfillment.get("currentStatus"),
            "fulfillment_version": fulfillment.get("aggregateVersion"),
            "return_quantity": case.get("quantity"),
            "return_fulfillment_status": case.get("returnFulfillmentStatus"),
            "refund_status": case.get("refundStatus"),
            "refund_amount_minor": case.get("approvedAmountMinor"),
            "aftersales_status": case.get("caseStatus"),
            "resolution_saga_status": case.get("resolutionSagaStatus"),
            "resolution_saga_version": case.get("resolutionSagaVersion"),
            "client_command_count": aftersales.get("client_command_count"),
            "all_replay_duplicate": aftersales.get("all_replay_duplicate"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", type=Path, default=Path("~/.cloudmold/runs"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.run_root.expanduser().resolve(), args.run_id)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
