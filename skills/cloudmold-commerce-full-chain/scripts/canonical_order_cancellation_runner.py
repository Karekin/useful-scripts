#!/usr/bin/env python3
"""Deterministic release-before-cancel compensation runner for a Listing order."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys

from canonical_inventory_runner import Client, ScenarioError
from canonical_listing_fulfillment_runner import (
    INVENTORY_ROUTE,
    LISTING_ROUTE,
    ORDER_ROUTE,
    RUN_ID_PATTERN,
    RunRecorder,
    authenticated_client,
    execute_listing,
    inventory_payload,
    load_catalog_identity,
    place_from_listing_payload,
    require,
    transition_payload,
    validate_inventory,
)


ROUTES = (LISTING_ROUTE, INVENTORY_ROUTE, ORDER_ROUTE)


def scenario_plan() -> list[dict]:
    operations = (
        ("listing", "CREATE_DRAFT", "DRAFT/v1"),
        ("listing", "SUBMIT", "SUBMITTED/v2"),
        ("listing", "PASS_COMPLETION", "COMPLETION_PASSED/v3"),
        ("listing", "APPROVE_BUSINESS", "BUSINESS_APPROVED/v4"),
        ("listing", "APPROVE_RISK", "RISK_APPROVED/v5"),
        ("listing", "PUBLISH", "PUBLISHED/v6"),
        ("inventory", "RECEIVE", "10/0/10/v1"),
        ("order", "PLACE_FROM_LISTING", "PLACED/v1"),
        ("inventory", "RESERVE", "10/2/8/v2"),
        ("order", "CONFIRM_INVENTORY", "INVENTORY_RESERVED/v2"),
        ("inventory", "RELEASE", "10/0/10/v3"),
        ("order", "CANCEL", "CANCELLED/v3"),
    )
    return [{"step": index, "domain": domain, "operation": operation, "expected": expected}
            for index, (domain, operation, expected) in enumerate(operations, 1)]


def write_ledger(args: argparse.Namespace, ledger: dict) -> Path:
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "commerce-cancellation" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def execute(args: argparse.Namespace) -> dict:
    sku_id, spu_id, catalog_ledger = load_catalog_identity(args)
    warehouse_id = args.warehouse_id or f"scenario:{args.run_id}"
    recorder = RunRecorder(authenticated_client(args))
    listing, offer_id, index = execute_listing(recorder, args, sku_id, spu_id)
    listing_id = listing["listingId"]

    receive = recorder.call("inventory", INVENTORY_ROUTE, inventory_payload(
        args.run_id, index, "RECEIVE", sku_id, warehouse_id, args.owner_id, "10.000000",
        "TEST_FIXTURE", args.run_id, "fixture-line", f"FIXTURE-{args.run_id}"))
    validate_inventory(receive, ("10.000000", "0.000000", "10.000000", 1), "RECEIVE")
    index += 1

    order = recorder.call("order", ORDER_ROUTE,
                          place_from_listing_payload(args.run_id, index, sku_id, listing_id, offer_id))
    require(order.get("currentStatus") == "PLACED" and order.get("aggregateVersion") == 1,
            f"PLACE_FROM_LISTING invariant failed: {order}")
    require(len(order.get("items") or []) == 1, f"Order item invariant failed: {order}")
    order_id, order_no = order["orderId"], order["orderNo"]
    order_item_id = order["items"][0]["orderItemId"]
    index += 1

    reserve = recorder.call("inventory", INVENTORY_ROUTE, inventory_payload(
        args.run_id, index, "RESERVE", sku_id, warehouse_id, args.owner_id, "2.000000",
        "TRADE_ORDER", order_id, order_item_id, order_no))
    validate_inventory(reserve, ("10.000000", "2.000000", "8.000000", 2), "RESERVE")
    reservation_id = reserve["reservationId"]
    index += 1

    order = recorder.call("order", ORDER_ROUTE, transition_payload(
        args.run_id, index, "order", "CONFIRM_INVENTORY", "orderId", order_id, 1,
        reservationReferences=[{"orderItemId": order_item_id, "reservationId": reservation_id}],
        reason="all Listing order lines reserved"))
    require(order.get("currentStatus") == "INVENTORY_RESERVED" and order.get("aggregateVersion") == 2,
            f"CONFIRM_INVENTORY invariant failed: {order}")
    index += 1

    released_inventory = recorder.call("inventory", INVENTORY_ROUTE, inventory_payload(
        args.run_id, index, "RELEASE", sku_id, warehouse_id, args.owner_id, "2.000000",
        "TRADE_ORDER", order_id, order_item_id, order_no, reservation_id))
    validate_inventory(released_inventory, ("10.000000", "0.000000", "10.000000", 3), "RELEASE")
    index += 1

    order = recorder.call("order", ORDER_ROUTE, transition_payload(
        args.run_id, index, "order", "CANCEL", "orderId", order_id, 2,
        reason="released all reservations before cancellation"))
    require(order.get("currentStatus") == "CANCELLED" and order.get("aggregateVersion") == 3,
            f"CANCEL invariant failed: {order}")
    require(order.get("paymentId") is None and order.get("fulfillmentId") is None
            and order.get("shipmentId") is None,
            f"cancelled order unexpectedly references payment or fulfillment: {order}")
    require(not any(call["domain"] in {"payment", "fulfillment"} for call in recorder.calls),
            "cancellation compensation must not create payment or fulfillment")

    replay = recorder.replay_all()
    absence_proof = {
        "scope": "this unique run_id and canonical order",
        "payment_command_count": 0,
        "fulfillment_command_count": 0,
        "order_payment_id": None,
        "order_fulfillment_id": None,
        "order_shipment_id": None,
        "proof_basis": ["executed-domain ledger", "terminal canonical Order result"],
    }
    evidence_hook = {
        "run_id": args.run_id,
        "domains": ["listing", "inventory", "order"],
        "aggregate_ids": {"listing_id": listing_id, "order_id": order_id,
                          "reservation_id": reservation_id},
        "expected_terminal": {"listing": "PUBLISHED/v6", "order": "CANCELLED/v3",
                              "inventory": "10/0/10/v3", "reservation": "RELEASED"},
        "expected_absence": {"payment": True, "fulfillment": True},
        "expected_business_commands": len(recorder.calls),
        "all_replay_duplicate": True,
    }
    ledger = {
        "scenario": "canonical-order-cancellation-compensation-v1",
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "canonical_sku_id": sku_id,
        "canonical_spu_id": spu_id,
        "catalog_ledger": catalog_ledger,
        "calls": recorder.redacted_calls(),
        "replay": replay,
        "absence_proof": absence_proof,
        "lakehouse_evidence_hook": evidence_hook,
        "final": {"listing": listing, "order": order, "inventory": released_inventory,
                  "absence_proof": absence_proof, "all_replay_duplicate": True},
    }
    output = write_ledger(args, ledger)
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output),
            "canonical_sku_id": sku_id, "canonical_spu_id": spu_id,
            "lakehouse_evidence_hook": evidence_hook, **ledger["final"]}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--sku-id")
    parser.add_argument("--spu-id")
    parser.add_argument("--catalog-ledger")
    parser.add_argument("--warehouse-id")
    parser.add_argument("--owner-id", default="internal-company")
    parser.add_argument("--timeout", type=int, default=20)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)),
                "run_id must be 6-32 characters using letters, digits, dot, underscore, or hyphen")
        require(args.environment in {"local", "demo", "test"},
                "the cancellation runner is restricted to local, demo, or test")
        sku_id, spu_id, catalog_ledger = load_catalog_identity(args)
        if args.mode == "plan":
            result = {"scenario": "canonical-order-cancellation-compensation-v1",
                      "run_id": args.run_id, "canonical_sku_id": sku_id,
                      "canonical_spu_id": spu_id, "catalog_ledger": catalog_ledger,
                      "steps": scenario_plan(), "replay": "all 12 commands",
                      "compensation_order": "RELEASE every reservation before CANCEL",
                      "expected_absence": ["payment", "fulfillment"],
                      "lakehouse_evidence_hook": "emitted after execute; no command name assumed",
                      "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, None, args.timeout).openapi().get("paths", {})
            missing = [route for route in ROUTES if route not in paths or "post" not in paths[route]]
            require(not missing, f"live OpenAPI is missing routes: {missing}")
            result = {"status": "ready", "run_id": args.run_id, "routes": list(ROUTES),
                      "canonical_sku_id": sku_id, "canonical_spu_id": spu_id,
                      "catalog_ledger": catalog_ledger, "side_effects": False}
        else:
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
