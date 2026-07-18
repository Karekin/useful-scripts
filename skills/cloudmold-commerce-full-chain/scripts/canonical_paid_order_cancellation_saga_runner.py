#!/usr/bin/env python3
"""Deterministic paid-but-unshipped durable cancellation Saga runner."""

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
    FULFILLMENT_ROUTE,
    INVENTORY_ROUTE,
    LISTING_ROUTE,
    ORDER_ROUTE,
    PAYMENT_ROUTE,
    PAYABLE_MINOR,
    RUN_ID_PATTERN,
    RunRecorder,
    authenticated_client,
    execute_listing,
    fulfillment_create_payload,
    inventory_payload,
    load_catalog_identity,
    metadata,
    payment_payload,
    place_from_listing_payload,
    require,
    stable_result,
    transition_payload,
    validate_inventory,
)


SAGA_COMMAND_ROUTE = "/admin-api/cloudmold/order-cancellation-saga/command"
SAGA_QUERY_ROUTE = "/admin-api/cloudmold/order-cancellation-saga/get"
POST_ROUTES = (LISTING_ROUTE, INVENTORY_ROUTE, ORDER_ROUTE, PAYMENT_ROUTE,
               FULFILLMENT_ROUTE, SAGA_COMMAND_ROUTE)
GET_ROUTES = (SAGA_QUERY_ROUTE,)
CANCELLATION_MODE = "PAID_UNSHIPPED"
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
        ("payment", "CAPTURE", "CAPTURED/v1"),
        ("order", "CONFIRM_PAYMENT", "PAYMENT_CONFIRMED/v3"),
        ("fulfillment", "CREATE", "CREATED/v1 without shipment"),
        ("cancellation_saga", "START PAID_UNSHIPPED", "REQUESTED/v1"),
        ("cancellation_saga", "POLL", "COMPLETED/v9"),
        ("proof", "REPLAY_FULFILLMENT_REQUEST", "CANCELLATION_PENDING/v2 duplicate"),
        ("proof", "REPLAY_FULFILLMENT_FINALIZE", "CANCELLED/v3 duplicate"),
        ("proof", "REPLAY_PAYMENT_REFUND", "REFUNDED/v2 duplicate"),
        ("proof", "REPLAY_INVENTORY_RELEASE", "10/0/10/v3 duplicate"),
        ("proof", "REPLAY_ORDER_FINALIZE", "CANCELLED/v5 duplicate"),
        ("proof", "REPLAY_ALL_CLIENT_COMMANDS", "all 14 duplicate"),
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
        "cancellationMode": CANCELLATION_MODE,
        "reason": "paid-but-unshipped cancellation requested by ERP Operator",
    }


def fulfillment_request_replay_payload(start: dict, saga_id: str, fulfillment_id: str,
                                       order_id: str, run_id: str) -> dict:
    return {
        "operation": "REQUEST_CANCELLATION",
        "idempotencyKey": f"cancel-saga:{saga_id}:fulfillment:{fulfillment_id}:request",
        "runId": run_id,
        "fulfillmentId": fulfillment_id,
        "expectedVersion": 1,
        "orderId": order_id,
        "cancellationSagaId": saga_id,
        "cancellationStepOrdinal": 1,
        "reason": start["reason"],
        "correlationId": start["correlationId"],
        "occurredAt": start["occurredAt"],
    }


def fulfillment_finalize_replay_payload(start: dict, saga_id: str, fulfillment_id: str,
                                        order_id: str, run_id: str) -> dict:
    return {
        "operation": "FINALIZE_CANCELLATION",
        "idempotencyKey": f"cancel-saga:{saga_id}:fulfillment:{fulfillment_id}:finalize",
        "runId": run_id,
        "fulfillmentId": fulfillment_id,
        "expectedVersion": 2,
        "orderId": order_id,
        "cancellationSagaId": saga_id,
        "cancellationStepOrdinal": 1,
        "reason": start["reason"],
        "correlationId": start["correlationId"],
        "occurredAt": add_seconds(start["occurredAt"], 1),
    }


def payment_refund_replay_payload(start: dict, saga_id: str, payment_id: str,
                                  order_id: str, run_id: str) -> dict:
    return {
        "operation": "REFUND",
        "idempotencyKey": f"cancel-saga:{saga_id}:payment:{payment_id}:refund",
        "runId": run_id,
        "paymentId": payment_id,
        "expectedVersion": 1,
        "orderId": order_id,
        "amountMinor": PAYABLE_MINOR,
        "currencyCode": "CNY",
        "providerCode": "INTERNAL_TEST",
        "providerTransactionId": f"cancel-saga:{saga_id}:refund:{payment_id}",
        "reason": start["reason"],
        "cancellationSagaId": saga_id,
        "cancellationStepOrdinal": 2,
        "correlationId": start["correlationId"],
        "occurredAt": add_seconds(start["occurredAt"], 2),
    }


def inventory_release_replay_payload(start: dict, saga_id: str, reservation_id: str,
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
        "cancellationSagaId": saga_id,
        "cancellationStepOrdinal": 3,
        "correlationId": start["correlationId"],
        "occurredAt": add_seconds(start["occurredAt"], 3),
    }


def order_finalize_replay_payload(start: dict, saga_id: str, order_id: str,
                                  payment_id: str, fulfillment_id: str,
                                  refund_id: str, run_id: str) -> dict:
    return {
        "operation": "FINALIZE_CANCELLATION",
        "idempotencyKey": f"cancel-saga:{saga_id}:order-finalize",
        "runId": run_id,
        "orderId": order_id,
        "expectedVersion": 4,
        "cancellationSagaId": saga_id,
        "cancellationMode": CANCELLATION_MODE,
        "cancellationStepOrdinal": 4,
        "paymentId": payment_id,
        "fulfillmentId": fulfillment_id,
        "refundId": refund_id,
        "reason": start["reason"],
        "correlationId": start["correlationId"],
        "occurredAt": add_seconds(start["occurredAt"], 5),
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
                "paid cancellation Saga requires manual review: "
                f"code={saga.get('lastErrorCode')} status={saga.get('status')}")
        if monotonic() >= deadline:
            raise ScenarioError(
                "paid cancellation Saga polling timed out: "
                f"status={saga.get('status')} step={saga.get('activeStep')}")
        sleep(interval)


def validate_started_saga(saga: dict, order_id: str, payment_id: str, fulfillment_id: str) -> None:
    require(saga.get("status") == "REQUESTED" and saga.get("aggregateVersion") == 1
            and isinstance(saga.get("duplicate"), bool),
            f"Paid Saga START invariant failed: {saga}")
    require(saga.get("cancellationMode") == CANCELLATION_MODE
            and saga.get("orderId") == order_id and saga.get("paymentId") == payment_id
            and saga.get("fulfillmentId") == fulfillment_id,
            f"Paid Saga exact aggregate snapshot invariant failed: {saga}")
    require(saga.get("paymentStatus") == "CAPTURED"
            and saga.get("fulfillmentStatus") == "FENCED"
            and saga.get("expectedFulfillmentCount") == 1
            and saga.get("cancelledFulfillmentCount") == 0,
            f"Paid Saga initial financial/fulfillment fence invariant failed: {saga}")


def validate_completed_saga(saga: dict, order_id: str, payment_id: str,
                            fulfillment_id: str, reservation_id: str) -> None:
    require(saga.get("status") == "COMPLETED" and saga.get("activeStep") == "NONE",
            f"Paid Saga terminal state invariant failed: {saga}")
    require(saga.get("cancellationMode") == CANCELLATION_MODE
            and saga.get("orderId") == order_id and saga.get("paymentId") == payment_id
            and saga.get("fulfillmentId") == fulfillment_id,
            f"Paid Saga aggregate identity invariant failed: {saga}")
    require(saga.get("orderStatusAtRequest") == "PAYMENT_CONFIRMED"
            and saga.get("orderVersionAtRequest") == 3,
            f"Paid Saga Order source invariant failed: {saga}")
    require(saga.get("paymentStatus") == "REFUNDED",
            f"Paid Saga Payment terminal invariant failed: {saga}")
    require(saga.get("paymentRefundTransactionId") is not None,
            f"Paid Saga refund transaction invariant failed: {saga}")
    require(saga.get("fulfillmentStatus") == "CANCELLED"
            and saga.get("expectedFulfillmentCount") == 1
            and saga.get("cancelledFulfillmentCount") == 1,
            f"Paid Saga Fulfillment terminal invariant failed: {saga}")
    require(saga.get("expectedReservationCount") == 1
            and saga.get("releasedReservationCount") == 1,
            f"Paid Saga reservation count invariant failed: {saga}")
    items = saga.get("items") or []
    require(len(items) == 1 and items[0].get("reservationId") == reservation_id
            and items[0].get("status") == "RELEASED",
            f"Paid Saga exact reservation invariant failed: {items}")
    require(saga.get("aggregateVersion") == 9 and saga.get("completedAt") is not None
            and saga.get("lastErrorCode") is None,
            f"Paid Saga completion/version invariant failed: {saga}")


def write_ledger(args: argparse.Namespace, ledger: dict, suffix: str = "ledger.json") -> Path:
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "paid-order-cancellation-saga" / args.run_id / suffix
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"{output.stem}-{stamp}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def proof_internal_commands(recorder: RunRecorder, start: dict, saga: dict,
                            payment_id: str, fulfillment_id: str, reservation_id: str,
                            sku_id: str, warehouse_id: str, owner_id: str,
                            order_id: str, order_item_id: str, order_no: str) -> dict:
    saga_id, run_id = saga["sagaId"], saga["runId"]
    refund_id = str(saga["paymentRefundTransactionId"])
    payloads = {
        "fulfillment_request": (FULFILLMENT_ROUTE, fulfillment_request_replay_payload(
            start, saga_id, fulfillment_id, order_id, run_id)),
        "fulfillment_finalize": (FULFILLMENT_ROUTE, fulfillment_finalize_replay_payload(
            start, saga_id, fulfillment_id, order_id, run_id)),
        "payment_refund": (PAYMENT_ROUTE, payment_refund_replay_payload(
            start, saga_id, payment_id, order_id, run_id)),
        "inventory_release": (INVENTORY_ROUTE, inventory_release_replay_payload(
            start, saga_id, reservation_id, sku_id, warehouse_id, owner_id,
            order_id, order_item_id, order_no)),
        "order_finalize": (ORDER_ROUTE, order_finalize_replay_payload(
            start, saga_id, order_id, payment_id, fulfillment_id, refund_id, run_id)),
    }
    results = {}
    for name, (route, payload) in payloads.items():
        result = recorder.client.request("POST", route, payload)
        require(result.get("duplicate") is True, f"{name} proof was not an immutable duplicate")
        results[name] = {"request_hash": request_hash(payload), "result": result}

    require(results["fulfillment_request"]["result"].get("currentStatus") == "CANCELLATION_PENDING"
            and results["fulfillment_request"]["result"].get("aggregateVersion") == 2,
            f"Fulfillment request proof failed: {results['fulfillment_request']}")
    fulfillment = results["fulfillment_finalize"]["result"]
    require(fulfillment.get("currentStatus") == "CANCELLED"
            and fulfillment.get("aggregateVersion") == 3 and fulfillment.get("shipmentId") is None,
            f"Fulfillment finalize proof failed: {fulfillment}")
    payment = results["payment_refund"]["result"]
    require(payment.get("currentStatus") == "REFUNDED" and payment.get("aggregateVersion") == 2
            and payment.get("capturedAmountMinor") == PAYABLE_MINOR
            and payment.get("refundedAmountMinor") == PAYABLE_MINOR,
            f"Payment refund proof failed: {payment}")
    inventory = results["inventory_release"]["result"]
    validate_inventory(inventory, ("10.000000", "0.000000", "10.000000", 3),
                       "Paid Saga RELEASE proof")
    order = results["order_finalize"]["result"]
    require(order.get("currentStatus") == "CANCELLED" and order.get("aggregateVersion") == 5
            and order.get("cancellationSagaId") == saga_id and order.get("paymentId") == payment_id
            and order.get("fulfillmentId") == fulfillment_id and order.get("refundId") == refund_id,
            f"Order finalize proof failed: {order}")
    require(order.get("shipmentId") is None,
            f"Cancelled paid Order unexpectedly owns a Shipment: {order}")
    return results


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

    payment = recorder.call("payment", PAYMENT_ROUTE, payment_payload(
        args.run_id, index, "CAPTURE", orderId=order_id, amountMinor=PAYABLE_MINOR,
        currencyCode="CNY", providerCode="INTERNAL_TEST",
        providerTransactionId=f"capture-{args.run_id}", reason="deterministic paid cancellation capture"))
    require(payment.get("currentStatus") == "CAPTURED" and payment.get("aggregateVersion") == 1
            and payment.get("capturedAmountMinor") == PAYABLE_MINOR
            and payment.get("refundedAmountMinor") == 0 and payment.get("testMode") is True,
            f"CAPTURE invariant failed: {payment}")
    payment_id = payment["paymentId"]
    index += 1

    order = recorder.call("order", ORDER_ROUTE, transition_payload(
        args.run_id, index, "order", "CONFIRM_PAYMENT", "orderId", order_id, 2,
        paymentId=payment_id, reason="exact test payment captured"))
    require(order.get("currentStatus") == "PAYMENT_CONFIRMED" and order.get("aggregateVersion") == 3,
            f"CONFIRM_PAYMENT invariant failed: {order}")
    index += 1

    fulfillment = recorder.call("fulfillment", FULFILLMENT_ROUTE, fulfillment_create_payload(
        args.run_id, index, order_id, order_item_id, sku_id, reservation_id, warehouse_id))
    require(fulfillment.get("currentStatus") == "CREATED"
            and fulfillment.get("aggregateVersion") == 1 and fulfillment.get("shipmentId") is None,
            f"Fulfillment CREATE invariant failed: {fulfillment}")
    fulfillment_id = fulfillment["fulfillmentId"]
    index += 1

    start_payload = saga_start_payload(args.run_id, index, order_id)
    saga_initial = recorder.call("cancellation_saga", SAGA_COMMAND_ROUTE, start_payload)
    validate_started_saga(saga_initial, order_id, payment_id, fulfillment_id)
    saga_id = saga_initial["sagaId"]

    if args.completion_mode == "start-only":
        current = recorder.client.request("GET", f"{SAGA_QUERY_ROUTE}?sagaId={saga_id}")
        require(current.get("status") == "REQUESTED" and current.get("aggregateVersion") == 1,
                "start-only requires the normal Saga worker to be disabled before START")
        current["duplicate"] = saga_initial["duplicate"]
        validate_started_saga(current, order_id, payment_id, fulfillment_id)
        replay = recorder.replay_all()
        partial = {
            "scenario": "canonical-paid-order-cancellation-saga-v1",
            "status": "paused_for_recovery",
            "run_id": args.run_id,
            "environment": args.environment,
            "tenant": args.tenant,
            "catalog_ledger": catalog_ledger,
            "calls": recorder.redacted_calls(),
            "replay": replay,
            "saga": current,
            "saga_start_was_recovery_replay": saga_initial["duplicate"],
            "restart_instruction": "restart with cloudmold.order-cancellation-saga.enabled=true and rerun same run_id",
        }
        output = write_ledger(args, partial, "recovery-start-ledger.json")
        return {"status": "paused_for_recovery", "run_id": args.run_id, "ledger": str(output),
                "saga": current, "saga_start_was_recovery_replay": saga_initial["duplicate"],
                "all_replay_duplicate": True}

    saga, observations = poll_saga(recorder.client, saga_id, args.saga_timeout, args.poll_interval)
    validate_completed_saga(saga, order_id, payment_id, fulfillment_id, reservation_id)
    proofs = proof_internal_commands(recorder, start_payload, saga, payment_id, fulfillment_id,
                                     reservation_id, sku_id, warehouse_id, args.owner_id,
                                     order_id, order_item_id, order_no)
    replay = recorder.replay_all()
    require(len(replay) == 14 and replay[-1]["domain"] == "cancellation_saga"
            and replay[-1]["result"].get("duplicate") is True
            and stable_result(replay[-1]["result"]) == stable_result(saga_initial),
            "Paid Saga START replay did not preserve its immutable initial result")

    final = {
        "listing": listing,
        "saga": saga,
        "order": proofs["order_finalize"]["result"],
        "payment": proofs["payment_refund"]["result"],
        "fulfillment": proofs["fulfillment_finalize"]["result"],
        "inventory": proofs["inventory_release"]["result"],
        "shipment_count": 0,
        "all_replay_duplicate": True,
    }
    evidence_hook = {
        "run_id": args.run_id,
        "domains": ["listing", "inventory", "order", "payment", "fulfillment",
                    "order_cancellation_saga"],
        "aggregate_ids": {"listing_id": listing_id, "order_id": order_id,
                          "payment_id": payment_id, "fulfillment_id": fulfillment_id,
                          "saga_id": saga_id, "reservation_id": reservation_id},
        "expected_terminal": {"order": "CANCELLED/v5", "payment": "REFUNDED/v2",
                              "fulfillment": "CANCELLED/v3", "inventory": "10/0/10/v3",
                              "reservation": "RELEASED", "cancellation_saga": "COMPLETED/v9"},
        "expected_client_commands": 14,
        "expected_internal_proofs": 5,
        "expected_shipment_count": 0,
        "all_replay_duplicate": True,
        "saga_start_was_recovery_replay": saga_initial["duplicate"],
    }
    ledger = {
        "scenario": "canonical-paid-order-cancellation-saga-v1",
        "status": "succeeded",
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "canonical_sku_id": sku_id,
        "canonical_spu_id": spu_id,
        "catalog_ledger": catalog_ledger,
        "calls": recorder.redacted_calls(),
        "saga_observations": observations,
        "saga_start_was_recovery_replay": saga_initial["duplicate"],
        "proof_replays": proofs,
        "replay": replay,
        "lakehouse_evidence_hook": evidence_hook,
        "final": final,
    }
    output = write_ledger(args, ledger)
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output),
            "canonical_sku_id": sku_id, "canonical_spu_id": spu_id,
            "lakehouse_evidence_hook": evidence_hook,
            "saga_start_was_recovery_replay": saga_initial["duplicate"], **final}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--completion-mode", choices=("wait", "start-only"), default="wait")
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
    parser.add_argument("--saga-timeout", type=float, default=120)
    parser.add_argument("--poll-interval", type=float, default=1)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)),
                "run_id must be 6-32 characters using letters, digits, dot, underscore, or hyphen")
        require(args.environment in {"local", "demo", "test"},
                "the paid cancellation Saga runner is restricted to local, demo, or test")
        require(args.completion_mode != "start-only" or args.environment in {"local", "test"},
                "start-only recovery drill is restricted to local or test")
        require(args.saga_timeout > 0 and args.poll_interval > 0,
                "Saga timeout and poll interval must be positive")
        sku_id, spu_id, catalog_ledger = load_catalog_identity(args)
        if args.mode == "plan":
            result = {"scenario": "canonical-paid-order-cancellation-saga-v1",
                      "run_id": args.run_id, "canonical_sku_id": sku_id,
                      "canonical_spu_id": spu_id, "catalog_ledger": catalog_ledger,
                      "steps": scenario_plan(), "client_command_replay": "all 14 commands",
                      "internal_duplicate_proofs": 5,
                      "cancellation_mode": CANCELLATION_MODE,
                      "worker_switch": "cloudmold.order-cancellation-saga.enabled",
                      "completion_mode": args.completion_mode,
                      "fault_injection_request_fields": [],
                      "lakehouse_reconcile_command": "reconcile-canonical-paid-cancellation-saga",
                      "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, None, args.timeout).openapi().get("paths", {})
            missing = [route for route in POST_ROUTES if route not in paths or "post" not in paths[route]]
            missing += [route for route in GET_ROUTES if route not in paths or "get" not in paths[route]]
            require(not missing, f"live OpenAPI is missing routes: {missing}")
            result = {"status": "ready", "run_id": args.run_id,
                      "post_routes": list(POST_ROUTES), "get_routes": list(GET_ROUTES),
                      "cancellation_mode": CANCELLATION_MODE,
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
