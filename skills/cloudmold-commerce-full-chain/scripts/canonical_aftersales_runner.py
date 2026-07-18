#!/usr/bin/env python3
"""Governed completed-order return/refund runner backed by AfterSale resolution Saga."""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode
import uuid

from aftersales_runner_core import (
    AtomicRunLedger,
    CheckpointRecorder,
    SCENARIO_NAME,
    endpoint_fingerprint,
    execute_forward_to_completed,
    execute_multi_line_forward_to_completed,
    load_endpoint_manifest,
    openapi_fingerprint,
    poll_aftersales,
    route,
    sha256_json,
    source_commit,
    verify_openapi,
)
from canonical_inventory_runner import Client, ScenarioError
from canonical_listing_fulfillment_runner import (
    PAYABLE_MINOR,
    RUN_ID_PATTERN,
    authenticated_client,
    event_time,
    load_catalog_identity,
    require,
)


SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = SKILL_DIR / "references" / "scenarios" / "aftersales-endpoints-v1.json"
DEFAULT_SCENARIO = SKILL_DIR / "references" / "scenarios" / f"{SCENARIO_NAME}.json"
EXPECTED_CLIENT_COMMANDS = 25
EXPECTED_AFTERSALES_COMMANDS = 6
PROMOTION_WRITES_BY_BENEFIT_MODE = {"entitlement-backed": 8, "stacked-entitlements": 14}
EXISTING_ORDER_EVIDENCE_SCENARIO = "canonical-aftersales-completed-order-evidence-v1"
MASTER_SCENARIO = "canonical-merchant-warehouse-first-slice-v1"


def deterministic_uuid(run_id: str, value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{run_id}:aftersales:{value}"))


def load_master_identity(path_value: str | None, tenant: int) -> dict:
    require(bool(path_value),
            "full flow requires --master-ledger from a SUCCEEDED canonical master run")
    path = Path(path_value).expanduser().resolve()
    require(path.is_file(), f"master ledger does not exist: {path}")
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read master ledger: {exc}") from exc
    require(ledger.get("scenario") == MASTER_SCENARIO,
            "master ledger has an unexpected scenario")
    require(ledger.get("status") == "SUCCEEDED", "master ledger is not SUCCEEDED")
    require(ledger.get("tenant") == tenant, "master ledger tenant does not match")
    final = ledger.get("final") or {}
    require(final.get("merchant_status") == "ACTIVE", "master Merchant is not ACTIVE")
    require(final.get("shop_status") == "ACTIVE", "master Shop is not ACTIVE")
    require(final.get("warehouse_status") == "ACTIVE", "master Warehouse is not ACTIVE")
    identity_fields = ("principal_id", "merchant_id", "shop_id", "warehouse_id")
    require(all(isinstance(final.get(field), str) and final.get(field) for field in identity_fields),
            "master ledger is missing canonical commerce identities")
    publish_steps = [step for step in ledger.get("steps", [])
                     if step.get("domain") == "listing" and step.get("operation") == "PUBLISH"]
    deferred = (final.get("listing_mode") == "defer"
                or final.get("listing_status") == "DEFERRED_TO_COMMERCE")
    if deferred:
        require(final.get("listing_id") is None and not publish_steps,
                "deferred master ledger must leave Listing ownership to Commerce")
        published = None
    else:
        require(len(publish_steps) == 1, "master ledger must contain one Listing PUBLISH proof")
        published = publish_steps[0].get("result") or {}
        offers = [offer for offer in published.get("offers") or [] if offer.get("enabled") is True]
        require(published.get("listingId") == final.get("listing_id")
                and published.get("currentStatus") == "PUBLISHED"
                and published.get("aggregateVersion") == 6,
                "master ledger Listing proof is not PUBLISHED/v6")
        require(len(offers) == 1 and isinstance(offers[0].get("listingOfferId"), str),
                "master ledger Listing proof has no single enabled offer")
    return {
        "path": str(path),
        **{field: final[field] for field in identity_fields},
        "listing_id": final.get("listing_id"),
        "published_listing": published,
    }


def aftersales_metadata(run_id: str, index: int, operation: str,
                        causation: str) -> dict:
    return {
        "idempotencyKey": f"{run_id}-{index:02d}-aftersale-{operation.lower()}",
        "runId": run_id,
        "occurredAt": event_time(run_id, index),
        "correlationId": deterministic_uuid(run_id, "correlation"),
        "causationId": deterministic_uuid(run_id, causation),
    }


def aftersales_payload(run_id: str, index: int, operation: str,
                       causation: str, **values: object) -> dict:
    return {
        "operation": operation,
        **aftersales_metadata(run_id, index, operation, causation),
        **values,
    }


def scenario_plan(manifest: dict, flow_mode: str = "full", benefit_mode: str = "none",
                  return_plan: str = "full") -> list[dict]:
    case_count = 1 if return_plan == "full" else 2
    forward_count = 22 if return_plan == "multi-line-full" else 19
    single_entitlement = (
        ("promotion", "CREATE_CAMPAIGN", "DRAFT/v1"),
        ("promotion", "ACTIVATE_CAMPAIGN", "ACTIVE/v2"),
        ("promotion", "CREATE_COUPON_TEMPLATE", "DRAFT/v1"),
        ("promotion", "ACTIVATE_COUPON_TEMPLATE", "ACTIVE/v2"),
        ("promotion", "ISSUE_COUPON_ENTITLEMENT", "ISSUED/v1"),
        ("promotion", "COLLECT_COUPON_ENTITLEMENT", "AVAILABLE/v2"),
        ("promotion", "RESERVE_COUPON_ENTITLEMENT", "RESERVED/v3"),
        ("promotion", "REDEEM_COUPON_ENTITLEMENT", "USED/v4"),
    )
    stacked_entitlements = (
        ("promotion", "CREATE_CAMPAIGN", "DRAFT/v1"),
        ("promotion", "ACTIVATE_CAMPAIGN", "ACTIVE/v2"),
        ("promotion", "CREATE_COUPON_TEMPLATE", "DRAFT/v1 platform"),
        ("promotion", "ACTIVATE_COUPON_TEMPLATE", "ACTIVE/v2 platform"),
        ("promotion", "ISSUE_COUPON_ENTITLEMENT", "ISSUED/v1 platform"),
        ("promotion", "COLLECT_COUPON_ENTITLEMENT", "AVAILABLE/v2 platform"),
        ("promotion", "RESERVE_COUPON_ENTITLEMENT", "RESERVED/v3 platform"),
        ("promotion", "REDEEM_COUPON_ENTITLEMENT", "USED/v4 platform"),
        ("promotion", "CREATE_COUPON_TEMPLATE", "DRAFT/v1 merchant"),
        ("promotion", "ACTIVATE_COUPON_TEMPLATE", "ACTIVE/v2 merchant"),
        ("promotion", "ISSUE_COUPON_ENTITLEMENT", "ISSUED/v1 merchant"),
        ("promotion", "COLLECT_COUPON_ENTITLEMENT", "AVAILABLE/v2 merchant"),
        ("promotion", "RESERVE_COUPON_ENTITLEMENT", "RESERVED/v3 merchant"),
        ("promotion", "REDEEM_COUPON_ENTITLEMENT", "USED/v4 merchant"),
    )
    promotion = (single_entitlement if benefit_mode == "entitlement-backed"
                 else stacked_entitlements if benefit_mode == "stacked-entitlements"
                 else ()) if flow_mode == "full" else ()
    forward = (
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
        ("fulfillment", "CREATE", "CREATED/v1"),
        ("inventory", "SHIP", "8/0/8/v3"),
        ("fulfillment", "SHIP", "SHIPPED/v2"),
        ("order", "SHIP_WITH_FULFILLMENT", "SHIPPED/v4"),
        ("fulfillment", "MARK_IN_TRANSIT", "IN_TRANSIT/v3"),
        ("fulfillment", "DELIVER", "DELIVERED/v4"),
        ("order", "COMPLETE_AFTER_DELIVERY", "COMPLETED/v5"),
    )
    if return_plan == "multi-line-full":
        forward = (
            ("listing", "CREATE_DRAFT", "two offers DRAFT/v1"),
            ("listing", "SUBMIT", "SUBMITTED/v2"),
            ("listing", "PASS_COMPLETION", "COMPLETION_PASSED/v3"),
            ("listing", "APPROVE_BUSINESS", "BUSINESS_APPROVED/v4"),
            ("listing", "APPROVE_RISK", "RISK_APPROVED/v5"),
            ("listing", "PUBLISH", "two offers PUBLISHED/v6"),
            ("inventory", "RECEIVE_LINE_1", "10/0/10/v1"),
            ("inventory", "RECEIVE_LINE_2", "10/0/10/v1"),
            ("order", "PLACE_FROM_LISTING", "two lines PLACED/v1"),
            ("inventory", "RESERVE_LINE_1", "10/1/9/v2"),
            ("inventory", "RESERVE_LINE_2", "10/1/9/v2"),
            ("order", "CONFIRM_INVENTORY", "two reservations INVENTORY_RESERVED/v2"),
            ("payment", "CAPTURE", "CAPTURED/v1"),
            ("order", "CONFIRM_PAYMENT", "PAYMENT_CONFIRMED/v3"),
            ("fulfillment", "CREATE", "two lines CREATED/v1"),
            ("inventory", "SHIP_LINE_1", "9/0/9/v3"),
            ("inventory", "SHIP_LINE_2", "9/0/9/v3"),
            ("fulfillment", "SHIP", "SHIPPED/v2"),
            ("order", "SHIP_WITH_FULFILLMENT", "SHIPPED/v4"),
            ("fulfillment", "MARK_IN_TRANSIT", "IN_TRANSIT/v3"),
            ("fulfillment", "DELIVER", "DELIVERED/v4"),
            ("order", "COMPLETE_AFTER_DELIVERY", "COMPLETED/v5"),
        )
    operations = manifest["operations"]
    one_case = (
        ("aftersales", operations["request"], "REQUESTED/v1"),
        ("aftersales", operations["approve"], "APPROVED/v2 + return CREATED/v1"),
        ("aftersales", operations["hand_over_return"], "return HANDED_OVER/v2"),
        ("aftersales", operations["mark_return_in_transit"], "return IN_TRANSIT/v3"),
        ("aftersales", operations["receive_return"], "return RECEIVED/v4"),
        ("aftersales", operations["accept_inspection"],
         "return INSPECTION_ACCEPTED/v5 + resolution Saga started"),
        ("aftersales", "POLL", "case COMPLETED/v4 + governed resolution Saga terminal"
         if benefit_mode != "none"
         else "case COMPLETED/v4 + resolution Saga terminal"),
    )
    aftersales = one_case if return_plan == "full" else (
        *one_case,
        ("proof", "VERIFY_PARTIAL",
         "first line/case leaves Order non-terminal and Payment PARTIALLY_REFUNDED"),
        *one_case,
    )
    aftersales += (
        ("proof", "REPLAY_ALL_CLIENT_WRITES",
         f"all {forward_count + EXPECTED_AFTERSALES_COMMANDS * case_count + PROMOTION_WRITES_BY_BENEFIT_MODE.get(benefit_mode, 0)} immutable duplicates"
         if flow_mode == "full"
         else f"all {EXPECTED_AFTERSALES_COMMANDS * case_count} immutable duplicates"),
        ("safety", "RETAIN", "no destructive cleanup after refund"),
    )
    selected = promotion + forward + aftersales if flow_mode == "full" else aftersales
    return [
        {"step": index, "domain": domain, "operation": operation, "expected": expected}
        for index, (domain, operation, expected) in enumerate(selected, 1)
    ]


def run_ledger_path(args: argparse.Namespace) -> Path:
    run_root = Path(os.environ.get(
        "CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    return run_root / "aftersales" / args.run_id / "ledger.json"


def load_scenario_contract() -> dict:
    try:
        return json.loads(DEFAULT_SCENARIO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read after-sales scenario contract: {exc}") from exc


def load_completed_order_evidence(args: argparse.Namespace) -> tuple[dict, str]:
    require(bool(args.completed_order_evidence),
            "existing-order mode requires --completed-order-evidence")
    path = Path(args.completed_order_evidence).expanduser().resolve()
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read completed-order evidence {path}: {exc}") from exc
    require(evidence.get("scenario") == EXISTING_ORDER_EVIDENCE_SCENARIO,
            "completed-order evidence has an unexpected scenario")
    require(evidence.get("tenant") == args.tenant,
            "completed-order evidence tenant does not match the requested tenant")
    require(evidence.get("environment") == args.environment,
            "completed-order evidence environment does not match the requested environment")
    final = evidence.get("final") or {}
    listing = final.get("listing") or {}
    order = final.get("order") or {}
    payment = final.get("payment") or {}
    fulfillment = final.get("fulfillment") or {}
    inventory = final.get("inventory") or {}
    require(listing.get("currentStatus") == "PUBLISHED"
            and listing.get("aggregateVersion") == 6,
            "completed-order evidence must prove Listing PUBLISHED/v6")
    require(order.get("currentStatus") == "COMPLETED" and order.get("aggregateVersion") == 5,
            "completed-order evidence must prove Order COMPLETED/v5")
    items = order.get("items") or []
    require(len(items) == 1 and bool(items[0].get("orderItemId")),
            "completed-order evidence must contain exactly one exact Order item")
    require(payment.get("currentStatus") == "CAPTURED"
            and payment.get("aggregateVersion") == 1
            and payment.get("capturedAmountMinor") == PAYABLE_MINOR,
            "completed-order evidence must prove exact Payment CAPTURED/v1")
    require(fulfillment.get("currentStatus") == "DELIVERED"
            and fulfillment.get("aggregateVersion") == 4,
            "completed-order evidence must prove positive Fulfillment DELIVERED/v4")
    require(str(inventory.get("onHandQuantity")) in {"8", "8.0", "8.000000"}
            and str(inventory.get("reservedQuantity")) in {"0", "0.0", "0.000000"}
            and str(inventory.get("availableQuantity")) in {"8", "8.0", "8.000000"}
            and inventory.get("aggregateVersion") == 3,
            "completed-order evidence must prove Inventory 8/0/8/v3")
    sku_id = evidence.get("canonical_sku_id") or items[0].get("canonicalSkuId")
    spu_id = evidence.get("canonical_spu_id")
    require(isinstance(sku_id, str) and sku_id and isinstance(spu_id, str) and spu_id,
            "completed-order evidence must include canonical SKU and SPU identities")
    forward = {
        "listing": listing,
        "listing_id": listing.get("listingId"),
        "order": order,
        "order_id": order.get("orderId"),
        "order_item_id": items[0]["orderItemId"],
        "payment": payment,
        "payment_id": payment.get("paymentId"),
        "fulfillment": fulfillment,
        "fulfillment_id": fulfillment.get("fulfillmentId"),
        "inventory": inventory,
        "canonical_sku_id": sku_id,
        "canonical_spu_id": spu_id,
    }
    require(all(forward.get(key) for key in (
        "listing_id", "order_id", "payment_id", "fulfillment_id")),
        "completed-order evidence is missing an exact aggregate identity")
    return forward, str(path)


def resolve_execution_input(args: argparse.Namespace) -> tuple[str, str, str | None, dict | None]:
    if args.flow_mode == "existing-order":
        forward, evidence_path = load_completed_order_evidence(args)
        return (forward["canonical_sku_id"], forward["canonical_spu_id"],
                evidence_path, forward)
    sku_id, spu_id, catalog_ledger = load_catalog_identity(args)
    return sku_id, spu_id, catalog_ledger, None


def resolve_multi_line_skus(args: argparse.Namespace, primary_sku_id: str,
                            catalog_ledger: str | None) -> list[str]:
    second = args.second_sku_id
    if second is None:
        require(bool(catalog_ledger),
                "multi-line return proof requires --second-sku-id or an ACTIVE --catalog-ledger")
        try:
            evidence = json.loads(Path(catalog_ledger).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScenarioError(f"cannot read catalog ledger for second SKU: {exc}") from exc
        candidates = (evidence.get("final") or {}).get("sku_ids") or []
        second = next((value for value in candidates if value != primary_sku_id), None)
    require(isinstance(second, str) and second and second != primary_sku_id,
            "multi-line return proof requires a distinct second canonical SKU")
    return [primary_sku_id, second]


def validate_case(result: dict, status: str, version: int, operation: str) -> None:
    require(result.get("caseStatus") == status and result.get("aggregateVersion") == version,
            f"{operation} case invariant failed: {result}")


def proportional_delta(amount_minor: int, previous_quantity: Decimal,
                       requested_quantity: Decimal, ordered_quantity: Decimal) -> int:
    before = int(Decimal(amount_minor) * previous_quantity / ordered_quantity)
    after = int(Decimal(amount_minor) * (previous_quantity + requested_quantity) / ordered_quantity)
    return after - before


def return_waybill_no(run_id: str, case_start_index: int) -> str:
    # Keep the original single/full-case payload stable for immutable replay.
    return f"RTN-{run_id}" if case_start_index == 20 else f"RTN-{run_id}-{case_start_index}"


def execute_aftersales(recorder: CheckpointRecorder, args: argparse.Namespace,
                       manifest: dict, forward: dict, *, start_index: int = 20,
                       order_item_id: str | None = None,
                       requested_quantity: Decimal | None = None,
                       previously_returned: Decimal = Decimal("0"),
                       expect_full: bool = True) -> tuple[dict, list[dict]]:
    selected_order_item_id = order_item_id or forward["order_item_id"]
    item = next(value for value in forward["order"]["items"]
                if value["orderItemId"] == selected_order_item_id)
    ordered_quantity = Decimal(str(item.get("quantity", "2")))
    quantity = requested_quantity or ordered_quantity - previously_returned
    expected_gross = proportional_delta(
        item["lineAmountMinor"], previously_returned, quantity, ordered_quantity)
    ordered_benefit = item.get("discountAmountMinor")
    if ordered_benefit is None:
        ordered_benefit = item["lineAmountMinor"] - item["netAmountMinor"]
    expected_benefit = proportional_delta(
        ordered_benefit, previously_returned, quantity, ordered_quantity)
    expected_net = expected_gross - expected_benefit
    operations = manifest["operations"]
    recovery_endpoint = manifest["endpoints"]["aftersales_query_by_order_item"]
    recovery_query = recovery_endpoint["path"] + "?" + urlencode({
        recovery_endpoint.get("order_id_parameter", "orderId"): forward["order_id"],
        recovery_endpoint.get("order_item_id_parameter", "orderItemId"): selected_order_item_id,
    })
    request = recorder.call("aftersales", "aftersales_command", aftersales_payload(
        args.run_id, start_index, operations["request"], "order-completed",
        orderId=forward["order_id"], orderItemId=selected_order_item_id,
        requestedQuantity=format(quantity, "f"),
        afterSaleType="RETURN_AND_REFUND", reasonCode="SIZE_NOT_FIT",
        responsibility="BUYER",
        reason="buyer requested governed return and refund after delivery"),
        ambiguity_query=recovery_query)
    validate_case(request, "REQUESTED", 1, operations["request"])
    require(request.get("orderId") == forward["order_id"]
            and request.get("orderItemId") == selected_order_item_id
            and bool(request.get("afterSaleItemId")),
            f"REQUEST exact item invariant failed: {request}")
    aftersales_id = request["afterSaleId"]

    approve = recorder.call("aftersales", "aftersales_command", aftersales_payload(
        args.run_id, start_index + 1, operations["approve"], "aftersale-request",
        afterSaleId=aftersales_id, expectedVersion=1,
        reviewerId=f"operator:{args.run_id}"))
    validate_case(approve, "APPROVED", 2, operations["approve"])
    require(approve.get("returnFulfillmentStatus") == "CREATED"
            and bool(approve.get("returnFulfillmentId"))
            and approve.get("approvedAmountMinor") == expected_net
            and approve.get("grossAmountMinor") == expected_gross
            and approve.get("benefitAmountMinor") == expected_benefit
            and approve.get("netAmountMinor") == expected_net
            and approve.get("currencyCode") == "CNY",
            f"APPROVE must create exact reverse fulfillment: {approve}")
    return_fulfillment_id = approve["returnFulfillmentId"]

    hand_over = recorder.call("aftersales", "aftersales_command", aftersales_payload(
        args.run_id, start_index + 2, operations["hand_over_return"], "aftersale-approved",
        afterSaleId=aftersales_id, expectedVersion=2,
        carrierCode="INTERNAL_TEST", waybillNo=return_waybill_no(args.run_id, start_index)))
    validate_case(hand_over, "APPROVED", 2, operations["hand_over_return"])
    require(hand_over.get("returnFulfillmentId") == return_fulfillment_id
            and hand_over.get("returnFulfillmentStatus") == "HANDED_OVER"
            and bool(hand_over.get("returnShipmentId")),
            f"HAND_OVER_RETURN invariant failed: {hand_over}")

    in_transit = recorder.call("aftersales", "aftersales_command", aftersales_payload(
        args.run_id, start_index + 3, operations["mark_return_in_transit"], "return-handed-over",
        afterSaleId=aftersales_id, expectedVersion=2))
    validate_case(in_transit, "APPROVED", 2, operations["mark_return_in_transit"])
    require(in_transit.get("returnFulfillmentStatus") == "IN_TRANSIT",
            f"MARK_RETURN_IN_TRANSIT invariant failed: {in_transit}")

    received = recorder.call("aftersales", "aftersales_command", aftersales_payload(
        args.run_id, start_index + 4, operations["receive_return"], "return-in-transit",
        afterSaleId=aftersales_id, expectedVersion=2,
        receiverId=f"warehouse-receiver:{args.run_id}"))
    validate_case(received, "APPROVED", 2, operations["receive_return"])
    require(received.get("returnFulfillmentStatus") == "RECEIVED",
            f"RECEIVE_RETURN invariant failed: {received}")

    accepted = recorder.call("aftersales", "aftersales_command", aftersales_payload(
        args.run_id, start_index + 5, operations["accept_inspection"], "return-received",
        afterSaleId=aftersales_id, expectedVersion=2,
        inspectorId=f"quality-inspector:{args.run_id}", qualityStatus="QUALIFIED"))
    require(accepted.get("returnFulfillmentStatus") == "INSPECTION_ACCEPTED"
            and bool(accepted.get("inspectionId"))
            and bool(accepted.get("resolutionSagaId")),
            f"ACCEPT_INSPECTION must start resolution Saga: {accepted}")
    require(accepted.get("caseStatus") in {"RESOLUTION_PENDING", "COMPLETED"}
            and accepted.get("aggregateVersion") in {3, 4}
            and accepted.get("resolutionSagaStatus") in {
                "REQUESTED", "RUNNING", "RETRY_SCHEDULED", "COMPLETED"},
            f"ACCEPT_INSPECTION Saga state invariant failed: {accepted}")

    terminal, observations = poll_aftersales(
        recorder.client, recorder.ledger, manifest, aftersales_id,
        args.saga_timeout, args.poll_interval, time.sleep, time.monotonic)
    terminal_contract = manifest["terminal"]
    require(terminal.get("caseStatus") == terminal_contract["case_status"]
            and terminal.get("aggregateVersion") == terminal_contract["case_version"],
            f"AfterSale terminal case invariant failed: {terminal}")
    require(terminal.get("returnFulfillmentStatus")
            == terminal_contract["return_fulfillment_status"],
            f"AfterSale terminal reverse fulfillment invariant failed: {terminal}")
    saga_version_baseline = (10 if expected_benefit > 0 else 8) + (4 if expect_full else 0)
    saga_version = terminal.get("resolutionSagaVersion")
    require(terminal.get("resolutionSagaStatus")
            == terminal_contract["resolution_saga_status"]
            and isinstance(saga_version, int)
            and saga_version >= saga_version_baseline
            and (saga_version - saga_version_baseline) % 2 == 0,
            f"AfterSale terminal Saga invariant failed: {terminal}")
    require(terminal.get("refundStatus") == manifest["terminal"].get("refund_status", "SUCCEEDED")
            and terminal.get("approvedAmountMinor") == expected_net
            and terminal.get("grossAmountMinor") == expected_gross
            and terminal.get("benefitAmountMinor") == expected_benefit
            and terminal.get("netAmountMinor") == expected_net
            and terminal.get("currencyCode") == "CNY"
            and bool(terminal.get("paymentRefundTransactionId")),
            f"AfterSale terminal refund invariant failed: {terminal}")
    require(bool(terminal.get("inventoryOperationId"))
            and bool(terminal.get("inventoryLedgerTransactionId")),
            f"AfterSale terminal inventory evidence invariant failed: {terminal}")
    require((expected_benefit == 0 and terminal.get("benefitReversalStatus") == "NOT_REQUIRED")
            or (expected_benefit > 0
                and terminal.get("benefitReversalStatus") == "RECORDED"
                and terminal.get("benefitReversalAmountMinor") == expected_benefit
                and bool(terminal.get("benefitReversalBatchId"))),
            f"AfterSale terminal benefit reversal invariant failed: {terminal}")
    require(terminal.get("orderReturnFull") is expect_full
            and bool(terminal.get("orderSettlementEffectId"))
            and isinstance(terminal.get("orderSettlementVersion"), int)
            and terminal.get("orderSettlementVersion") >= 1,
            f"AfterSale cumulative Order settlement invariant failed: {terminal}")
    require(terminal.get("afterSaleItemId") == request.get("afterSaleItemId")
            and terminal.get("orderItemId") == selected_order_item_id,
            f"AfterSale terminal item identity invariant failed: {terminal}")
    recorder.ledger.mark_irreversible(
        aftersales_id, terminal.get("paymentRefundTransactionId"))
    return terminal, observations


def execute(args: argparse.Namespace, manifest: dict) -> dict:
    sku_id, spu_id, source_evidence, existing_forward = resolve_execution_input(args)
    master = None
    if args.flow_mode == "full":
        master = load_master_identity(args.master_ledger, args.tenant)
        args.publisher_principal_id = master["principal_id"]
        args.merchant_id = master["merchant_id"]
        args.shop_id = master["shop_id"]
        args.owner_id = master["merchant_id"]
        args.warehouse_id = master["warehouse_id"]
        args.published_listing = master["published_listing"]
    require(args.return_plan != "multi-line-full" or args.flow_mode == "full",
            "multi-line return proof currently requires full forward execution")
    require(args.return_plan != "multi-line-full" or args.benefit_mode == "none",
            "multi-line return proof currently isolates settlement and requires --benefit-mode none")
    multi_line_sku_ids = (resolve_multi_line_skus(args, sku_id, source_evidence)
                          if args.return_plan == "multi-line-full" else None)
    client = authenticated_client(args)
    openapi = client.openapi()
    missing = verify_openapi(openapi, manifest)
    require(not missing, f"live OpenAPI is missing endpoint-manifest routes: {missing}")
    scenario = load_scenario_contract()
    identity = {
        "scenario": SCENARIO_NAME,
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "source_commit": source_commit(args.workspace),
        "endpoint_manifest_hash": endpoint_fingerprint(manifest),
        "openapi_paths_hash": openapi_fingerprint(openapi),
        "scenario_contract_hash": sha256_json(scenario),
        "source_evidence": source_evidence,
        "master_evidence": master["path"] if master else None,
        "flow_mode": args.flow_mode,
        "return_plan": args.return_plan,
        "canonical_sku_id": sku_id,
        "canonical_sku_ids": multi_line_sku_ids,
        "canonical_spu_id": spu_id,
        "merchant_id": master["merchant_id"] if master else None,
        "shop_id": master["shop_id"] if master else None,
        "publisher_principal_id": master["principal_id"] if master else None,
        "warehouse_id": master["warehouse_id"] if master else None,
    }
    ledger = AtomicRunLedger(run_ledger_path(args), identity)
    recorder = CheckpointRecorder(client, ledger, manifest)
    try:
        if args.return_plan == "multi-line-full":
            forward = execute_multi_line_forward_to_completed(
                recorder, args, multi_line_sku_ids, spu_id)
            first_terminal, first_observations = execute_aftersales(
                recorder, args, manifest, forward, start_index=23,
                order_item_id=forward["order_item_ids"][0], expect_full=False)
            terminal, second_observations = execute_aftersales(
                recorder, args, manifest, forward, start_index=29,
                order_item_id=forward["order_item_ids"][1], expect_full=True)
            terminals = [first_terminal, terminal]
            observations = first_observations + second_observations
        else:
            forward = (existing_forward if existing_forward is not None
                       else execute_forward_to_completed(recorder, args, manifest, sku_id, spu_id))
        if args.return_plan == "partial-then-full":
            first_terminal, first_observations = execute_aftersales(
                recorder, args, manifest, forward, start_index=20,
                requested_quantity=Decimal("1"), expect_full=False)
            terminal, second_observations = execute_aftersales(
                recorder, args, manifest, forward, start_index=26,
                requested_quantity=Decimal("1"), previously_returned=Decimal("1"),
                expect_full=True)
            terminals = [first_terminal, terminal]
            observations = first_observations + second_observations
        elif args.return_plan == "full":
            terminal, observations = execute_aftersales(recorder, args, manifest, forward)
            terminals = [terminal]
        replay = recorder.replay_all()
        aftersales_commands = EXPECTED_AFTERSALES_COMMANDS * len(terminals)
        forward_commands = (22 if args.return_plan == "multi-line-full"
                            else 13 if getattr(args, "published_listing", None) else 19)
        expected_commands = (forward_commands + aftersales_commands
                             + PROMOTION_WRITES_BY_BENEFIT_MODE.get(args.benefit_mode, 0)
                             if args.flow_mode == "full" else aftersales_commands)
        require(len(replay) == expected_commands,
                f"expected {expected_commands} client command replays, got {len(replay)}")
        aftersales_id = terminal["afterSaleId"]
        final = {
            "listing": forward["listing"],
            "forward_fulfillment": forward["fulfillment"],
            "aftersales": terminal,
            "aftersales_cases": terminals,
            "all_replay_duplicate": True,
            "client_command_count": expected_commands,
            "flow_mode": args.flow_mode,
            "return_plan": args.return_plan,
            "cleanup_policy": "retain; refund is irreversible; compensation/manual review only",
            "expected_participant_terminal": manifest["terminal"],
            "master_identity": master,
        }
        ledger.data["replay"] = replay
        ledger.data["saga_observations"] = observations
        ledger.data["lakehouse_evidence_hook"] = {
            "run_id": args.run_id,
            "aftersales_ids": [value["afterSaleId"] for value in terminals],
            "expected_command": "reconcile-canonical-aftersales",
            "read_only_after_cdc_timeout": True,
        }
        ledger.finish("SUCCEEDED", final)
        return {
            "status": "succeeded",
            "run_id": args.run_id,
            "ledger": str(ledger.path),
            "canonical_sku_id": sku_id,
            "canonical_spu_id": spu_id,
            "aftersales_id": aftersales_id,
            "all_replay_duplicate": True,
            "client_command_count": expected_commands,
            **final,
        }
    except Exception as exc:
        ledger.finish("FAILED", error=str(exc))
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv(
        "CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--workspace", default=os.getenv(
        "CLOUDMOLD_WORKSPACE", "/Users/karekin/Downloads/coding/project/CloudMold"))
    parser.add_argument("--endpoint-manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--flow-mode", choices=("full", "existing-order"), default="full")
    parser.add_argument("--return-plan",
                        choices=("full", "partial-then-full", "multi-line-full"),
                        default="full")
    parser.add_argument("--benefit-mode", choices=("none", "governed-split", "entitlement-backed",
                                                   "stacked-entitlements"),
                        default="none")
    parser.add_argument("--completed-order-evidence")
    parser.add_argument("--sku-id")
    parser.add_argument("--second-sku-id")
    parser.add_argument("--spu-id")
    parser.add_argument("--catalog-ledger")
    parser.add_argument("--master-ledger", default=os.getenv("CLOUDMOLD_MASTER_LEDGER"))
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
                "the after-sales runner is restricted to local, demo, or test")
        require(args.saga_timeout > 0 and args.poll_interval > 0,
                "Saga timeout and poll interval must be positive")
        require(args.return_plan != "multi-line-full" or args.flow_mode == "full",
                "multi-line return proof currently requires --flow-mode full")
        require(args.return_plan != "multi-line-full" or args.benefit_mode == "none",
                "multi-line return proof currently requires --benefit-mode none")
        manifest = load_endpoint_manifest(args.endpoint_manifest)
        sku_id, spu_id, source_evidence, _ = resolve_execution_input(args)
        multi_line_sku_ids = (resolve_multi_line_skus(args, sku_id, source_evidence)
                              if args.return_plan == "multi-line-full" else None)
        if args.mode == "execute" and args.flow_mode == "full":
            require(bool(source_evidence),
                    "full execute requires --catalog-ledger from an ACTIVE same-tenant Catalog run")
        if args.mode == "plan":
            result = {
                "scenario": SCENARIO_NAME,
                "run_id": args.run_id,
                "canonical_sku_id": sku_id,
                "canonical_sku_ids": multi_line_sku_ids,
                "canonical_spu_id": spu_id,
                "source_evidence": source_evidence,
                "flow_mode": args.flow_mode,
                "endpoint_manifest": str(Path(args.endpoint_manifest).expanduser().resolve()),
                "endpoint_manifest_hash": endpoint_fingerprint(manifest),
                "return_plan": args.return_plan,
                "steps": scenario_plan(manifest, args.flow_mode, args.benefit_mode, args.return_plan),
                "client_command_replay": (
                    f"all {(22 if args.return_plan == 'multi-line-full' else 19) + EXPECTED_AFTERSALES_COMMANDS * (1 if args.return_plan == 'full' else 2) + PROMOTION_WRITES_BY_BENEFIT_MODE.get(args.benefit_mode, 0)} writes"
                    if args.flow_mode == "full"
                    else f"all {EXPECTED_AFTERSALES_COMMANDS * (1 if args.return_plan == 'full' else 2)} AfterSale writes"),
                "participant_writes": "backend resolution Saga only",
                "cleanup": "no destructive cleanup after refund",
                "side_effects": False,
            }
        elif args.mode == "dry-run":
            document = Client(args.base_url, args.tenant, None, args.timeout).openapi()
            missing = verify_openapi(document, manifest)
            require(not missing, f"live OpenAPI is missing endpoint-manifest routes: {missing}")
            result = {
                "status": "ready",
                "run_id": args.run_id,
                "routes": [
                    f"{value['method'].upper()} {value['path']}"
                    for value in manifest["endpoints"].values()
                ],
                "openapi_paths_hash": openapi_fingerprint(document),
                "endpoint_manifest_hash": endpoint_fingerprint(manifest),
                "side_effects": False,
            }
        else:
            result = execute(args, manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
