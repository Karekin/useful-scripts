#!/usr/bin/env python3
"""Build one deterministic, approval-ready input for the durable R3 Skill Task."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

from canonical_aftersales_runner import aftersales_payload
from canonical_catalog_runner import build_payloads as build_catalog_payloads, scenario_identity
from canonical_listing_fulfillment_runner import (
    fulfillment_create_payload,
    inventory_payload,
    listing_create_payload,
    payment_payload,
    place_from_listing_payload,
    transition_payload,
)
from canonical_merchant_warehouse_runner import base_command, merchant_command, scenario_context


RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,19}$")
PLACEHOLDER_ID = "00000000-0000-0000-0000-000000000000"
QUANTITY = "2.000000"


def build_catalog(run_id: str) -> dict:
    definitions = build_catalog_payloads(run_id)
    namespace = hashlib.sha256(run_id.encode()).hexdigest()[:8].upper()
    for definition in definitions:
        definition["colorCode"] = f"{definition['colorCode']}_{namespace}"
        definition["sizeGroupCode"] = f"{definition['sizeGroupCode']}_{namespace}"
    correlation_id = definitions[0]["correlationId"]
    occurred_at = scenario_identity(run_id)[2]
    specs = [
        ("STYLE", "ACTIVATE", 1),
        ("SPU", "SUBMIT", 1),
        ("SPU", "APPROVE", 2),
        ("SIZE_GROUP", "ACTIVATE", 1),
        *(("SIZE", "ACTIVATE", 1) for _ in range(3)),
        *(("COLOR", "ACTIVATE", 1) for _ in range(2)),
        *(("SKU", "ACTIVATE", 1) for _ in range(6)),
        ("SPU", "ACTIVATE", 3),
    ]
    lifecycle = []
    for index, (entity_type, action, expected_version) in enumerate(specs, 1):
        lifecycle.append({
            "entityType": entity_type,
            "entityId": PLACEHOLDER_ID,
            "action": action,
            "expectedVersion": expected_version,
            "idempotencyKey": f"{run_id}-lifecycle-{index}-{entity_type.lower()}-{action.lower()}",
            "reason": f"durable-r3-full-chain:{run_id}",
            "correlationId": correlation_id,
            "occurredAt": (occurred_at + dt.timedelta(seconds=100 + index))
                .isoformat().replace("+00:00", "Z"),
        })
    return {"definitions": definitions, "lifecycle": lifecycle}


def build_master(run_id: str, system_admin_source_id: str,
                 erp_warehouse_source_id: str, eligibility_at: str) -> dict:
    correlation_id, occurred_at = scenario_context(run_id)
    digest = hashlib.sha256(run_id.encode()).hexdigest()
    commands = [
        merchant_command(
            "CREATE_ONBOARDING_DRAFT", run_id, 1, correlation_id, occurred_at,
            legalName=f"Y-Shopping durable fixture {run_id}",
            registrationHashToken="sha256:" + digest,
            businessLicenseToken="token:" + run_id,
            ownerPrincipalId=PLACEHOLDER_ID,
            channelCode="YSHOPPING_INTERNAL",
            externalShopId=f"YS-{run_id}",
        ),
        merchant_command("SUBMIT_ONBOARDING", run_id, 2, correlation_id, occurred_at,
                         applicationId=PLACEHOLDER_ID, expectedVersion=1),
        merchant_command("START_ONBOARDING_REVIEW", run_id, 3, correlation_id, occurred_at,
                         applicationId=PLACEHOLDER_ID, expectedVersion=2),
        merchant_command("APPROVE_ONBOARDING", run_id, 4, correlation_id, occurred_at,
                         applicationId=PLACEHOLDER_ID, expectedVersion=3),
        merchant_command("ACTIVATE_MERCHANT", run_id, 5, correlation_id, occurred_at,
                         merchantId=PLACEHOLDER_ID, expectedVersion=1),
        merchant_command("ACTIVATE_SHOP", run_id, 6, correlation_id, occurred_at,
                         shopId=PLACEHOLDER_ID, expectedVersion=1),
    ]
    warehouse_commands = [
        {
            **base_command("DEFINE_WAREHOUSE", run_id, 1, correlation_id, occurred_at),
            "warehouse": {
                "warehouseCode": "CM-" + digest[:12].upper(),
                "name": f"Y-Shopping durable warehouse {run_id}",
                "warehouseType": "FULFILLMENT",
                "timezone": "Asia/Shanghai",
            },
        },
        {
            **base_command("CHANGE_WAREHOUSE_STATUS", run_id, 2, correlation_id, occurred_at),
            "warehouse": {
                "warehouseId": PLACEHOLDER_ID,
                "status": "ACTIVE",
                "expectedVersion": 1,
            },
        },
        {
            **base_command("DEFINE_ZONE", run_id, 3, correlation_id, occurred_at),
            "zone": {
                "warehouseId": PLACEHOLDER_ID,
                "zoneCode": "PICK-01",
                "name": "Pick zone 01",
                "zoneType": "PICKING",
            },
        },
        {
            **base_command("CHANGE_ZONE_STATUS", run_id, 4, correlation_id, occurred_at),
            "zone": {
                "zoneId": PLACEHOLDER_ID,
                "status": "ACTIVE",
                "expectedVersion": 1,
            },
        },
        {
            **base_command("DEFINE_LOCATION", run_id, 5, correlation_id, occurred_at),
            "location": {
                "warehouseId": PLACEHOLDER_ID,
                "zoneId": PLACEHOLDER_ID,
                "locationCode": "A01-R01-B01-L01",
                "name": "A01 R01 B01 L01",
                "locationType": "PICK_FACE",
                "aisleCode": "A01",
                "rackCode": "R01",
                "bayCode": "B01",
                "levelCode": "L01",
                "allowItemMixing": False,
                "allowLotMixing": False,
                "capacityQuantity": "1000",
                "capacityUomCode": "PCS",
            },
        },
        {
            **base_command("CHANGE_LOCATION_STATUS", run_id, 6, correlation_id, occurred_at),
            "location": {
                "locationId": PLACEHOLDER_ID,
                "status": "ACTIVE",
                "expectedVersion": 1,
            },
        },
        {
            **base_command("LINK_SOURCE", run_id, 7, correlation_id, occurred_at),
            "sourceMapping": {
                "sourceSystem": "ERP",
                "sourceType": "WAREHOUSE",
                "sourceId": erp_warehouse_source_id,
                "targetType": "WAREHOUSE",
                "warehouseId": PLACEHOLDER_ID,
                "validFrom": occurred_at.isoformat().replace("+00:00", "Z"),
                "verificationRef":
                    f"erp_warehouse:{erp_warehouse_source_id}:skill-task:{run_id}",
            },
        },
    ]
    return {
        "erpWarehouseSourceId": erp_warehouse_source_id,
        "identityReference": {
            "sourceSystem": "SYSTEM",
            "sourceType": "SYSTEM_ADMIN_USER",
            "sourceId": system_admin_source_id,
        },
        "merchantCommands": commands,
        "warehouseCommands": warehouse_commands,
        "warehouseReference": {
            "sourceSystem": "ERP",
            "sourceType": "WAREHOUSE",
            "sourceId": erp_warehouse_source_id,
        },
        "eligibilityAt": eligibility_at,
    }


def build_aftersale(run_id: str, address_ref: str) -> dict:
    listing = listing_create_payload(
        run_id, 1, PLACEHOLDER_ID, PLACEHOLDER_ID,
        PLACEHOLDER_ID, PLACEHOLDER_ID, PLACEHOLDER_ID)
    commands = [listing]
    for index, operation in enumerate((
        "SUBMIT", "PASS_COMPLETION", "APPROVE_BUSINESS", "APPROVE_RISK", "PUBLISH"
    ), 2):
        command = transition_payload(
            run_id, index, "listing", operation, "listingId", PLACEHOLDER_ID, index - 1,
            reason=f"durable R3 {operation.lower()}")
        if operation == "PUBLISH":
            command["publisherRef"] = PLACEHOLDER_ID
        commands.append(command)
    commands.extend([
        inventory_payload(run_id, 7, "RECEIVE", PLACEHOLDER_ID, PLACEHOLDER_ID,
                          PLACEHOLDER_ID, "10.000000", "TEST_FIXTURE", run_id,
                          "fixture-line", f"FIXTURE-{run_id}"),
        place_from_listing_payload(
            run_id, 8, PLACEHOLDER_ID, PLACEHOLDER_ID, PLACEHOLDER_ID, address_ref),
        inventory_payload(run_id, 9, "RESERVE", PLACEHOLDER_ID, PLACEHOLDER_ID,
                          PLACEHOLDER_ID, QUANTITY, "TRADE_ORDER", PLACEHOLDER_ID,
                          PLACEHOLDER_ID, f"ORDER-{run_id}"),
        transition_payload(
            run_id, 10, "order", "CONFIRM_INVENTORY", "orderId", PLACEHOLDER_ID, 1,
            reservationReferences=[{
                "orderItemId": PLACEHOLDER_ID,
                "reservationId": PLACEHOLDER_ID,
            }], reason="all Listing order lines reserved"),
        payment_payload(
            run_id, 11, "CAPTURE", orderId=PLACEHOLDER_ID, amountMinor=39800,
            currencyCode="CNY", providerCode="INTERNAL_TEST",
            providerTransactionId=f"capture-{run_id}", reason="deterministic test capture"),
        transition_payload(
            run_id, 12, "order", "CONFIRM_PAYMENT", "orderId", PLACEHOLDER_ID, 2,
            paymentId=PLACEHOLDER_ID, reason="exact test payment captured"),
        fulfillment_create_payload(
            run_id, 13, PLACEHOLDER_ID, PLACEHOLDER_ID, PLACEHOLDER_ID,
            PLACEHOLDER_ID, PLACEHOLDER_ID, PLACEHOLDER_ID),
        inventory_payload(run_id, 14, "SHIP", PLACEHOLDER_ID, PLACEHOLDER_ID,
                          PLACEHOLDER_ID, QUANTITY, "TRADE_ORDER", PLACEHOLDER_ID,
                          PLACEHOLDER_ID, f"ORDER-{run_id}", PLACEHOLDER_ID),
        transition_payload(
            run_id, 15, "fulfillment", "SHIP", "fulfillmentId", PLACEHOLDER_ID, 1,
            carrierCode="INTERNAL_TEST", waybillNo=f"WB-{run_id}",
            reason="parcel handed to test carrier"),
        transition_payload(
            run_id, 16, "order", "SHIP_WITH_FULFILLMENT", "orderId", PLACEHOLDER_ID, 3,
            fulfillmentId=PLACEHOLDER_ID, shipmentId=PLACEHOLDER_ID,
            reason="validated canonical shipment"),
        transition_payload(
            run_id, 17, "fulfillment", "MARK_IN_TRANSIT", "fulfillmentId", PLACEHOLDER_ID, 2,
            carrierCode="INTERNAL_TEST", waybillNo=f"WB-{run_id}", reason="test parcel in transit"),
        transition_payload(
            run_id, 18, "fulfillment", "DELIVER", "fulfillmentId", PLACEHOLDER_ID, 3,
            carrierCode="INTERNAL_TEST", waybillNo=f"WB-{run_id}", reason="test delivery confirmed"),
        transition_payload(
            run_id, 19, "order", "COMPLETE_AFTER_DELIVERY", "orderId", PLACEHOLDER_ID, 4,
            reason="delivered fulfillment validated"),
        aftersales_payload(
            run_id, 20, "REQUEST", "order-completed", orderId=PLACEHOLDER_ID,
            orderItemId=PLACEHOLDER_ID, requestedQuantity=QUANTITY,
            afterSaleType="RETURN_AND_REFUND", reasonCode="SIZE_NOT_FIT",
            responsibility="BUYER", reason="governed return and refund after delivery"),
        aftersales_payload(
            run_id, 21, "APPROVE", "aftersale-request", afterSaleId=PLACEHOLDER_ID,
            expectedVersion=1, reviewerId=f"operator:{run_id}"),
        aftersales_payload(
            run_id, 22, "HAND_OVER_RETURN", "aftersale-approved", afterSaleId=PLACEHOLDER_ID,
            expectedVersion=2, carrierCode="INTERNAL_TEST", waybillNo=f"RTN-{run_id}"),
        aftersales_payload(
            run_id, 23, "MARK_RETURN_IN_TRANSIT", "return-handed-over",
            afterSaleId=PLACEHOLDER_ID, expectedVersion=2),
        aftersales_payload(
            run_id, 24, "RECEIVE_RETURN", "return-in-transit", afterSaleId=PLACEHOLDER_ID,
            expectedVersion=2, receiverId=f"warehouse-receiver:{run_id}"),
        aftersales_payload(
            run_id, 25, "ASSESS_DISPOSITION", "return-received", afterSaleId=PLACEHOLDER_ID,
            expectedVersion=2, assessorId=f"ai-return-assessor:{run_id}",
            packagingScore=96, appearanceScore=95, functionScore=98,
            safetyRisk=False, counterfeitRisk=False,
            estimatedResaleValueMinor=39800, estimatedRecoveryCostMinor=1000,
            inspectionEvidenceRef=f"restricted:return-inspection:{run_id}"),
        aftersales_payload(
            run_id, 26, "ACCEPT_INSPECTION", "disposition-assessed", afterSaleId=PLACEHOLDER_ID,
            expectedVersion=2, dispositionAssessmentId=PLACEHOLDER_ID,
            dispositionCode="RESTOCK", inspectorId=f"warehouse-inspector:{run_id}",
            qualityStatus="QUALIFIED"),
    ])
    return {"commands": commands}


def build_product(base_run_id: str, catalog: dict, master: dict,
                  aftersale: dict) -> dict:
    occurred_at = catalog["definitions"][0]["occurredAt"]
    product_run_id = f"{base_run_id}-product"
    listing_commands = copy.deepcopy(aftersale["commands"][:6])
    source_offer = listing_commands[0]["offers"][0]
    listing_commands[0]["offers"] = [
        {
            **source_offer,
            "externalOfferId": f"internal-offer:{base_run_id}:{index}",
        }
        for index in range(1, 7)
    ]
    return {
        "runIds": {
            "product": product_run_id,
            "catalog": f"{base_run_id}-cat",
            "master": f"{base_run_id}-master",
        },
        "catalog": catalog,
        "master": master,
        "listing": {"commands": listing_commands},
        "listingReceipt": {
            "idempotencyKey": f"{base_run_id}-channel-receipt",
            "listingId": PLACEHOLDER_ID,
            "expectedVersion": 6,
            "outcome": "CONFIRMED_PUBLISHED",
            "channelListingId": f"internal-channel:{base_run_id}",
            "channelStatus": "ONLINE",
            "confirmedAt": occurred_at,
            "evidenceRef": f"synthetic:yshopping-internal:{base_run_id}",
            "correlationId": str(uuid.uuid5(
                uuid.NAMESPACE_URL, f"{base_run_id}:channel-confirmation")),
            "occurredAt": occurred_at,
        },
        "readback": {"listingId": PLACEHOLDER_ID},
    }


def build_readback(erp_warehouse_source_id: str, eligibility_at: str) -> dict:
    return {
        "authority": {
            "reference": {"merchantId": PLACEHOLDER_ID, "shopId": PLACEHOLDER_ID},
            "operator": {"principalId": PLACEHOLDER_ID},
        },
        "product": {"skuId": PLACEHOLDER_ID, "spuId": PLACEHOLDER_ID},
        "listing": {"validation": {
            "canonicalSkuId": PLACEHOLDER_ID,
            "listingId": PLACEHOLDER_ID,
            "listingOfferId": PLACEHOLDER_ID,
            "expectedPriceMinor": 19900,
            "currencyCode": "CNY",
        }},
        "order": {"orderId": PLACEHOLDER_ID, "orderItemId": PLACEHOLDER_ID},
        "payment": {"paymentId": PLACEHOLDER_ID, "amountMinor": 39800, "currencyCode": "CNY"},
        "fulfillment": {"fulfillmentId": PLACEHOLDER_ID, "shipmentId": PLACEHOLDER_ID},
        "aftersale": {"afterSaleId": PLACEHOLDER_ID, "returnFulfillmentId": PLACEHOLDER_ID},
        "warehouse": {
            "warehouseId": PLACEHOLDER_ID,
            "locationId": PLACEHOLDER_ID,
            "source": {
                "sourceSystem": "ERP",
                "sourceType": "WAREHOUSE",
                "sourceId": erp_warehouse_source_id,
            },
            "eligibilityAt": eligibility_at,
        },
    }


def build_input(base_run_id: str, system_admin_source_id: str,
                erp_warehouse_source_id: str, eligibility_at: str,
                address_ref: str | None) -> dict:
    if not RUN_ID_PATTERN.fullmatch(base_run_id):
        raise ValueError("run-id must be 6-20 characters using letters, digits, dot, underscore, or dash")
    run_ids = {
        "product": f"{base_run_id}-product",
        "catalog": f"{base_run_id}-cat",
        "projection": f"{base_run_id}-proj",
        "master": f"{base_run_id}-master",
        "aftersale": f"{base_run_id}-aftersale",
        "readback": f"{base_run_id}-readback",
    }
    if any(len(value) > 32 for value in run_ids.values()):
        raise ValueError("run-id is too long after durable child suffixes are added")
    try:
        normalized_address_ref = str(uuid.UUID(address_ref or ""))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(
            "address-ref must identify an owned App address snapshot") from exc
    catalog = build_catalog(run_ids["catalog"])
    master = build_master(run_ids["master"], system_admin_source_id,
                          erp_warehouse_source_id, eligibility_at)
    aftersale = build_aftersale(run_ids["aftersale"], normalized_address_ref)
    return {
        "runIds": run_ids,
        "product": build_product(base_run_id, catalog, master, aftersale),
        "catalog": catalog,
        "projection": {"plans": [
            {"canonicalSkuId": PLACEHOLDER_ID, "targets": ["MALL", "ERP", "WMS"]}
            for _ in range(6)
        ]},
        "master": master,
        "aftersale": aftersale,
        "readback": build_readback(erp_warehouse_source_id, eligibility_at),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--system-admin-source-id", required=True)
    parser.add_argument("--erp-warehouse-source-id", required=True)
    parser.add_argument(
        "--address-ref",
        required=True,
        help="Owned App address snapshot reference used by the canonical order",
    )
    parser.add_argument(
        "--eligibility-at",
        default=os.getenv("CLOUDMOLD_ELIGIBILITY_AT", "2026-07-19T00:00:00Z"),
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        value = build_input(args.run_id, args.system_admin_source_id,
                            args.erp_warehouse_source_id, args.eligibility_at,
                            args.address_ref)
    except ValueError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
