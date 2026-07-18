#!/usr/bin/env python3
"""Deterministic Listing-to-Fulfillment commerce runner for a disposable tenant."""

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

from canonical_inventory_runner import Client, ScenarioError, decimal, request_hash


LISTING_ROUTE = "/admin-api/cloudmold/listing/command"
INVENTORY_ROUTE = "/admin-api/cloudmold/inventory/command"
ORDER_ROUTE = "/admin-api/cloudmold/order/command"
PAYMENT_ROUTE = "/admin-api/cloudmold/payment/command"
FULFILLMENT_ROUTE = "/admin-api/cloudmold/fulfillment/command"
ROUTES = (LISTING_ROUTE, INVENTORY_ROUTE, ORDER_ROUTE, PAYMENT_ROUTE, FULFILLMENT_ROUTE)
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,31}$")
PRICE_MINOR = 19_900
QUANTITY = "2.000000"
PAYABLE_MINOR = 39_800


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioError(message)


def event_time(run_id: str, index: int) -> str:
    seed = int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16) % (365 * 24 * 60 * 60)
    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seed)
    return (start + dt.timedelta(seconds=index)).isoformat().replace("+00:00", "Z")


def publication_start_time(run_id: str, index: int) -> str:
    """Keep deterministic business timestamps from accidentally scheduling a future Listing."""
    candidate = dt.datetime.fromisoformat(event_time(run_id, index).replace("Z", "+00:00"))
    latest_safe_start = dt.datetime(2026, 6, 30, tzinfo=dt.timezone.utc)
    return min(candidate, latest_safe_start).isoformat().replace("+00:00", "Z")


def metadata(run_id: str, index: int, domain: str, operation: str) -> dict:
    return {
        "idempotencyKey": f"{run_id}-{index:02d}-{domain}-{operation.lower()}",
        "correlationId": str(uuid.uuid5(
            uuid.NAMESPACE_URL, f"cloudmold:{run_id}:listing-fulfillment:{index}")),
        "occurredAt": event_time(run_id, index),
    }


def load_catalog_identity(args: argparse.Namespace) -> tuple[str, str, str | None]:
    ledger_path = Path(args.catalog_ledger).expanduser().resolve() if args.catalog_ledger else None
    ledger_sku = ledger_spu = None
    ledger_sku_ids: list[str] = []
    if ledger_path:
        if not ledger_path.is_file():
            raise ScenarioError(f"Catalog ledger does not exist: {ledger_path}")
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScenarioError(f"cannot read Catalog ledger: {exc}") from exc
        require(ledger.get("scenario") == "canonical-catalog-first-slice-v1",
                "Catalog ledger has an unexpected scenario")
        require(ledger.get("tenant") == args.tenant,
                "Catalog ledger tenant does not match commerce tenant")
        final = ledger.get("final") or {}
        require(final.get("catalog_status") == "ACTIVE",
                "Catalog ledger does not prove an ACTIVE Catalog lifecycle")
        sku_ids = final.get("sku_ids")
        require(isinstance(sku_ids, list) and sku_ids
                and all(isinstance(value, str) and value for value in sku_ids),
                "Catalog ledger does not contain canonical SKU identities")
        ledger_sku_ids = sorted(sku_ids)
        ledger_sku = ledger_sku_ids[0]
        ledger_spu = final.get("spu_id")
        require(isinstance(ledger_spu, str) and ledger_spu,
                "Catalog ledger does not contain a canonical SPU identity")
    if args.sku_id and ledger_sku:
        require(args.sku_id in ledger_sku_ids,
                "--sku-id is not proven by --catalog-ledger")
    if args.spu_id and ledger_spu:
        require(args.spu_id == ledger_spu,
                "--spu-id conflicts with the canonical SPU selected from --catalog-ledger")
    sku_id = args.sku_id or ledger_sku
    spu_id = args.spu_id or ledger_spu
    require(bool(sku_id and spu_id),
            "provide an ACTIVE --catalog-ledger or both --sku-id and --spu-id")
    return sku_id, spu_id, str(ledger_path) if ledger_path else None


def listing_create_payload(run_id: str, index: int, sku_id: str, spu_id: str,
                           merchant_id: str | None = None, shop_id: str | None = None,
                           publisher_principal_id: str | None = None) -> dict:
    merchant_id = merchant_id or os.getenv("CLOUDMOLD_MERCHANT_ID", "internal-company")
    shop_id = shop_id or os.getenv("CLOUDMOLD_SHOP_ID", f"internal-shop:{run_id}")
    publisher_principal_id = publisher_principal_id or os.getenv(
        "CLOUDMOLD_PUBLISHER_PRINCIPAL_ID", "agent:cloudmold-erp-operator")
    return {
        "operation": "CREATE_DRAFT",
        **metadata(run_id, index, "listing", "CREATE_DRAFT"),
        "runId": run_id,
        "merchantId": merchant_id,
        "channelCode": os.getenv("CLOUDMOLD_CHANNEL_CODE", "YSHOPPING_INTERNAL"),
        "shopId": shop_id,
        "canonicalSpuId": spu_id,
        "title": f"Y-Shopping deterministic listing {run_id}",
        "categoryRef": "INTERNAL:CATEGORY:DRESS",
        "brandRef": "INTERNAL:BRAND:YSHOPPING",
        "sourceSystem": "cloudmold-erp-operator",
        "publisherRef": publisher_principal_id,
        "publishStartAt": publication_start_time(run_id, index),
        "offers": [{
            "canonicalSkuId": sku_id,
            "priceMinor": PRICE_MINOR,
            "currencyCode": "CNY",
            "enabled": True,
            "externalOfferId": f"internal-offer:{run_id}",
        }],
        "reason": "deterministic Listing first slice",
    }


def transition_payload(run_id: str, index: int, domain: str, operation: str,
                       aggregate_field: str, aggregate_id: str, expected_version: int,
                       **values: object) -> dict:
    return {
        "operation": operation,
        **metadata(run_id, index, domain, operation),
        "runId": run_id,
        aggregate_field: aggregate_id,
        "expectedVersion": expected_version,
        **values,
    }


def inventory_payload(run_id: str, index: int, operation: str, sku_id: str,
                      warehouse_id: str, owner_id: str, quantity: str, business_type: str,
                      business_id: str, business_item_id: str, business_no: str,
                      reservation_id: str | None = None) -> dict:
    payload = {
        "operation": operation,
        **metadata(run_id, index, "inventory", operation),
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


def place_from_listing_payload(run_id: str, index: int, sku_id: str, listing_id: str,
                               listing_offer_id: str) -> dict:
    return {
        "operation": "PLACE_FROM_LISTING",
        **metadata(run_id, index, "order", "PLACE_FROM_LISTING"),
        "runId": run_id,
        "buyerId": f"internal-buyer:{run_id}",
        "items": [{
            "canonicalSkuId": sku_id,
            "quantity": QUANTITY,
            "unitPriceMinor": PRICE_MINOR,
            "listingId": listing_id,
            "listingOfferId": listing_offer_id,
        }],
        "shippingAmountMinor": 0,
        "discountAmountMinor": 0,
        "currencyCode": "CNY",
        "reason": "order from exact published Listing offer",
    }


def payment_payload(run_id: str, index: int, operation: str, **values: object) -> dict:
    return {"operation": operation, **metadata(run_id, index, "payment", operation),
            "runId": run_id, **values}


def fulfillment_create_payload(run_id: str, index: int, order_id: str, order_item_id: str,
                               sku_id: str, reservation_id: str, warehouse_id: str,
                               seller_id: str = "internal-company") -> dict:
    return {
        "operation": "CREATE",
        **metadata(run_id, index, "fulfillment", "CREATE"),
        "runId": run_id,
        "orderId": order_id,
        "sellerId": seller_id,
        "warehouseId": warehouse_id,
        "deliveryPromiseVersionRef": "LOCAL_TEST_DELIVERY_V1",
        "promisedDeliveryAt": event_time(run_id, index + 3600),
        "items": [{
            "orderItemId": order_item_id,
            "canonicalSkuId": sku_id,
            "quantity": QUANTITY,
            "reservationId": reservation_id,
        }],
        "reason": "one complete first-slice fulfillment",
    }


def validate_inventory(result: dict, expected: tuple[str, str, str, int], operation: str) -> None:
    actual = (decimal(result["onHandQuantity"]), decimal(result["reservedQuantity"]),
              decimal(result["availableQuantity"]), result["aggregateVersion"])
    require(actual == expected,
            f"{operation} inventory invariant mismatch: expected={expected} actual={actual}")


def stable_result(result: dict) -> dict:
    value = dict(result)
    value.pop("duplicate", None)
    return value


class RunRecorder:
    def __init__(self, client: Client):
        self.client = client
        self.calls: list[dict] = []

    def call(self, domain: str, route: str, payload: dict) -> dict:
        result = self.client.request("POST", route, payload)
        self.calls.append({"domain": domain, "route": route, "operation": payload["operation"],
                           "request_hash": request_hash(payload), "payload": payload, "result": result})
        return result

    def replay_all(self) -> list[dict]:
        replayed = []
        for original in self.calls:
            replay = self.client.request("POST", original["route"], original["payload"])
            require(replay.get("duplicate") is True,
                    f"{original['domain']} {original['operation']} replay was not duplicate")
            require(stable_result(replay) == stable_result(original["result"]),
                    f"{original['domain']} {original['operation']} replay changed the immutable result")
            replayed.append({"domain": original["domain"], "operation": original["operation"],
                             "request_hash": original["request_hash"], "result": replay})
        return replayed

    def redacted_calls(self) -> list[dict]:
        return [{key: value for key, value in call.items() if key != "payload"} for call in self.calls]


def execute_listing(recorder: RunRecorder, args: argparse.Namespace, sku_id: str,
                    spu_id: str, start_index: int = 1) -> tuple[dict, str, int]:
    listing = recorder.call("listing", LISTING_ROUTE,
                            listing_create_payload(args.run_id, start_index, sku_id, spu_id))
    require(listing.get("currentStatus") == "DRAFT" and listing.get("aggregateVersion") == 1,
            f"CREATE_DRAFT invariant failed: {listing}")
    require(len(listing.get("offers") or []) == 1, f"Listing offer invariant failed: {listing}")
    listing_id = listing["listingId"]
    offer_id = listing["offers"][0]["listingOfferId"]
    transitions = (
        ("SUBMIT", "SUBMITTED"),
        ("PASS_COMPLETION", "COMPLETION_PASSED"),
        ("APPROVE_BUSINESS", "BUSINESS_APPROVED"),
        ("APPROVE_RISK", "RISK_APPROVED"),
        ("PUBLISH", "PUBLISHED"),
    )
    for offset, (operation, status) in enumerate(transitions, 1):
        index = start_index + offset
        payload = transition_payload(args.run_id, index, "listing", operation, "listingId",
                                     listing_id, offset,
                                     reason=f"deterministic {operation.lower()}")
        if operation == "PUBLISH":
            payload["publisherRef"] = os.getenv(
                "CLOUDMOLD_PUBLISHER_PRINCIPAL_ID", "agent:cloudmold-erp-operator"
            )
        listing = recorder.call("listing", LISTING_ROUTE, payload)
        require(listing.get("currentStatus") == status
                and listing.get("aggregateVersion") == offset + 1,
                f"{operation} invariant failed: {listing}")
    require(listing.get("completionPassed") is True
            and listing.get("businessApproved") is True
            and listing.get("riskApproved") is True,
            f"PUBLISHED Listing approvals invariant failed: {listing}")
    return listing, offer_id, start_index + len(transitions) + 1


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
        ("fulfillment", "CREATE", "CREATED/v1"),
        ("inventory", "SHIP", "8/0/8/v3"),
        ("fulfillment", "SHIP", "SHIPPED/v2"),
        ("order", "SHIP_WITH_FULFILLMENT", "SHIPPED/v4"),
        ("fulfillment", "MARK_IN_TRANSIT", "IN_TRANSIT/v3"),
        ("fulfillment", "DELIVER", "DELIVERED/v4"),
        ("order", "COMPLETE_AFTER_DELIVERY", "COMPLETED/v5"),
        ("payment", "REFUND", "REFUNDED/v2"),
        ("order", "CONFIRM_REFUND", "REFUNDED/v6"),
        ("inventory", "RETURN", "10/0/10/v4"),
        ("order", "RETURN", "RETURNED/v7"),
    )
    return [{"step": index, "domain": domain, "operation": operation, "expected": expected}
            for index, (domain, operation, expected) in enumerate(operations, 1)]


def write_ledger(args: argparse.Namespace, ledger: dict) -> Path:
    run_root = Path(os.environ.get("CLOUDMOLD_RUN_DIR", str(Path.home() / ".cloudmold" / "runs")))
    output = run_root / "listing-fulfillment" / args.run_id / "ledger.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        suffix = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = output.parent / f"replay-ledger-{suffix}.json"
    output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def authenticated_client(args: argparse.Namespace) -> Client:
    client = Client(args.base_url, args.tenant, os.getenv("CLOUDMOLD_ADMIN_TOKEN"), args.timeout)
    if not client.token:
        username = os.getenv("CLOUDMOLD_ADMIN_USERNAME")
        password = os.getenv("CLOUDMOLD_ADMIN_PASSWORD")
        if not username or not password:
            raise ScenarioError("set credentials through CLOUDMOLD_ADMIN_TOKEN or username/password environment variables")
        client.login(username, password)
    return client


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
    require(order.get("payableAmountMinor") == PAYABLE_MINOR and len(order.get("items") or []) == 1,
            f"PLACE_FROM_LISTING amount/item invariant failed: {order}")
    line = order["items"][0]
    require(line.get("listingId") == listing_id and line.get("listingOfferId") == offer_id
            and line.get("listingRevision") == 1 and line.get("listingVersion") == 6,
            f"Order did not preserve exact Listing snapshot: {line}")
    order_id, order_no, order_item_id = order["orderId"], order["orderNo"], line["orderItemId"]
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
        providerTransactionId=f"capture-{args.run_id}", reason="deterministic test capture"))
    require(payment.get("currentStatus") == "CAPTURED" and payment.get("aggregateVersion") == 1
            and payment.get("capturedAmountMinor") == PAYABLE_MINOR and payment.get("testMode") is True,
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
        args.run_id, index, order_id, order_item_id, sku_id, reservation_id, warehouse_id,
        args.owner_id))
    require(fulfillment.get("currentStatus") == "CREATED" and fulfillment.get("aggregateVersion") == 1,
            f"Fulfillment CREATE invariant failed: {fulfillment}")
    fulfillment_id = fulfillment["fulfillmentId"]
    index += 1

    shipped_inventory = recorder.call("inventory", INVENTORY_ROUTE, inventory_payload(
        args.run_id, index, "SHIP", sku_id, warehouse_id, args.owner_id, QUANTITY,
        "TRADE_ORDER", order_id, order_item_id, order_no, reservation_id))
    validate_inventory(shipped_inventory, ("8.000000", "0.000000", "8.000000", 3), "SHIP")
    index += 1

    fulfillment = recorder.call("fulfillment", FULFILLMENT_ROUTE, transition_payload(
        args.run_id, index, "fulfillment", "SHIP", "fulfillmentId", fulfillment_id, 1,
        carrierCode="INTERNAL_TEST", waybillNo=f"WB-{args.run_id}", reason="parcel handed to test carrier"))
    require(fulfillment.get("currentStatus") == "SHIPPED" and fulfillment.get("aggregateVersion") == 2
            and bool(fulfillment.get("shipmentId")), f"Fulfillment SHIP invariant failed: {fulfillment}")
    shipment_id = fulfillment["shipmentId"]
    index += 1

    order = recorder.call("order", ORDER_ROUTE, transition_payload(
        args.run_id, index, "order", "SHIP_WITH_FULFILLMENT", "orderId", order_id, 3,
        fulfillmentId=fulfillment_id, shipmentId=shipment_id,
        reason="validated canonical shipment"))
    require(order.get("currentStatus") == "SHIPPED" and order.get("aggregateVersion") == 4,
            f"Order SHIP_WITH_FULFILLMENT invariant failed: {order}")
    index += 1

    fulfillment = recorder.call("fulfillment", FULFILLMENT_ROUTE, transition_payload(
        args.run_id, index, "fulfillment", "MARK_IN_TRANSIT", "fulfillmentId", fulfillment_id, 2,
        carrierCode="INTERNAL_TEST", waybillNo=f"WB-{args.run_id}", reason="test parcel in transit"))
    require(fulfillment.get("currentStatus") == "IN_TRANSIT" and fulfillment.get("aggregateVersion") == 3,
            f"MARK_IN_TRANSIT invariant failed: {fulfillment}")
    index += 1

    fulfillment = recorder.call("fulfillment", FULFILLMENT_ROUTE, transition_payload(
        args.run_id, index, "fulfillment", "DELIVER", "fulfillmentId", fulfillment_id, 3,
        carrierCode="INTERNAL_TEST", waybillNo=f"WB-{args.run_id}", reason="test delivery confirmed"))
    require(fulfillment.get("currentStatus") == "DELIVERED" and fulfillment.get("aggregateVersion") == 4,
            f"DELIVER invariant failed: {fulfillment}")
    index += 1

    order = recorder.call("order", ORDER_ROUTE, transition_payload(
        args.run_id, index, "order", "COMPLETE_AFTER_DELIVERY", "orderId", order_id, 4,
        reason="delivered fulfillment validated"))
    require(order.get("currentStatus") == "COMPLETED" and order.get("aggregateVersion") == 5,
            f"COMPLETE_AFTER_DELIVERY invariant failed: {order}")
    index += 1

    refund_provider_id = f"refund-{args.run_id}"
    payment = recorder.call("payment", PAYMENT_ROUTE, payment_payload(
        args.run_id, index, "REFUND", paymentId=payment_id, expectedVersion=1,
        orderId=order_id, amountMinor=PAYABLE_MINOR, currencyCode="CNY",
        providerCode="INTERNAL_TEST", providerTransactionId=refund_provider_id,
        reason="deterministic full refund"))
    require(payment.get("currentStatus") == "REFUNDED" and payment.get("aggregateVersion") == 2
            and payment.get("capturedAmountMinor") == PAYABLE_MINOR
            and payment.get("refundedAmountMinor") == PAYABLE_MINOR,
            f"REFUND invariant failed: {payment}")
    index += 1

    order = recorder.call("order", ORDER_ROUTE, transition_payload(
        args.run_id, index, "order", "CONFIRM_REFUND", "orderId", order_id, 5,
        refundId=refund_provider_id, reason="full refund confirmed"))
    require(order.get("currentStatus") == "REFUNDED" and order.get("aggregateVersion") == 6,
            f"CONFIRM_REFUND invariant failed: {order}")
    index += 1

    returned_inventory = recorder.call("inventory", INVENTORY_ROUTE, inventory_payload(
        args.run_id, index, "RETURN", sku_id, warehouse_id, args.owner_id, QUANTITY,
        "TRADE_ORDER", order_id, order_item_id, order_no))
    validate_inventory(returned_inventory, ("10.000000", "0.000000", "10.000000", 4), "RETURN")
    index += 1

    order = recorder.call("order", ORDER_ROUTE, transition_payload(
        args.run_id, index, "order", "RETURN", "orderId", order_id, 6,
        reason="returned stock received"))
    require(order.get("currentStatus") == "RETURNED" and order.get("aggregateVersion") == 7,
            f"Order RETURN invariant failed: {order}")

    replay = recorder.replay_all()
    evidence_hook = {
        "run_id": args.run_id,
        "domains": ["listing", "inventory", "order", "payment", "fulfillment"],
        "aggregate_ids": {"listing_id": listing_id, "order_id": order_id, "payment_id": payment_id,
                          "fulfillment_id": fulfillment_id, "shipment_id": shipment_id},
        "expected_terminal": {"listing": "PUBLISHED/v6", "order": "RETURNED/v7",
                              "payment": "REFUNDED/v2", "fulfillment": "DELIVERED/v4",
                              "inventory": "10/0/10/v4"},
        "expected_business_commands": len(recorder.calls),
        "all_replay_duplicate": True,
    }
    ledger = {
        "scenario": "canonical-listing-fulfillment-first-slice-v1",
        "run_id": args.run_id,
        "environment": args.environment,
        "tenant": args.tenant,
        "canonical_sku_id": sku_id,
        "canonical_spu_id": spu_id,
        "catalog_ledger": catalog_ledger,
        "calls": recorder.redacted_calls(),
        "replay": replay,
        "lakehouse_evidence_hook": evidence_hook,
        "final": {"listing": listing, "order": order, "payment": payment,
                  "fulfillment": fulfillment, "inventory": returned_inventory,
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
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        require(bool(RUN_ID_PATTERN.fullmatch(args.run_id)),
                "run_id must be 6-32 characters using letters, digits, dot, underscore, or hyphen")
        require(args.environment in {"local", "demo", "test"},
                "the Listing/Fulfillment runner is restricted to local, demo, or test")
        sku_id, spu_id, catalog_ledger = load_catalog_identity(args)
        if args.mode == "plan":
            result = {"scenario": "canonical-listing-fulfillment-first-slice-v1",
                      "run_id": args.run_id, "canonical_sku_id": sku_id,
                      "canonical_spu_id": spu_id, "catalog_ledger": catalog_ledger,
                      "steps": scenario_plan(), "replay": "all 23 commands",
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
