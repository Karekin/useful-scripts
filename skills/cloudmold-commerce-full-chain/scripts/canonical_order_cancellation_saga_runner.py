#!/usr/bin/env python3
"""Deterministic durable release-before-cancel Saga runner for a Listing order."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable

from canonical_inventory_runner import Client, ScenarioError, request_hash
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
    metadata,
    place_from_listing_payload,
    require,
    stable_result,
    transition_payload,
    validate_inventory,
)


SAGA_COMMAND_ROUTE = "/admin-api/cloudmold/order-cancellation-saga/command"
SAGA_QUERY_ROUTE = "/admin-api/cloudmold/order-cancellation-saga/get"
POST_ROUTES = (LISTING_ROUTE, INVENTORY_ROUTE, ORDER_ROUTE, SAGA_COMMAND_ROUTE)
GET_ROUTES = (SAGA_QUERY_ROUTE,)
TERMINAL_FAILURE_STATES = {"MANUAL_REVIEW"}
QUANTITY = "2.000000"


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
        ("cancellation_saga", "START", "REQUESTED/v1"),
        ("cancellation_saga", "POLL", "COMPLETED"),
        ("proof", "REPLAY_INTERNAL_RELEASE", "10/0/10/v3 duplicate"),
        ("proof", "REPLAY_INTERNAL_FINALIZE", "CANCELLED/v4 duplicate"),
        ("proof", "REPLAY_ALL_CLIENT_COMMANDS", "all 11 duplicate"),
    )
    return [{"step": index, "domain": domain, "operation": operation, "expected": expected}
            for index, (domain, operation, expected) in enumerate(operations, 1)]


def add_seconds(value: str, seconds: int) -> str:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed + dt.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def saga_start_payload(run_id: str, index: int, order_id: str) -> dict:
    return {
        "operation": "START",
        **metadata(run_id, index, "cancellation-saga", "START"),
        "runId": run_id,
        "orderId": order_id,
        "reason": "durable pre-payment cancellation requested by ERP Operator",
    }


def internal_release_replay_payload(start: dict, saga_id: str, reservation_id: str,
                                    sku_id: str, warehouse_id: str, owner_id: str,
                                    order_id: str, order_item_id: str, order_no: str) -> dict:
    return {
        "operation": "RELEASE",
        "idempotencyKey": f"cancel-saga:{saga_id}:release:{reservation_id}",
        "ownerId": owner_id,
        "canonicalSkuId": sku_id,
        "warehouseId": warehouse_id,
        "stockStatus": "SELLABLE",
        "qualityStatus": "QUALIFIED",
        "uomCode": "PCS",
        "quantity": QUANTITY,
        "reservationId": reservation_id,
        "businessType": "TRADE_ORDER",
        "businessId": order_id,
        "businessItemId": order_item_id,
        "businessNo": order_no,
        "correlationId": start["correlationId"],
        "occurredAt": add_seconds(start["occurredAt"], 1),
    }


def internal_finalize_replay_payload(start: dict, saga: dict) -> dict:
    item_count = len(saga.get("items") or [])
    return {
        "operation": "FINALIZE_CANCELLATION",
        "idempotencyKey": f"cancel-saga:{saga['sagaId']}:order-finalize",
        "runId": saga["runId"],
        "orderId": saga["orderId"],
        "expectedVersion": saga["orderVersionAtRequest"] + 1,
        "cancellationSagaId": saga["sagaId"],
        "reason": saga["reason"],
        "correlationId": start["correlationId"],
        "occurredAt": add_seconds(start["occurredAt"], item_count + 2),
    }


def poll_saga(client: Client, saga_id: str, timeout: float, interval: float,
              sleep: Callable[[float], None] = time.sleep,
              monotonic: Callable[[], float] = time.monotonic) -> tuple[dict, list[dict]]:
    deadline = monotonic() + timeout
    observations: list[dict] = []
    while True:
        saga = client.request("GET", f"{SAGA_QUERY_ROUTE}?sagaId={saga_id}")
        observations.append({
            "status": saga.get("status"),
            "active_step": saga.get("activeStep"),
            "attempt_count": saga.get("attemptCount"),
            "aggregate_version": saga.get("aggregateVersion"),
            "released_reservation_count": saga.get("releasedReservationCount"),
            "last_error_code": saga.get("lastErrorCode"),
        })
        if saga.get("status") == "COMPLETED":
            return saga, observations
        if saga.get("status") in TERMINAL_FAILURE_STATES:
            raise ScenarioError(
                "durable cancellation Saga requires manual review: "
                f"code={saga.get('lastErrorCode')} status={saga.get('status')}")
        if monotonic() >= deadline:
            raise ScenarioError(
                "durable cancellation Saga polling timed out: "
                f"status={saga.get('status')} step={saga.get('activeStep')}")
        sleep(interval)


def validate_completed_saga(saga: dict, order_id: str, reservation_id: str) -> None:
    require(saga.get("status") == "COMPLETED" and saga.get("activeStep") == "NONE",
            f"Saga terminal state invariant failed: {saga}")
    require(saga.get("orderId") == order_id,
            f"Saga Order identity invariant failed: {saga}")
    require(saga.get("orderStatusAtRequest") == "INVENTORY_RESERVED"
            and saga.get("orderVersionAtRequest") == 2,
            f"Saga cancellation fence source invariant failed: {saga}")
    require(saga.get("expectedReservationCount") == 1
            and saga.get("releasedReservationCount") == 1,
            f"Saga reservation count invariant failed: {saga}")
    items = saga.get("items") or []
    require(len(items) == 1 and items[0].get("reservationId") == reservation_id
            and items[0].get("status") == "RELEASED",
            f"Saga exact reservation terminal invariant failed: {items}")
    require(saga.get("completedAt") is not None and saga.get("lastErrorCode") is None,
            f"Saga completion/error invariant failed: {saga}")


def validate_started_saga(saga: dict) -> None:
    """Accept both a fresh START and the immutable START replay used for restart recovery."""
    require(saga.get("status") == "REQUESTED"
            and saga.get("aggregateVersion") == 1
            and isinstance(saga.get("duplicate"), bool),
            f"Saga START invariant failed: {saga}")


def write_ledger(args: argparse.Namespace, ledger: dict) -> Path:
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "order-cancellation-saga" / args.run_id / "ledger.json"
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
        args.run_id, index, "RESERVE", sku_id, warehouse_id, args.owner_id, QUANTITY,
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

    start_payload = saga_start_payload(args.run_id, index, order_id)
    saga_initial = recorder.call("cancellation_saga", SAGA_COMMAND_ROUTE, start_payload)
    validate_started_saga(saga_initial)
    saga_id = saga_initial["sagaId"]

    saga, observations = poll_saga(recorder.client, saga_id, args.saga_timeout, args.poll_interval)
    validate_completed_saga(saga, order_id, reservation_id)

    release_payload = internal_release_replay_payload(
        start_payload, saga_id, reservation_id, sku_id, warehouse_id, args.owner_id,
        order_id, order_item_id, order_no)
    released_inventory = recorder.client.request("POST", INVENTORY_ROUTE, release_payload)
    require(released_inventory.get("duplicate") is True,
            "internal Saga Inventory RELEASE proof was not an immutable duplicate")
    validate_inventory(released_inventory, ("10.000000", "0.000000", "10.000000", 3),
                       "Saga RELEASE proof")

    finalize_payload = internal_finalize_replay_payload(start_payload, saga)
    cancelled_order = recorder.client.request("POST", ORDER_ROUTE, finalize_payload)
    require(cancelled_order.get("duplicate") is True
            and cancelled_order.get("currentStatus") == "CANCELLED"
            and cancelled_order.get("aggregateVersion") == 4
            and cancelled_order.get("cancellationSagaId") == saga_id,
            f"internal Saga Order FINALIZE proof failed: {cancelled_order}")
    require(cancelled_order.get("paymentId") is None
            and cancelled_order.get("fulfillmentId") is None
            and cancelled_order.get("shipmentId") is None,
            f"cancelled order unexpectedly owns money or fulfillment: {cancelled_order}")
    require(not any(call["domain"] in {"payment", "fulfillment"} for call in recorder.calls),
            "durable cancellation scenario must not issue Payment or Fulfillment commands")

    replay = recorder.replay_all()
    require(len(replay) == 11 and replay[-1]["domain"] == "cancellation_saga"
            and replay[-1]["result"].get("duplicate") is True
            and stable_result(replay[-1]["result"]) == stable_result(saga_initial),
            "Saga START replay did not preserve its immutable initial result")
    absence_proof = {
        "scope": "this unique run_id, canonical Order, and durable cancellation Saga",
        "payment_command_count": 0,
        "fulfillment_command_count": 0,
        "order_payment_id": None,
        "order_fulfillment_id": None,
        "order_shipment_id": None,
        "proof_basis": ["redacted executed-domain ledger", "duplicate final Order proof"],
    }
    evidence_hook = {
        "run_id": args.run_id,
        "domains": ["listing", "inventory", "order", "order_cancellation_saga"],
        "aggregate_ids": {"listing_id": listing_id, "order_id": order_id,
                          "saga_id": saga_id, "reservation_id": reservation_id},
        "expected_terminal": {"listing": "PUBLISHED/v6", "order": "CANCELLED/v4",
                              "inventory": "10/0/10/v3", "reservation": "RELEASED",
                              "cancellation_saga": "COMPLETED"},
        "expected_absence": {"payment": True, "fulfillment": True},
        "expected_client_commands": 11,
        "all_client_command_replays_duplicate": True,
        "saga_start_was_recovery_replay": saga_initial["duplicate"],
    }
    proof_replays = {
        "inventory_release": {"request_hash": request_hash(release_payload),
                              "result": released_inventory},
        "order_finalize": {"request_hash": request_hash(finalize_payload),
                           "result": cancelled_order},
    }
    ledger = {
        "scenario": "canonical-order-cancellation-saga-v1",
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "canonical_sku_id": sku_id,
        "canonical_spu_id": spu_id,
        "catalog_ledger": catalog_ledger,
        "calls": recorder.redacted_calls(),
        "saga_observations": observations,
        "saga_start_was_recovery_replay": saga_initial["duplicate"],
        "proof_replays": proof_replays,
        "replay": replay,
        "absence_proof": absence_proof,
        "lakehouse_evidence_hook": evidence_hook,
        "final": {"listing": listing, "saga": saga, "order": cancelled_order,
                  "inventory": released_inventory, "absence_proof": absence_proof,
                  "all_replay_duplicate": True},
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
    parser.add_argument("--saga-timeout", type=float, default=90)
    parser.add_argument("--poll-interval", type=float, default=1)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)),
                "run_id must be 6-32 characters using letters, digits, dot, underscore, or hyphen")
        require(args.environment in {"local", "demo", "test"},
                "the durable cancellation Saga runner is restricted to local, demo, or test")
        require(args.saga_timeout > 0 and args.poll_interval > 0,
                "Saga timeout and poll interval must be positive")
        sku_id, spu_id, catalog_ledger = load_catalog_identity(args)
        if args.mode == "plan":
            result = {"scenario": "canonical-order-cancellation-saga-v1",
                      "run_id": args.run_id, "canonical_sku_id": sku_id,
                      "canonical_spu_id": spu_id, "catalog_ledger": catalog_ledger,
                      "steps": scenario_plan(), "client_command_replay": "all 11 commands",
                      "durability": "START then poll; Saga owns RELEASE and FINALIZE_CANCELLATION",
                      "fault_injection_request_fields": [],
                      "expected_absence": ["payment", "fulfillment"],
                      "lakehouse_reconcile_command": "reconcile-canonical-cancellation-saga",
                      "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, None, args.timeout).openapi().get("paths", {})
            missing = [route for route in POST_ROUTES if route not in paths or "post" not in paths[route]]
            missing += [route for route in GET_ROUTES if route not in paths or "get" not in paths[route]]
            require(not missing, f"live OpenAPI is missing routes: {missing}")
            result = {"status": "ready", "run_id": args.run_id,
                      "post_routes": list(POST_ROUTES), "get_routes": list(GET_ROUTES),
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
