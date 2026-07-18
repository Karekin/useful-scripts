#!/usr/bin/env python3
"""Shared deterministic primitives for the governed after-sales vertical."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Callable
import uuid

from canonical_inventory_runner import Client, ScenarioError, request_hash
from canonical_listing_fulfillment_runner import (
    PAYABLE_MINOR,
    PRICE_MINOR,
    QUANTITY,
    fulfillment_create_payload,
    inventory_payload,
    listing_create_payload,
    payment_payload,
    place_from_listing_payload,
    require,
    stable_result,
    transition_payload,
    validate_inventory,
)
from canonical_order_payment_runner import (
    GOVERNED_DISCOUNT_MINOR,
    governed_benefit_application,
    metadata,
    stacked_entitlement_applications,
    validate_benefit_result,
)


SCENARIO_NAME = "canonical-aftersales-return-refund-v1"
TERMINAL_FAILURE_STATES = {"MANUAL_REVIEW", "REJECTED", "CANCELLED"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_json(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_endpoint_manifest(path: str | Path) -> dict:
    manifest_path = Path(path).expanduser().resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"cannot read endpoint manifest {manifest_path}: {exc}") from exc
    require(manifest.get("schema_version") == 1,
            "endpoint manifest schema_version must be 1")
    endpoints = manifest.get("endpoints")
    require(isinstance(endpoints, dict), "endpoint manifest endpoints must be an object")
    required = {
        "listing_command": "post",
        "inventory_command": "post",
        "order_command": "post",
        "payment_command": "post",
        "promotion_command": "post",
        "fulfillment_command": "post",
        "aftersales_command": "post",
        "aftersales_query": "get",
        "aftersales_query_by_order_item": "get",
    }
    for name, method in required.items():
        endpoint = endpoints.get(name)
        require(isinstance(endpoint, dict), f"endpoint manifest is missing {name}")
        require(endpoint.get("method", "").lower() == method,
                f"endpoint {name} must use {method.upper()}")
        require(isinstance(endpoint.get("path"), str) and endpoint["path"].startswith("/"),
                f"endpoint {name} path must be absolute")
    operations = manifest.get("operations")
    require(isinstance(operations, dict), "endpoint manifest operations must be an object")
    for name in ("request", "approve", "hand_over_return", "mark_return_in_transit",
                 "receive_return", "accept_inspection", "retry_resolution"):
        require(isinstance(operations.get(name), str) and operations[name],
                f"endpoint manifest is missing operation {name}")
    return manifest


def route(manifest: dict, name: str) -> str:
    return manifest["endpoints"][name]["path"]


def endpoint_fingerprint(manifest: dict) -> str:
    return sha256_json(manifest)


def openapi_fingerprint(document: dict) -> str:
    paths = document.get("paths") or {}
    return sha256_json(paths)


def verify_openapi(document: dict, manifest: dict) -> list[str]:
    paths = document.get("paths") or {}
    missing: list[str] = []
    for endpoint in manifest["endpoints"].values():
        path = endpoint["path"]
        method = endpoint["method"].lower()
        if path not in paths or method not in paths[path]:
            missing.append(f"{method.upper()} {path}")
    return missing


def source_commit(workspace: str | Path) -> str:
    repository = Path(workspace).expanduser().resolve() / "yudao-cloud"
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True, capture_output=True)
    if completed.returncode != 0:
        raise ScenarioError(f"cannot resolve yudao-cloud source commit: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _atomic_replace(path: Path, payload: dict) -> None:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp.exists():
            temp.unlink()


class AtomicRunLedger:
    """Crash-safe run ledger created before the first write and checkpointed per step."""

    def __init__(self, path: Path, identity: dict):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ScenarioError(f"existing run ledger is unreadable: {exc}") from exc
            for field, expected in identity.items():
                require(self.data.get(field) == expected,
                        f"existing run ledger {field} conflicts with this execution")
        else:
            self.data = {
                **identity,
                "created_at": utc_now(),
                "status": "INITIALIZED",
                "attempts": [],
                "irreversible_boundary": None,
            }
            encoded = (json.dumps(self.data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        self.attempt = {
            "attempt_id": str(uuid.uuid4()),
            "started_at": utc_now(),
            "steps": [],
            "observations": [],
            "status": "RUNNING",
        }
        self.data["attempts"].append(self.attempt)
        self.data["status"] = "RUNNING"
        self.checkpoint()

    def checkpoint(self) -> None:
        self.data["updated_at"] = utc_now()
        _atomic_replace(self.path, self.data)

    def before_request(self, domain: str, route_path: str, payload: dict) -> dict:
        step = {
            "ordinal": len(self.attempt["steps"]) + 1,
            "domain": domain,
            "route": route_path,
            "operation": payload.get("operation"),
            "request_hash": request_hash(payload),
            "status": "REQUESTING",
            "started_at": utc_now(),
            "retry_count": 0,
        }
        self.attempt["steps"].append(step)
        self.checkpoint()
        return step

    def after_request(self, step: dict, result: dict) -> None:
        step["status"] = "SUCCEEDED"
        step["completed_at"] = utc_now()
        step["response"] = result
        self.checkpoint()

    def record_observation(self, domain: str, result: dict) -> None:
        self.attempt["observations"].append({
            "domain": domain,
            "observed_at": utc_now(),
            "result": result,
        })
        self.checkpoint()

    def mark_irreversible(self, aftersales_id: str, refund_transaction_id: int | None) -> None:
        self.data["irreversible_boundary"] = {
            "kind": "PAYMENT_REFUNDED",
            "aftersales_id": aftersales_id,
            "refund_transaction_id": refund_transaction_id,
            "observed_at": utc_now(),
            "cleanup_policy": "retain audit evidence; compensate or enter manual review; never delete",
        }
        self.checkpoint()

    def finish(self, status: str, final: dict | None = None, error: str | None = None) -> None:
        self.attempt["status"] = status
        self.attempt["completed_at"] = utc_now()
        if error:
            self.attempt["error"] = error
        self.data["status"] = status
        if final is not None:
            self.data["final"] = final
        self.checkpoint()


class CheckpointRecorder:
    def __init__(self, client: Client, ledger: AtomicRunLedger, manifest: dict):
        self.client = client
        self.ledger = ledger
        self.manifest = manifest
        self.calls: list[dict] = []

    def call(self, domain: str, endpoint_name: str, payload: dict,
             ambiguity_query: str | None = None) -> dict:
        path = route(self.manifest, endpoint_name)
        step = self.ledger.before_request(domain, path, payload)
        try:
            result = self.client.request("POST", path, payload)
        except Exception as exc:
            step["status"] = "AMBIGUOUS"
            step["error"] = str(exc)
            step["recovery"] = (
                "Do not retry blindly. Query by aggregate/idempotency key and current state, "
                "then resume with the same deterministic payload.")
            if ambiguity_query:
                step["ambiguity_query"] = ambiguity_query
                try:
                    recovered = self.client.request("GET", ambiguity_query)
                except Exception as query_exc:
                    step["ambiguity_query_error"] = str(query_exc)
                else:
                    exact_identity = (
                        recovered.get("afterSaleId")
                        and recovered.get("orderId") == payload.get("orderId")
                        and recovered.get("orderItemId") == payload.get("orderItemId"))
                    if exact_identity:
                        step["status"] = "RECOVERED_BY_READ"
                        step["completed_at"] = utc_now()
                        step["response"] = recovered
                        self.ledger.checkpoint()
                        self.calls.append({
                            "domain": domain,
                            "endpoint": endpoint_name,
                            "route": path,
                            "operation": payload["operation"],
                            "request_hash": request_hash(payload),
                            "payload": payload,
                            "result": recovered,
                            "recovered_by_read": True,
                        })
                        return recovered
                    step["ambiguity_query_error"] = (
                        "recovery query returned a case with missing or conflicting "
                        "orderId/orderItemId")
            self.ledger.checkpoint()
            raise
        self.ledger.after_request(step, result)
        self.calls.append({
            "domain": domain,
            "endpoint": endpoint_name,
            "route": path,
            "operation": payload["operation"],
            "request_hash": request_hash(payload),
            "payload": payload,
            "result": result,
        })
        return result

    def replay_all(self) -> list[dict]:
        replayed: list[dict] = []
        for original in self.calls:
            step = self.ledger.before_request(
                f"replay:{original['domain']}", original["route"], original["payload"])
            try:
                result = self.client.request("POST", original["route"], original["payload"])
            except Exception as exc:
                step["status"] = "AMBIGUOUS"
                step["error"] = str(exc)
                step["recovery"] = (
                    "Replay timed out. Query the immutable operation/current aggregate state; "
                    "do not alter the payload or create a replacement command.")
                self.ledger.checkpoint()
                raise
            require(result.get("duplicate") is True,
                    f"{original['domain']} {original['operation']} replay was not duplicate")
            replay_stable = stable_result(result)
            original_stable = stable_result(original["result"])
            if original.get("recovered_by_read"):
                replay_stable.pop("operationId", None)
                original_stable.pop("operationId", None)
            require(replay_stable == original_stable,
                    f"{original['domain']} {original['operation']} replay changed immutable result")
            self.ledger.after_request(step, result)
            evidence = {
                "domain": original["domain"],
                "operation": original["operation"],
                "request_hash": original["request_hash"],
                "result": result,
            }
            replayed.append(evidence)
            self.ledger.record_observation("replay", evidence)
        return replayed


def _stable_promotion_id(run_id: str, kind: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudmold:{run_id}:promotion:{kind}"))


def execute_entitlement_lifecycle(recorder: CheckpointRecorder, args) -> tuple[str, int]:
    campaign_id = _stable_promotion_id(args.run_id, "campaign")
    template_id = _stable_promotion_id(args.run_id, "template")
    entitlement_id = _stable_promotion_id(args.run_id, "entitlement")
    common = {"validFrom": "2025-01-01T00:00:00Z", "validTo": "2030-01-01T00:00:00Z"}
    commands = [
        {"operation": "CREATE_CAMPAIGN", **metadata(args.run_id, -8, "CREATE_CAMPAIGN"),
         "campaign": {"campaignId": campaign_id, "campaignCode": f"C-{args.run_id}",
                      "campaignKind": "COUPON", "name": f"Entitlement {args.run_id}",
                      "startsAt": common["validFrom"], "endsAt": common["validTo"]}},
        {"operation": "ACTIVATE_CAMPAIGN", **metadata(args.run_id, -7, "ACTIVATE_CAMPAIGN"),
         "campaign": {"campaignId": campaign_id, "expectedVersion": 1}},
        {"operation": "CREATE_COUPON_TEMPLATE", **metadata(args.run_id, -6, "CREATE_COUPON_TEMPLATE"),
         "couponTemplate": {"templateId": template_id, "templateCode": f"T-{args.run_id}",
                            "campaignId": campaign_id, "title": f"Returnable {args.run_id}",
                            "benefitType": "FIXED_AMOUNT", "faceAmountMinor": GOVERNED_DISCOUNT_MINOR,
                            "thresholdMinor": 0, "currencyCode": "CNY", "funderType": "SHARED",
                            "merchantId": args.owner_id, **common}},
        {"operation": "ACTIVATE_COUPON_TEMPLATE", **metadata(args.run_id, -5, "ACTIVATE_COUPON_TEMPLATE"),
         "couponTemplate": {"templateId": template_id, "expectedVersion": 1}},
        {"operation": "ISSUE_COUPON_ENTITLEMENT", **metadata(args.run_id, -4, "ISSUE_COUPON_ENTITLEMENT"),
         "couponEntitlement": {"entitlementId": entitlement_id,
                               "entitlementCode": f"E-{args.run_id}", "templateId": template_id,
                               "principalId": "controlled-buyer", "reason": "controlled full-return proof"}},
        {"operation": "COLLECT_COUPON_ENTITLEMENT", **metadata(args.run_id, -3, "COLLECT_COUPON_ENTITLEMENT"),
         "couponEntitlement": {"entitlementId": entitlement_id, "expectedVersion": 1}},
        {"operation": "RESERVE_COUPON_ENTITLEMENT", **metadata(args.run_id, -2, "RESERVE_COUPON_ENTITLEMENT"),
         "couponEntitlement": {"entitlementId": entitlement_id, "expectedVersion": 2,
                               "orderRef": args.run_id}},
        {"operation": "REDEEM_COUPON_ENTITLEMENT", **metadata(args.run_id, -1, "REDEEM_COUPON_ENTITLEMENT"),
         "couponEntitlement": {"entitlementId": entitlement_id, "expectedVersion": 3,
                               "orderRef": args.run_id}},
    ]
    expected = (("DRAFT", 1), ("ACTIVE", 2), ("DRAFT", 1), ("ACTIVE", 2),
                ("ISSUED", 1), ("AVAILABLE", 2), ("RESERVED", 3), ("USED", 4))
    for command, (status, version) in zip(commands, expected):
        result = recorder.call("promotion", "promotion_command", command)
        require(result.get("status") == status and result.get("aggregateVersion") == version,
                f"Promotion entitlement lifecycle invariant failed: {result}")
    return entitlement_id, 4


def execute_stacked_entitlement_lifecycle(recorder: CheckpointRecorder, args) -> tuple[list[str], int]:
    campaign_id = _stable_promotion_id(args.run_id, "campaign")
    definitions = (
        ("platform", 2000, "PLATFORM"),
        ("merchant", 1800, "MERCHANT"),
    )
    common = {"validFrom": "2025-01-01T00:00:00Z", "validTo": "2030-01-01T00:00:00Z"}
    commands = [
        {"operation": "CREATE_CAMPAIGN", **metadata(args.run_id, -14, "CREATE_CAMPAIGN"),
         "campaign": {"campaignId": campaign_id, "campaignCode": f"C-{args.run_id}",
                      "campaignKind": "COUPON", "name": f"Stacked entitlements {args.run_id}",
                      "startsAt": common["validFrom"], "endsAt": common["validTo"]}},
        {"operation": "ACTIVATE_CAMPAIGN", **metadata(args.run_id, -13, "ACTIVATE_CAMPAIGN"),
         "campaign": {"campaignId": campaign_id, "expectedVersion": 1}},
    ]
    entitlement_ids = []
    index = -12
    for label, amount, funder_type in definitions:
        template_id = _stable_promotion_id(args.run_id, f"template-{label}")
        entitlement_id = _stable_promotion_id(args.run_id, f"entitlement-{label}")
        entitlement_ids.append(entitlement_id)
        commands.extend([
            {"operation": "CREATE_COUPON_TEMPLATE",
             **metadata(args.run_id, index, f"CREATE_COUPON_TEMPLATE_{label.upper()}"),
             "couponTemplate": {"templateId": template_id,
                                "templateCode": f"T-{label[0].upper()}-{args.run_id}",
                                "campaignId": campaign_id, "title": f"{label.title()} {args.run_id}",
                                "benefitType": "FIXED_AMOUNT", "faceAmountMinor": amount,
                                "thresholdMinor": 0, "currencyCode": "CNY", "funderType": funder_type,
                                **({"merchantId": args.owner_id} if funder_type == "MERCHANT" else {}),
                                **common}},
            {"operation": "ACTIVATE_COUPON_TEMPLATE",
             **metadata(args.run_id, index + 1, f"ACTIVATE_COUPON_TEMPLATE_{label.upper()}"),
             "couponTemplate": {"templateId": template_id, "expectedVersion": 1}},
            {"operation": "ISSUE_COUPON_ENTITLEMENT",
             **metadata(args.run_id, index + 2, f"ISSUE_COUPON_ENTITLEMENT_{label.upper()}"),
             "couponEntitlement": {"entitlementId": entitlement_id,
                                   "entitlementCode": f"E-{label[0].upper()}-{args.run_id}",
                                   "templateId": template_id, "principalId": "controlled-buyer",
                                   "reason": "controlled stacked full-return proof"}},
            {"operation": "COLLECT_COUPON_ENTITLEMENT",
             **metadata(args.run_id, index + 3, f"COLLECT_COUPON_ENTITLEMENT_{label.upper()}"),
             "couponEntitlement": {"entitlementId": entitlement_id, "expectedVersion": 1}},
            {"operation": "RESERVE_COUPON_ENTITLEMENT",
             **metadata(args.run_id, index + 4, f"RESERVE_COUPON_ENTITLEMENT_{label.upper()}"),
             "couponEntitlement": {"entitlementId": entitlement_id, "expectedVersion": 2,
                                   "orderRef": args.run_id}},
            {"operation": "REDEEM_COUPON_ENTITLEMENT",
             **metadata(args.run_id, index + 5, f"REDEEM_COUPON_ENTITLEMENT_{label.upper()}"),
             "couponEntitlement": {"entitlementId": entitlement_id, "expectedVersion": 3,
                                   "orderRef": args.run_id}},
        ])
        index += 6
    expected = (("DRAFT", 1), ("ACTIVE", 2)) + tuple(
        value for _ in definitions for value in (
            ("DRAFT", 1), ("ACTIVE", 2), ("ISSUED", 1), ("AVAILABLE", 2),
            ("RESERVED", 3), ("USED", 4)))
    for command, (status, version) in zip(commands, expected):
        result = recorder.call("promotion", "promotion_command", command)
        require(result.get("status") == status and result.get("aggregateVersion") == version,
                f"stacked Promotion entitlement lifecycle invariant failed: {result}")
    return entitlement_ids, 4


def execute_forward_to_completed(recorder: CheckpointRecorder, args, manifest: dict,
                                 sku_id: str, spu_id: str) -> dict:
    """Reuse the governed Listing/Fulfillment semantics through Order COMPLETED/v5."""
    entitlement_id = None
    entitlement_version = None
    if args.benefit_mode == "entitlement-backed":
        entitlement_id, entitlement_version = execute_entitlement_lifecycle(recorder, args)
    elif args.benefit_mode == "stacked-entitlements":
        entitlement_id, entitlement_version = execute_stacked_entitlement_lifecycle(recorder, args)

    listing = getattr(args, "published_listing", None)
    if listing is not None:
        require(listing.get("currentStatus") == "PUBLISHED"
                and listing.get("aggregateVersion") == 6,
                f"master Listing invariant failed: {listing}")
        require(len(listing.get("offers") or []) == 1,
                f"master Listing offer invariant failed: {listing}")
    else:
        listing = recorder.call("listing", "listing_command", listing_create_payload(
            args.run_id, 1, sku_id, spu_id,
            getattr(args, "merchant_id", None),
            getattr(args, "shop_id", None),
            getattr(args, "publisher_principal_id", None),
        ))
        require(listing.get("currentStatus") == "DRAFT" and listing.get("aggregateVersion") == 1,
                f"CREATE_DRAFT invariant failed: {listing}")
        require(len(listing.get("offers") or []) == 1, f"Listing offer invariant failed: {listing}")
        listing_id = listing["listingId"]
        for index, (operation, expected_status) in enumerate((
            ("SUBMIT", "SUBMITTED"),
            ("PASS_COMPLETION", "COMPLETION_PASSED"),
            ("APPROVE_BUSINESS", "BUSINESS_APPROVED"),
            ("APPROVE_RISK", "RISK_APPROVED"),
            ("PUBLISH", "PUBLISHED"),
        ), 2):
            payload = transition_payload(
                args.run_id, index, "listing", operation, "listingId", listing_id, index - 1,
                reason=f"deterministic {operation.lower()}")
            if operation == "PUBLISH":
                payload["publisherRef"] = getattr(
                    args, "publisher_principal_id", None
                ) or os.getenv("CLOUDMOLD_PUBLISHER_PRINCIPAL_ID", "agent:cloudmold-erp-operator")
            listing = recorder.call("listing", "listing_command", payload)
            require(listing.get("currentStatus") == expected_status
                    and listing.get("aggregateVersion") == index,
                    f"{operation} invariant failed: {listing}")

    listing_id = listing["listingId"]
    offer_id = listing["offers"][0]["listingOfferId"]
    require(listing["offers"][0].get("canonicalSkuId") == sku_id,
            "published Listing offer does not belong to the selected canonical SKU")

    warehouse_id = args.warehouse_id or f"scenario:{args.run_id}"
    receive = recorder.call("inventory", "inventory_command", inventory_payload(
        args.run_id, 7, "RECEIVE", sku_id, warehouse_id, args.owner_id, "10.000000",
        "TEST_FIXTURE", args.run_id, "fixture-line", f"FIXTURE-{args.run_id}"))
    validate_inventory(receive, ("10.000000", "0.000000", "10.000000", 1), "RECEIVE")

    place = place_from_listing_payload(args.run_id, 8, sku_id, listing_id, offer_id)
    if args.benefit_mode != "none":
        place["items"][0]["lineKey"] = "line-1"
        place["discountAmountMinor"] = GOVERNED_DISCOUNT_MINOR
        place["benefitApplications"] = (stacked_entitlement_applications(
            args.run_id, entitlement_id, entitlement_version, args.owner_id)
            if args.benefit_mode == "stacked-entitlements"
            else [governed_benefit_application(
                args.run_id, entitlement_id, entitlement_version, args.owner_id)])
    expected_payable = PAYABLE_MINOR - (
        GOVERNED_DISCOUNT_MINOR if args.benefit_mode != "none" else 0)
    order = recorder.call("order", "order_command", place)
    require(order.get("currentStatus") == "PLACED" and order.get("aggregateVersion") == 1,
            f"PLACE_FROM_LISTING invariant failed: {order}")
    require(order.get("payableAmountMinor") == expected_payable
            and len(order.get("items") or []) == 1,
            f"PLACE_FROM_LISTING amount/item invariant failed: {order}")
    validate_benefit_result(order, args.benefit_mode)
    line = order["items"][0]
    require(line.get("listingId") == listing_id and line.get("listingOfferId") == offer_id,
            f"Order did not preserve exact Listing identity: {line}")
    order_id, order_no, order_item_id = order["orderId"], order["orderNo"], line["orderItemId"]

    reserve = recorder.call("inventory", "inventory_command", inventory_payload(
        args.run_id, 9, "RESERVE", sku_id, warehouse_id, args.owner_id, QUANTITY,
        "TRADE_ORDER", order_id, order_item_id, order_no))
    validate_inventory(reserve, ("10.000000", "2.000000", "8.000000", 2), "RESERVE")
    reservation_id = reserve["reservationId"]

    order = recorder.call("order", "order_command", transition_payload(
        args.run_id, 10, "order", "CONFIRM_INVENTORY", "orderId", order_id, 1,
        reservationReferences=[{"orderItemId": order_item_id, "reservationId": reservation_id}],
        reason="all Listing order lines reserved"))
    require(order.get("currentStatus") == "INVENTORY_RESERVED"
            and order.get("aggregateVersion") == 2,
            f"CONFIRM_INVENTORY invariant failed: {order}")

    payment = recorder.call("payment", "payment_command", payment_payload(
        args.run_id, 11, "CAPTURE", orderId=order_id, amountMinor=expected_payable,
        currencyCode="CNY", providerCode="INTERNAL_TEST",
        providerTransactionId=f"capture-{args.run_id}", reason="deterministic test capture"))
    require(payment.get("currentStatus") == "CAPTURED" and payment.get("aggregateVersion") == 1
            and payment.get("capturedAmountMinor") == expected_payable
            and payment.get("testMode") is True,
            f"CAPTURE invariant failed: {payment}")
    payment_id = payment["paymentId"]

    order = recorder.call("order", "order_command", transition_payload(
        args.run_id, 12, "order", "CONFIRM_PAYMENT", "orderId", order_id, 2,
        paymentId=payment_id, reason="exact test payment captured"))
    require(order.get("currentStatus") == "PAYMENT_CONFIRMED"
            and order.get("aggregateVersion") == 3,
            f"CONFIRM_PAYMENT invariant failed: {order}")

    fulfillment = recorder.call("fulfillment", "fulfillment_command", fulfillment_create_payload(
        args.run_id, 13, order_id, order_item_id, sku_id, reservation_id, warehouse_id,
        args.owner_id))
    require(fulfillment.get("currentStatus") == "CREATED"
            and fulfillment.get("aggregateVersion") == 1,
            f"Fulfillment CREATE invariant failed: {fulfillment}")
    fulfillment_id = fulfillment["fulfillmentId"]

    inventory = recorder.call("inventory", "inventory_command", inventory_payload(
        args.run_id, 14, "SHIP", sku_id, warehouse_id, args.owner_id, QUANTITY,
        "TRADE_ORDER", order_id, order_item_id, order_no, reservation_id))
    validate_inventory(inventory, ("8.000000", "0.000000", "8.000000", 3), "SHIP")

    fulfillment = recorder.call("fulfillment", "fulfillment_command", transition_payload(
        args.run_id, 15, "fulfillment", "SHIP", "fulfillmentId", fulfillment_id, 1,
        carrierCode="INTERNAL_TEST", waybillNo=f"WB-{args.run_id}",
        reason="parcel handed to test carrier"))
    require(fulfillment.get("currentStatus") == "SHIPPED"
            and fulfillment.get("aggregateVersion") == 2
            and bool(fulfillment.get("shipmentId")),
            f"Fulfillment SHIP invariant failed: {fulfillment}")
    shipment_id = fulfillment["shipmentId"]

    order = recorder.call("order", "order_command", transition_payload(
        args.run_id, 16, "order", "SHIP_WITH_FULFILLMENT", "orderId", order_id, 3,
        fulfillmentId=fulfillment_id, shipmentId=shipment_id,
        reason="validated canonical shipment"))
    require(order.get("currentStatus") == "SHIPPED" and order.get("aggregateVersion") == 4,
            f"SHIP_WITH_FULFILLMENT invariant failed: {order}")

    fulfillment = recorder.call("fulfillment", "fulfillment_command", transition_payload(
        args.run_id, 17, "fulfillment", "MARK_IN_TRANSIT", "fulfillmentId", fulfillment_id, 2,
        carrierCode="INTERNAL_TEST", waybillNo=f"WB-{args.run_id}",
        reason="test parcel in transit"))
    require(fulfillment.get("currentStatus") == "IN_TRANSIT"
            and fulfillment.get("aggregateVersion") == 3,
            f"MARK_IN_TRANSIT invariant failed: {fulfillment}")

    fulfillment = recorder.call("fulfillment", "fulfillment_command", transition_payload(
        args.run_id, 18, "fulfillment", "DELIVER", "fulfillmentId", fulfillment_id, 3,
        carrierCode="INTERNAL_TEST", waybillNo=f"WB-{args.run_id}",
        reason="test delivery confirmed"))
    require(fulfillment.get("currentStatus") == "DELIVERED"
            and fulfillment.get("aggregateVersion") == 4,
            f"DELIVER invariant failed: {fulfillment}")

    order = recorder.call("order", "order_command", transition_payload(
        args.run_id, 19, "order", "COMPLETE_AFTER_DELIVERY", "orderId", order_id, 4,
        reason="delivered fulfillment validated"))
    require(order.get("currentStatus") == "COMPLETED" and order.get("aggregateVersion") == 5,
            f"COMPLETE_AFTER_DELIVERY invariant failed: {order}")
    return {
        "listing": listing,
        "listing_id": listing_id,
        "listing_offer_id": offer_id,
        "order": order,
        "order_id": order_id,
        "order_no": order_no,
        "order_item_id": order_item_id,
        "payment": payment,
        "payment_id": payment_id,
        "fulfillment": fulfillment,
        "fulfillment_id": fulfillment_id,
        "shipment_id": shipment_id,
        "inventory": inventory,
        "reservation_id": reservation_id,
        "warehouse_id": warehouse_id,
        "canonical_sku_id": sku_id,
        "canonical_spu_id": spu_id,
    }


def execute_multi_line_forward_to_completed(recorder: CheckpointRecorder, args,
                                            sku_ids: list[str], spu_id: str) -> dict:
    """Create one governed two-line order whose lines can settle independently."""
    require(args.benefit_mode == "none",
            "multi-line return proof currently isolates line settlement and forbids benefits")
    require(len(sku_ids) == 2 and len(set(sku_ids)) == 2,
            "multi-line return proof requires two distinct canonical SKUs")

    create = listing_create_payload(
        args.run_id, 1, sku_ids[0], spu_id,
        getattr(args, "merchant_id", None),
        getattr(args, "shop_id", None),
        getattr(args, "publisher_principal_id", None),
    )
    create["offers"] = [
        {
            "canonicalSkuId": sku_id,
            "priceMinor": PRICE_MINOR,
            "currencyCode": "CNY",
            "enabled": True,
            "externalOfferId": f"internal-offer:{args.run_id}:{ordinal}",
        }
        for ordinal, sku_id in enumerate(sku_ids, 1)
    ]
    listing = recorder.call("listing", "listing_command", create)
    require(listing.get("currentStatus") == "DRAFT" and listing.get("aggregateVersion") == 1,
            f"multi-line CREATE_DRAFT invariant failed: {listing}")
    require(len(listing.get("offers") or []) == 2,
            f"multi-line Listing must expose two offers: {listing}")
    listing_id = listing["listingId"]
    for index, (operation, expected_status) in enumerate((
        ("SUBMIT", "SUBMITTED"),
        ("PASS_COMPLETION", "COMPLETION_PASSED"),
        ("APPROVE_BUSINESS", "BUSINESS_APPROVED"),
        ("APPROVE_RISK", "RISK_APPROVED"),
        ("PUBLISH", "PUBLISHED"),
    ), 2):
        payload = transition_payload(
            args.run_id, index, "listing", operation, "listingId", listing_id, index - 1,
            reason=f"deterministic multi-line {operation.lower()}")
        if operation == "PUBLISH":
            payload["publisherRef"] = getattr(
                args, "publisher_principal_id", None
            ) or os.getenv("CLOUDMOLD_PUBLISHER_PRINCIPAL_ID", "agent:cloudmold-erp-operator")
        listing = recorder.call("listing", "listing_command", payload)
        require(listing.get("currentStatus") == expected_status
                and listing.get("aggregateVersion") == index,
                f"multi-line {operation} invariant failed: {listing}")

    warehouse_id = args.warehouse_id or f"scenario:{args.run_id}"
    for offset, sku_id in enumerate(sku_ids):
        received = recorder.call("inventory", "inventory_command", inventory_payload(
            args.run_id, 7 + offset, "RECEIVE", sku_id, warehouse_id, args.owner_id,
            "10.000000", "TEST_FIXTURE", args.run_id, f"fixture-line-{offset + 1}",
            f"FIXTURE-{args.run_id}-{offset + 1}"))
        validate_inventory(received, ("10.000000", "0.000000", "10.000000", 1),
                           f"RECEIVE_LINE_{offset + 1}")

    offer_by_sku = {value["canonicalSkuId"]: value["listingOfferId"]
                    for value in listing["offers"]}
    place = place_from_listing_payload(
        args.run_id, 9, sku_ids[0], listing_id, offer_by_sku[sku_ids[0]])
    place["items"] = [
        {
            "canonicalSkuId": sku_id,
            "quantity": "1.000000",
            "unitPriceMinor": PRICE_MINOR,
            "listingId": listing_id,
            "listingOfferId": offer_by_sku[sku_id],
        }
        for sku_id in sku_ids
    ]
    order = recorder.call("order", "order_command", place)
    require(order.get("currentStatus") == "PLACED" and order.get("aggregateVersion") == 1
            and order.get("payableAmountMinor") == PAYABLE_MINOR
            and len(order.get("items") or []) == 2,
            f"multi-line PLACE_FROM_LISTING invariant failed: {order}")
    lines_by_sku = {value["canonicalSkuId"]: value for value in order["items"]}
    require(set(lines_by_sku) == set(sku_ids)
            and all(value.get("listingId") == listing_id
                    and value.get("listingOfferId") == offer_by_sku[value["canonicalSkuId"]]
                    for value in order["items"]),
            f"multi-line Order did not preserve exact Listing identities: {order['items']}")
    order_id, order_no = order["orderId"], order["orderNo"]

    reservations: dict[str, str] = {}
    for offset, sku_id in enumerate(sku_ids):
        order_item_id = lines_by_sku[sku_id]["orderItemId"]
        reserved = recorder.call("inventory", "inventory_command", inventory_payload(
            args.run_id, 10 + offset, "RESERVE", sku_id, warehouse_id, args.owner_id,
            "1.000000", "TRADE_ORDER", order_id, order_item_id, order_no))
        validate_inventory(reserved, ("10.000000", "1.000000", "9.000000", 2),
                           f"RESERVE_LINE_{offset + 1}")
        reservations[sku_id] = reserved["reservationId"]

    order = recorder.call("order", "order_command", transition_payload(
        args.run_id, 12, "order", "CONFIRM_INVENTORY", "orderId", order_id, 1,
        reservationReferences=[
            {"orderItemId": lines_by_sku[sku_id]["orderItemId"],
             "reservationId": reservations[sku_id]}
            for sku_id in sku_ids
        ], reason="all two Listing order lines reserved"))
    require(order.get("currentStatus") == "INVENTORY_RESERVED"
            and order.get("aggregateVersion") == 2,
            f"multi-line CONFIRM_INVENTORY invariant failed: {order}")

    payment = recorder.call("payment", "payment_command", payment_payload(
        args.run_id, 13, "CAPTURE", orderId=order_id, amountMinor=PAYABLE_MINOR,
        currencyCode="CNY", providerCode="INTERNAL_TEST",
        providerTransactionId=f"capture-{args.run_id}", reason="two-line test capture"))
    require(payment.get("currentStatus") == "CAPTURED" and payment.get("aggregateVersion") == 1
            and payment.get("capturedAmountMinor") == PAYABLE_MINOR,
            f"multi-line CAPTURE invariant failed: {payment}")
    payment_id = payment["paymentId"]

    order = recorder.call("order", "order_command", transition_payload(
        args.run_id, 14, "order", "CONFIRM_PAYMENT", "orderId", order_id, 2,
        paymentId=payment_id, reason="exact two-line payment captured"))
    require(order.get("currentStatus") == "PAYMENT_CONFIRMED"
            and order.get("aggregateVersion") == 3,
            f"multi-line CONFIRM_PAYMENT invariant failed: {order}")

    fulfillment_payload = fulfillment_create_payload(
        args.run_id, 15, order_id, lines_by_sku[sku_ids[0]]["orderItemId"], sku_ids[0],
        reservations[sku_ids[0]], warehouse_id, args.owner_id)
    fulfillment_payload["items"] = [
        {
            "orderItemId": lines_by_sku[sku_id]["orderItemId"],
            "canonicalSkuId": sku_id,
            "quantity": "1.000000",
            "reservationId": reservations[sku_id],
        }
        for sku_id in sku_ids
    ]
    fulfillment = recorder.call("fulfillment", "fulfillment_command", fulfillment_payload)
    require(fulfillment.get("currentStatus") == "CREATED"
            and fulfillment.get("aggregateVersion") == 1,
            f"multi-line Fulfillment CREATE invariant failed: {fulfillment}")
    fulfillment_id = fulfillment["fulfillmentId"]

    inventories = []
    for offset, sku_id in enumerate(sku_ids):
        order_item_id = lines_by_sku[sku_id]["orderItemId"]
        shipped = recorder.call("inventory", "inventory_command", inventory_payload(
            args.run_id, 16 + offset, "SHIP", sku_id, warehouse_id, args.owner_id,
            "1.000000", "TRADE_ORDER", order_id, order_item_id, order_no,
            reservations[sku_id]))
        validate_inventory(shipped, ("9.000000", "0.000000", "9.000000", 3),
                           f"SHIP_LINE_{offset + 1}")
        inventories.append(shipped)

    fulfillment = recorder.call("fulfillment", "fulfillment_command", transition_payload(
        args.run_id, 18, "fulfillment", "SHIP", "fulfillmentId", fulfillment_id, 1,
        carrierCode="INTERNAL_TEST", waybillNo=f"WB-{args.run_id}",
        reason="two-line parcel handed to test carrier"))
    require(fulfillment.get("currentStatus") == "SHIPPED"
            and fulfillment.get("aggregateVersion") == 2
            and bool(fulfillment.get("shipmentId")),
            f"multi-line Fulfillment SHIP invariant failed: {fulfillment}")
    shipment_id = fulfillment["shipmentId"]

    order = recorder.call("order", "order_command", transition_payload(
        args.run_id, 19, "order", "SHIP_WITH_FULFILLMENT", "orderId", order_id, 3,
        fulfillmentId=fulfillment_id, shipmentId=shipment_id,
        reason="validated two-line canonical shipment"))
    require(order.get("currentStatus") == "SHIPPED" and order.get("aggregateVersion") == 4,
            f"multi-line Order SHIP invariant failed: {order}")
    fulfillment = recorder.call("fulfillment", "fulfillment_command", transition_payload(
        args.run_id, 20, "fulfillment", "MARK_IN_TRANSIT", "fulfillmentId", fulfillment_id, 2,
        carrierCode="INTERNAL_TEST", waybillNo=f"WB-{args.run_id}",
        reason="two-line parcel in transit"))
    require(fulfillment.get("currentStatus") == "IN_TRANSIT"
            and fulfillment.get("aggregateVersion") == 3,
            f"multi-line MARK_IN_TRANSIT invariant failed: {fulfillment}")
    fulfillment = recorder.call("fulfillment", "fulfillment_command", transition_payload(
        args.run_id, 21, "fulfillment", "DELIVER", "fulfillmentId", fulfillment_id, 3,
        carrierCode="INTERNAL_TEST", waybillNo=f"WB-{args.run_id}",
        reason="two-line delivery confirmed"))
    require(fulfillment.get("currentStatus") == "DELIVERED"
            and fulfillment.get("aggregateVersion") == 4,
            f"multi-line DELIVER invariant failed: {fulfillment}")
    order = recorder.call("order", "order_command", transition_payload(
        args.run_id, 22, "order", "COMPLETE_AFTER_DELIVERY", "orderId", order_id, 4,
        reason="two-line delivered fulfillment validated"))
    require(order.get("currentStatus") == "COMPLETED" and order.get("aggregateVersion") == 5,
            f"multi-line COMPLETE invariant failed: {order}")
    order_item_ids = [lines_by_sku[sku_id]["orderItemId"] for sku_id in sku_ids]
    return {
        "listing": listing, "listing_id": listing_id, "order": order,
        "order_id": order_id, "order_no": order_no, "order_item_id": order_item_ids[0],
        "order_item_ids": order_item_ids, "payment": payment, "payment_id": payment_id,
        "fulfillment": fulfillment, "fulfillment_id": fulfillment_id,
        "shipment_id": shipment_id, "inventory": inventories,
        "reservation_ids": [reservations[sku_id] for sku_id in sku_ids],
        "warehouse_id": warehouse_id, "canonical_sku_id": sku_ids[0],
        "canonical_sku_ids": sku_ids, "canonical_spu_id": spu_id,
    }


def poll_aftersales(client: Client, ledger: AtomicRunLedger, manifest: dict,
                    aftersales_id: str, timeout: float, interval: float,
                    sleep: Callable[[float], None], monotonic: Callable[[], float]) -> tuple[dict, list[dict]]:
    deadline = monotonic() + timeout
    observations: list[dict] = []
    query_path = route(manifest, "aftersales_query")
    query_parameter = manifest["endpoints"]["aftersales_query"].get("id_parameter", "afterSaleId")
    while True:
        current = client.request("GET", f"{query_path}?{query_parameter}={aftersales_id}")
        observation = {
            "status": current.get("caseStatus") or current.get("currentStatus") or current.get("status"),
            "active_step": current.get("activeResolutionStep") or current.get("activeStep"),
            "attempt_count": current.get("attemptCount"),
            "aggregate_version": current.get("aggregateVersion"),
            "last_error_code": current.get("lastErrorCode"),
        }
        observations.append(observation)
        ledger.record_observation("aftersales_poll", observation)
        status = observation["status"]
        if status == manifest.get("terminal", {}).get("case_status", "COMPLETED"):
            return current, observations
        if status in TERMINAL_FAILURE_STATES:
            raise ScenarioError(
                f"after-sales resolution stopped at {status}: {current.get('lastErrorCode')}; "
                "automatic execution is stopped. RETRY_RESOLUTION requires prior human evidence "
                "review and explicit authorization with retained case/Saga versions")
        if monotonic() >= deadline:
            raise ScenarioError(
                "after-sales resolution polling timed out; only read-only reconciliation is allowed "
                f"after timeout (status={status}, step={observation['active_step']})")
        sleep(interval)
