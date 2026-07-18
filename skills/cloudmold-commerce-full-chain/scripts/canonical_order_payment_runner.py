#!/usr/bin/env python3
"""Deterministic Agent runner for canonical Order/Payment and Order Benefit slices."""

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

from canonical_inventory_runner import Client, ScenarioError, decimal, request_hash, resolve_catalog_sku


INVENTORY_ROUTE = "/admin-api/cloudmold/inventory/command"
ORDER_ROUTE = "/admin-api/cloudmold/order/command"
PAYMENT_ROUTE = "/admin-api/cloudmold/payment/command"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,31}$")
GROSS_AMOUNT_MINOR = 39800
GOVERNED_DISCOUNT_MINOR = 3800


def event_time(run_id: str, index: int) -> str:
    seed = int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16) % (365 * 24 * 60 * 60)
    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seed)
    return (start + dt.timedelta(seconds=index)).isoformat().replace("+00:00", "Z")


def metadata(run_id: str, index: int, operation: str) -> dict:
    return {
        "idempotencyKey": f"{run_id}-{index:02d}-{operation.lower()}",
        "correlationId": str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{run_id}:commerce:{index}")),
        "occurredAt": event_time(run_id, index),
    }


def inventory_payload(run_id: str, index: int, operation: str, sku_id: str, warehouse_id: str,
                      owner_id: str, quantity: str, business_type: str, business_id: str,
                      business_item_id: str, business_no: str, reservation_id: str | None = None) -> dict:
    payload = {
        "operation": operation,
        **metadata(run_id, index, operation),
        "ownerId": owner_id,
        "canonicalSkuId": sku_id,
        "warehouseId": warehouse_id,
        "stockStatus": "SELLABLE",
        "qualityStatus": "QUALIFIED",
        "uomCode": "PCS",
        "quantity": quantity,
        "businessType": business_type,
        "businessId": business_id,
        "businessItemId": business_item_id,
        "businessNo": business_no,
    }
    if reservation_id:
        payload["reservationId"] = reservation_id
    return payload


def order_payload(run_id: str, index: int, operation: str, **values: object) -> dict:
    return {"operation": operation, **metadata(run_id, index, operation), "runId": run_id, **values}


def payment_payload(run_id: str, index: int, operation: str, **values: object) -> dict:
    return {"operation": operation, **metadata(run_id, index, operation), "runId": run_id, **values}


def governed_benefit_application(run_id: str, entitlement_id: str | None = None,
                                 entitlement_version: int | None = None,
                                 merchant_id: str = "controlled-merchant",
                                 application_key: str = "promotion-1",
                                 amount_minor: int = GOVERNED_DISCOUNT_MINOR,
                                 funding: list[dict] | None = None) -> dict:
    funding = funding or [
        {"fundingKey": f"{application_key}-line-1-platform", "funderType": "PLATFORM",
         "funderId": "cloudmold", "amountMinor": 2000},
        {"fundingKey": f"{application_key}-line-1-merchant", "funderType": "MERCHANT",
         "funderId": merchant_id, "amountMinor": 1800},
    ]
    calculation_input = {
        "algorithm": "governed-order-benefit-first-slice-v1",
        "application_key": application_key,
        "gross_amount_minor": GROSS_AMOUNT_MINOR,
        "discount_amount_minor": amount_minor,
        "currency_code": "CNY",
        "line_key": "line-1",
        "entitlement_id": entitlement_id,
        "entitlement_version": entitlement_version,
        "funding": [{"funder_type": item["funderType"], "funder_id": item["funderId"],
                     "amount_minor": item["amountMinor"]} for item in funding],
    }
    calculation_digest = hashlib.sha256(json.dumps(
        calculation_input, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {
        "applicationKey": application_key,
        "benefitType": "COUPON" if entitlement_id else "PROMOTION",
        "benefitSourceType": "COUPON_ENTITLEMENT" if entitlement_id else "CONTROLLED_PROMOTION",
        "benefitSourceId": entitlement_id or f"governed-promotion:{run_id}",
        "benefitSourceVersion": entitlement_version or 1,
        "entitlementId": entitlement_id,
        "amountMinor": amount_minor,
        "calculationDigest": calculation_digest,
        "allocations": [{
            "allocationKey": f"{application_key}-line-1",
            "lineKey": "line-1",
            "amountMinor": amount_minor,
            "funding": funding,
        }],
    }


def stacked_entitlement_applications(run_id: str, entitlement_ids: list[str],
                                     entitlement_version: int,
                                     merchant_id: str) -> list[dict]:
    require(len(entitlement_ids) == 2 and len(set(entitlement_ids)) == 2,
            "stacked entitlement proof requires two distinct entitlement IDs")
    return [
        governed_benefit_application(
            run_id, entitlement_ids[0], entitlement_version, merchant_id,
            application_key="coupon-platform", amount_minor=2000,
            funding=[{"fundingKey": "coupon-platform-line-1-platform",
                      "funderType": "PLATFORM", "funderId": "cloudmold", "amountMinor": 2000}]),
        governed_benefit_application(
            run_id, entitlement_ids[1], entitlement_version, merchant_id,
            application_key="coupon-merchant", amount_minor=1800,
            funding=[{"fundingKey": "coupon-merchant-line-1-merchant",
                      "funderType": "MERCHANT", "funderId": merchant_id, "amountMinor": 1800}]),
    ]


def commerce_amounts(benefit_mode: str) -> tuple[int, int]:
    discount = GOVERNED_DISCOUNT_MINOR if benefit_mode != "none" else 0
    return discount, GROSS_AMOUNT_MINOR - discount


def validate_benefit_result(result: dict, benefit_mode: str) -> None:
    applications = result.get("benefitApplications") or []
    items = result.get("items") or []
    if benefit_mode == "none":
        require(not applications, f"zero-discount order unexpectedly returned benefits: {applications}")
        return
    expected_applications = 2 if benefit_mode == "stacked-entitlements" else 1
    require(len(applications) == expected_applications and len(items) == 1,
            f"governed benefit cardinality mismatch: applications={applications} items={items}")
    application_total = 0
    entitlement_sources = set()
    for application in applications:
        allocations = application.get("allocations") or []
        require(len(allocations) == 1, f"governed benefit application mismatch: {application}")
        allocation = allocations[0]
        funding = allocation.get("funding") or []
        require(allocation.get("lineKey") == "line-1"
                and allocation.get("amountMinor") == application.get("amountMinor")
                and sum(item.get("amountMinor", 0) for item in funding) == application.get("amountMinor"),
                f"governed benefit allocation/funding mismatch: {allocation}")
        application_total += application.get("amountMinor", 0)
        if application.get("entitlementId"):
            require(application.get("benefitSourceType") == "COUPON_ENTITLEMENT"
                    and application.get("benefitSourceId") == application.get("entitlementId"),
                    f"entitlement source identity mismatch: {application}")
            entitlement_sources.add((application.get("benefitSourceId"),
                                     application.get("benefitSourceVersion")))
    require(application_total == GOVERNED_DISCOUNT_MINOR,
            f"governed benefit applications do not conserve discount: {applications}")
    if benefit_mode == "stacked-entitlements":
        require(len(entitlement_sources) == 2,
                f"stacked entitlement sources are not distinct: {applications}")
    require(items[0].get("lineKey") == "line-1"
            and items[0].get("lineAmountMinor") == GROSS_AMOUNT_MINOR
            and items[0].get("discountAmountMinor") == GOVERNED_DISCOUNT_MINOR
            and items[0].get("netAmountMinor") == GROSS_AMOUNT_MINOR - GOVERNED_DISCOUNT_MINOR,
            f"governed benefit order-line conservation mismatch: {items[0]}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def validate_inventory(result: dict, expected: tuple[str, str, str, int], operation: str) -> None:
    actual = (decimal(result["onHandQuantity"]), decimal(result["reservedQuantity"]),
              decimal(result["availableQuantity"]), result["aggregateVersion"])
    require(actual == expected, f"{operation} inventory invariant mismatch: expected={expected} actual={actual}")


def stable_result(result: dict) -> dict:
    value = dict(result)
    value.pop("duplicate", None)
    return value


def execute(args: argparse.Namespace) -> dict:
    client = Client(args.base_url, args.tenant, args.token, args.timeout)
    if not client.token:
        if not args.username or not args.password:
            raise ScenarioError("set token or username/password through environment variables")
        client.login(args.username, args.password)
    sku_id, catalog_ledger = resolve_catalog_sku(args)
    warehouse_id = args.warehouse_id or f"scenario:{args.run_id}"
    discount_amount, payable_amount = commerce_amounts(args.benefit_mode)
    calls: list[dict] = []

    def call(domain: str, route: str, payload: dict) -> dict:
        result = client.request("POST", route, payload)
        calls.append({"domain": domain, "route": route, "operation": payload["operation"],
                      "request_hash": request_hash(payload), "payload": payload, "result": result})
        return result

    receive = inventory_payload(args.run_id, 1, "RECEIVE", sku_id, warehouse_id, args.owner_id,
                                "10.000000", "TEST_FIXTURE", args.run_id, "fixture-line",
                                f"FIXTURE-{args.run_id}")
    receive_result = call("inventory", INVENTORY_ROUTE, receive)
    validate_inventory(receive_result, ("10.000000", "0.000000", "10.000000", 1), "RECEIVE")

    place_values = {
        "buyerId": f"internal-buyer:{args.run_id}",
        "items": [{"lineKey": "line-1", "canonicalSkuId": sku_id,
                   "quantity": "2.000000", "unitPriceMinor": 19900}],
        "shippingAmountMinor": 0,
        "discountAmountMinor": discount_amount,
        "currencyCode": "CNY",
        "reason": "canonical commerce first slice" if args.benefit_mode == "none"
                  else "governed Order Benefit first slice",
    }
    if args.benefit_mode == "governed-split":
        place_values["benefitApplications"] = [governed_benefit_application(args.run_id)]
    place = order_payload(args.run_id, 2, "PLACE", **place_values)
    order = call("order", ORDER_ROUTE, place)
    require(order.get("currentStatus") == "PLACED" and order.get("aggregateVersion") == 1,
            f"PLACE invariant failed: {order}")
    require(order.get("discountAmountMinor") == discount_amount
            and order.get("payableAmountMinor") == payable_amount
            and len(order.get("items") or []) == 1,
            f"PLACE amount/item invariant failed: {order}")
    validate_benefit_result(order, args.benefit_mode)
    order_id = order["orderId"]
    order_no = order["orderNo"]
    order_item_id = order["items"][0]["orderItemId"]

    reserve = inventory_payload(args.run_id, 3, "RESERVE", sku_id, warehouse_id, args.owner_id,
                                "2.000000", "TRADE_ORDER", order_id, order_item_id, order_no)
    reserve_result = call("inventory", INVENTORY_ROUTE, reserve)
    validate_inventory(reserve_result, ("10.000000", "2.000000", "8.000000", 2), "RESERVE")
    reservation_id = reserve_result["reservationId"]

    confirm_inventory = order_payload(args.run_id, 4, "CONFIRM_INVENTORY", orderId=order_id,
                                      expectedVersion=1, reservationReferences=[{
                                          "orderItemId": order_item_id, "reservationId": reservation_id}],
                                      reason="all order lines reserved")
    order = call("order", ORDER_ROUTE, confirm_inventory)
    require(order.get("currentStatus") == "INVENTORY_RESERVED" and order.get("aggregateVersion") == 2,
            f"CONFIRM_INVENTORY invariant failed: {order}")

    capture = payment_payload(args.run_id, 5, "CAPTURE", orderId=order_id, amountMinor=payable_amount,
                              currencyCode="CNY", providerCode="INTERNAL_TEST",
                              providerTransactionId=f"capture-{args.run_id}",
                              reason="deterministic test capture")
    payment = call("payment", PAYMENT_ROUTE, capture)
    require(payment.get("currentStatus") == "CAPTURED" and payment.get("aggregateVersion") == 1
            and payment.get("capturedAmountMinor") == payable_amount and payment.get("testMode") is True,
            f"CAPTURE invariant failed: {payment}")
    payment_id = payment["paymentId"]

    confirm_payment = order_payload(args.run_id, 6, "CONFIRM_PAYMENT", orderId=order_id,
                                    expectedVersion=2, paymentId=payment_id,
                                    reason="exact payment captured")
    order = call("order", ORDER_ROUTE, confirm_payment)
    require(order.get("currentStatus") == "PAYMENT_CONFIRMED" and order.get("aggregateVersion") == 3,
            f"CONFIRM_PAYMENT invariant failed: {order}")

    ship_inventory = inventory_payload(args.run_id, 7, "SHIP", sku_id, warehouse_id, args.owner_id,
                                       "2.000000", "TRADE_ORDER", order_id, order_item_id, order_no,
                                       reservation_id)
    ship_result = call("inventory", INVENTORY_ROUTE, ship_inventory)
    validate_inventory(ship_result, ("8.000000", "0.000000", "8.000000", 3), "SHIP")

    order = call("order", ORDER_ROUTE, order_payload(args.run_id, 8, "SHIP", orderId=order_id,
                                                     expectedVersion=3, reason="inventory shipped"))
    require(order.get("currentStatus") == "SHIPPED" and order.get("aggregateVersion") == 4,
            f"SHIP order invariant failed: {order}")
    order = call("order", ORDER_ROUTE, order_payload(args.run_id, 9, "COMPLETE", orderId=order_id,
                                                     expectedVersion=4, reason="delivery confirmed"))
    require(order.get("currentStatus") == "COMPLETED" and order.get("aggregateVersion") == 5,
            f"COMPLETE invariant failed: {order}")

    refund_provider_id = f"refund-{args.run_id}"
    refund = payment_payload(args.run_id, 10, "REFUND", paymentId=payment_id, expectedVersion=1,
                             orderId=order_id, amountMinor=payable_amount, currencyCode="CNY",
                             providerCode="INTERNAL_TEST", providerTransactionId=refund_provider_id,
                             reason="full return")
    payment = call("payment", PAYMENT_ROUTE, refund)
    require(payment.get("currentStatus") == "REFUNDED" and payment.get("aggregateVersion") == 2
            and payment.get("capturedAmountMinor") == payable_amount
            and payment.get("refundedAmountMinor") == payable_amount,
            f"REFUND invariant failed: {payment}")

    order = call("order", ORDER_ROUTE, order_payload(args.run_id, 11, "CONFIRM_REFUND", orderId=order_id,
                                                     expectedVersion=5, refundId=refund_provider_id,
                                                     reason="full refund confirmed"))
    require(order.get("currentStatus") == "REFUNDED" and order.get("aggregateVersion") == 6,
            f"CONFIRM_REFUND invariant failed: {order}")

    return_inventory = inventory_payload(args.run_id, 12, "RETURN", sku_id, warehouse_id, args.owner_id,
                                         "2.000000", "TRADE_ORDER", order_id, order_item_id, order_no)
    return_result = call("inventory", INVENTORY_ROUTE, return_inventory)
    validate_inventory(return_result, ("10.000000", "0.000000", "10.000000", 4), "RETURN")

    order = call("order", ORDER_ROUTE, order_payload(args.run_id, 13, "RETURN", orderId=order_id,
                                                     expectedVersion=6, reason="returned stock received"))
    require(order.get("currentStatus") == "RETURNED" and order.get("aggregateVersion") == 7,
            f"RETURN order invariant failed: {order}")

    replayed: list[dict] = []
    for original in calls:
        replay = client.request("POST", original["route"], original["payload"])
        require(replay.get("duplicate") is True, f"{original['operation']} replay was not duplicate")
        require(stable_result(replay) == stable_result(original["result"]),
                f"{original['operation']} replay changed the immutable first result")
        replayed.append({"domain": original["domain"], "operation": original["operation"],
                         "request_hash": original["request_hash"], "result": replay})

    ledger = {
        "scenario": "canonical-order-benefit-first-slice-v1" if args.benefit_mode == "governed-split"
                    else "canonical-order-payment-first-slice-v1",
        "run_id": args.run_id,
        "benefit_mode": args.benefit_mode,
        "environment": args.environment,
        "tenant": args.tenant,
        "canonical_sku_id": sku_id,
        "catalog_ledger": catalog_ledger,
        "calls": [{key: value for key, value in item.items() if key != "payload"} for item in calls],
        "replay": replayed,
        "final": {
            "order": order,
            "payment": payment,
            "inventory": return_result,
            "all_replay_duplicate": True,
        },
    }
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "commerce" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    return {"status": "succeeded", "run_id": args.run_id, "ledger": str(output),
            "canonical_sku_id": sku_id, **ledger["final"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "execute"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", default="local")
    parser.add_argument("--base-url", default=os.getenv("CLOUDMOLD_ERP_BASE_URL", "http://127.0.0.1:48080"))
    parser.add_argument("--tenant", type=int, default=int(os.getenv("CLOUDMOLD_TENANT_ID", "1")))
    parser.add_argument("--token", default=os.getenv("CLOUDMOLD_ADMIN_TOKEN"))
    parser.add_argument("--username", default=os.getenv("CLOUDMOLD_ADMIN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("CLOUDMOLD_ADMIN_PASSWORD"))
    parser.add_argument("--sku-id")
    parser.add_argument("--catalog-ledger")
    parser.add_argument("--warehouse-id")
    parser.add_argument("--owner-id", default="internal-company")
    parser.add_argument("--benefit-mode", choices=("none", "governed-split"), default="none")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        if not RUN_ID_PATTERN.fullmatch(args.run_id):
            raise ScenarioError("run_id must be 6-32 characters using letters, digits, dot, underscore, or hyphen")
        if args.environment not in {"local", "demo", "test"}:
            raise ScenarioError("the commerce runner is restricted to local, demo, or test")
        sku_id, catalog_ledger = resolve_catalog_sku(args)
        if args.mode == "plan":
            discount_amount, payable_amount = commerce_amounts(args.benefit_mode)
            result = {"scenario": "canonical-order-benefit-first-slice-v1"
                                  if args.benefit_mode == "governed-split"
                                  else "canonical-order-payment-first-slice-v1",
                      "run_id": args.run_id, "benefit_mode": args.benefit_mode,
                      "canonical_sku_id": sku_id, "catalog_ledger": catalog_ledger,
                      "flow": ["receive", "place", "reserve", "capture", "ship", "complete",
                               "refund", "return", "replay all"],
                      "expected": {"order": "RETURNED/v7", "payment": "REFUNDED/v2",
                                   "inventory": "10/0/10/v4", "gross_minor": GROSS_AMOUNT_MINOR,
                                   "discount_minor": discount_amount, "payable_minor": payable_amount},
                      "side_effects": False}
        elif args.mode == "dry-run":
            paths = Client(args.base_url, args.tenant, args.token, args.timeout).openapi().get("paths", {})
            missing = [route for route in (INVENTORY_ROUTE, ORDER_ROUTE, PAYMENT_ROUTE)
                       if route not in paths or "post" not in paths[route]]
            if missing:
                raise ScenarioError(f"live OpenAPI is missing routes: {missing}")
            result = {"status": "ready", "run_id": args.run_id,
                      "routes": [INVENTORY_ROUTE, ORDER_ROUTE, PAYMENT_ROUTE],
                      "canonical_sku_id": sku_id, "catalog_ledger": catalog_ledger, "side_effects": False}
        else:
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ScenarioError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
