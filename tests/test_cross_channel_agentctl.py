from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cross_channel_agentctl.py"
SPEC = importlib.util.spec_from_file_location("cross_channel_agentctl", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
RUN_ID = "cross-channel-0725"
SESSION_ID = "00000000-0000-4000-8000-000000000001"
ADDRESS_REF = "11111111-1111-4111-8111-111111111111"


def approval(environment="test"):
    value = {
        "schema_version": 1,
        "approvalType": "LOCAL_TEST_HUMAN_APPROVAL",
        "approvalId": "approval-cross-channel-0725",
        "runId": RUN_ID,
        "environment": environment,
        "approved": True,
        "approvedBy": "test-reviewer",
        "approvedAt": "2026-07-25T11:00:00Z",
        "expiresAt": "2026-07-25T13:00:00Z",
        "scopes": ["cross-channel:execute"],
    }
    value["approvalDigest"] = MODULE.approval_digest(value)
    return value


def valid_terminal():
    states = {
        "merchantStatus": "ACTIVE",
        "shopStatus": "ACTIVE",
        "catalogStatus": "ACTIVE",
        "listingStatus": "PUBLISHED",
        "stockStatus": "SELLABLE",
        "qualityStatus": "QUALIFIED",
        "paymentStatus": "REFUNDED",
        "fulfillmentStatus": "DELIVERED",
        "afterSaleStatus": "COMPLETED",
        "returnFulfillmentStatus": "INSPECTION_ACCEPTED",
        "refundStatus": "SUCCEEDED",
        "orderStatus": "RETURNED",
    }
    return {
        "identity": {
            "memberUserId": 247,
            "principalId": "principal-1",
            "sessionId": SESSION_ID,
        },
        "address": {
            "addressRef": ADDRESS_REF,
            "snapshotVersion": 1,
            "destinationRegionCode": "310000",
            "receiverSummary": "张*",
            "mobileSummary": "138****0000",
        },
        "recommendation": {
            "decisionToken": "recommend:1234567890abcdef123456",
            "resultSetToken": "recommend:1234567890abcdef123456",
            "policyVersion": "LOCAL_DETERMINISTIC_V1",
            "primaryListingId": "listing-1",
            "primaryRank": 1,
        },
        "community": {
            "contentId": "content-1",
            "likedByCurrentUser": True,
            "commentCount": 1,
            "productLinkListingId": "listing-1",
        },
        "product": {
            "merchantId": "merchant-1",
            "shopId": "shop-1",
            "canonicalSpuId": "spu-1",
            "canonicalSkuId": "sku-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "priceMinor": 39800,
            "currencyCode": "CNY",
            "inventoryVersion": 9,
            "qualityStatus": "QUALIFIED",
            "inStock": True,
        },
        "cart": {
            "cartId": "cart-1",
            "aggregateVersion": 2,
            "lineId": "line-1",
            "selectedLineCount": 1,
            "checkoutToken": "checkout-1",
        },
        "checkout": {
            "checkoutToken": "checkout-1",
            "principalId": "principal-1",
            "addressRef": ADDRESS_REF,
            "addressSnapshotVersion": 1,
            "canonicalSpuId": "spu-1",
            "canonicalSkuId": "sku-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "payableAmountMinor": 39800,
            "currencyCode": "CNY",
        },
        "order": {
            "orderId": "order-1",
            "orderItemId": "order-item-1",
            "buyerPrincipalId": "principal-1",
            "canonicalSkuId": "sku-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "quantity": 2,
            "payableAmountMinor": 39800,
            "currencyCode": "CNY",
        },
        "payment": {
            "paymentId": "payment-1",
            "orderId": "order-1",
            "capturedAmountMinor": 39800,
            "currencyCode": "CNY",
        },
        "fulfillment": {
            "fulfillmentId": "fulfillment-1",
            "shipmentId": "shipment-1",
            "orderId": "order-1",
            "canonicalSkuId": "sku-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
        },
        "review": {
            "eligible": True,
            "reviewId": "review-1",
            "moderationStatus": "APPROVED",
            "listingId": "listing-1",
            "canonicalSpuId": "spu-1",
            "canonicalSkuId": "sku-1",
            "total": 1,
        },
        "afterSale": {
            "afterSaleId": "after-sale-1",
            "orderId": "order-1",
            "canonicalSkuId": "sku-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "returnedQuantity": 2,
            "refundedAmountMinor": 39800,
            "currencyCode": "CNY",
        },
        "customerService": {
            "ticketId": "ticket-1",
            "referenceType": "AFTER_SALE",
            "referenceId": "after-sale-1",
        },
        "behavior": {
            "sessionId": SESSION_ID,
            "principalId": "principal-1",
            "eventTypes": [
                "SEARCH_REQUESTED",
                "SEARCH_RESULT_EXPOSED",
                "SEARCH_RESULT_CLICKED",
                "PDP_VIEWED",
                "CART_ADDED",
                "CHECKOUT_STARTED",
            ],
        },
        "inventory": {
            "availableQuantityBefore": 10,
            "availableQuantityAfter": 10,
            "restockedQuantity": 2,
        },
        "states": states,
        "lakehouse": {
            "outboxCdcCheckpointSucceeded": True,
            "fullDenominator": True,
            "nonempty": True,
            "sourceToFactMismatchCount": 0,
            "factToProjectionMismatchCount": 0,
            "crossTenantLinkCount": 0,
            "identityLinkMismatchCount": 0,
            "productLinkMismatchCount": 0,
            "orderPaymentMoneyMismatchCount": 0,
            "returnQuantityMismatchCount": 0,
            "dqcViolationCount": 0,
            "modelResults": {
                "yshopping_ads.ads_canonical_commerce_v2_readiness": "RECONCILED",
                "yshopping_ads.ads_canonical_after_sale_readiness": "RECONCILED",
                "yshopping_ads.ads_canonical_customer_service_readiness": "READY",
                "yshopping_ads.ads_canonical_commerce_acquisition_funnel": "NONEMPTY",
            },
        },
        "replay": {
            "verified": True,
            "effectHashMatch": True,
            "originalLedgerSha256": "a" * 64,
            "duplicateStageIds": [],
        },
    }


def _lineage(stage_id):
    base = {
        "runId": RUN_ID,
        "environment": "test",
        "tenantId": "1",
        "principalId": "principal-1",
    }
    if stage_id.startswith("app.recommendation"):
        return {**base, "sessionId": SESSION_ID}
    if stage_id.startswith("app.community"):
        return {**base, "sessionId": SESSION_ID, "contentId": "content-1"}
    if stage_id.startswith("app.session") or stage_id.startswith("app.behavior"):
        return {**base, "sessionId": SESSION_ID}
    if stage_id.startswith("app.address"):
        return {**base, "addressRef": ADDRESS_REF}
    if stage_id.startswith("app.cart"):
        return {**base, "sessionId": SESSION_ID, "addressRef": ADDRESS_REF}
    if stage_id.startswith("app.checkout"):
        return {**base, "sessionId": SESSION_ID, "addressRef": ADDRESS_REF}
    if stage_id.startswith("app.order") or stage_id.startswith("app.payment"):
        return {**base, "sessionId": SESSION_ID, "orderId": "order-1"}
    if stage_id.startswith("app.product_review"):
        return {
            **base,
            "sessionId": SESSION_ID,
            "orderId": "order-1",
            "orderItemId": "order-item-1",
        }
    if "after_sale" in stage_id or "after.sale" in stage_id:
        return {
            **base,
            "sessionId": SESSION_ID,
            "orderId": "order-1",
            "afterSaleId": "after-sale-1",
        }
    if "customer_service" in stage_id:
        return {
            **base,
            "sessionId": SESSION_ID,
            "orderId": "order-1",
            "afterSaleId": "after-sale-1",
            "ticketId": "ticket-1",
        }
    return base


def _stage_evidence(stage_id, terminal):
    evidence = {
        "app.identity.me": {
            "memberUserId": 247,
            "principalId": "principal-1",
            "principalStatus": "ACTIVE",
            "sourceSystem": "member",
            "sourceType": "MEMBER_USER",
        },
        "operator.merchant.onboard": {
            "merchantId": "merchant-1",
            "shopId": "shop-1",
            "principalId": "principal-1",
            "merchantStatus": "ACTIVE",
            "shopStatus": "ACTIVE",
            "outboxEventIds": ["merchant-event-1"],
        },
        "operator.catalog.publish": {
            "canonicalSpuId": "spu-1",
            "canonicalSkuId": "sku-1",
            "skuCode": "YS-SKU-1",
            "catalogStatus": "ACTIVE",
            "outboxEventIds": ["catalog-event-1"],
        },
        "operator.catalog.metadata_update": {
            "entityType": "SKU",
            "entityId": "sku-1",
            "businessCode": "YS-SKU-REV2",
            "currentStatus": "ACTIVE",
            "aggregateVersion": 2,
            "outboxEventIds": ["catalog-metadata-event-1"],
        },
        "operator.catalog.barcode_rotate": {
            "skuId": "sku-1",
            "previousBarcode": "6901234567890",
            "currentBarcode": "6901234567893",
            "barcodeType": "EAN13",
            "aggregateVersion": 3,
            "outboxEventIds": ["catalog-barcode-event-1"],
        },
        "operator.listing.publish": {
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "listingRevision": 1,
            "listingVersion": 6,
            "listingStatus": "PUBLISHED",
            "priceMinor": 39800,
            "currencyCode": "CNY",
            "outboxEventIds": ["listing-event-1"],
        },
        "operator.supply.prepare": {
            "sourceSystem": "YUDAO_ERP",
            "documentType": "PURCHASE_ORDER",
            "documentId": "781",
            "documentNo": "PO-20260725-01",
            "status": "PREPARE",
        },
        "operator.warehouse.receive": {
            "warehouseId": "warehouse-1",
            "locationId": "location-1",
            "inventoryLedgerTransactionId": "inventory-ledger-1",
            "receivedQuantity": 10,
            "outboxEventIds": ["warehouse-event-1"],
        },
        "operator.quality.release": {
            "inspectionTaskId": "inspection-task-1",
            "qualityStandardVersion": 1,
            "qualityStatus": "QUALIFIED",
            "inspectionDecision": "PASS",
            "outboxEventIds": ["quality-event-1"],
        },
        "operator.inventory.sellable": {
            "inventoryBalanceId": "balance-1",
            "inventoryVersion": 9,
            "availableQuantity": 10,
            "stockStatus": "SELLABLE",
            "qualityStatus": "QUALIFIED",
        },
        "app.session.start": {
            "sessionId": SESSION_ID,
            "aggregateVersion": 1,
            "eventId": "session-event-1",
        },
        "app.session.link_identity": {
            "sessionId": SESSION_ID,
            "aggregateVersion": 2,
            "status": "LINKED",
        },
        "app.recommendation.home": {
            "sceneCode": "HOME_FEED",
            "policyVersion": "LOCAL_DETERMINISTIC_V1",
            "decisionToken": terminal["recommendation"]["decisionToken"],
            "resultSetToken": terminal["recommendation"]["resultSetToken"],
            "ttlSeconds": 900,
            "expiresAt": "2026-07-25T12:30:00Z",
            "items": [
                {
                    "rank": 1,
                    "listingId": "listing-1",
                    "listingOfferId": "offer-1",
                    "canonicalSpuId": "spu-1",
                    "canonicalSkuId": "sku-1",
                    "qualityStatus": "QUALIFIED",
                }
            ],
        },
        "app.recommendation.exposure": {
            "sessionId": SESSION_ID,
            "decisionToken": terminal["recommendation"]["decisionToken"],
            "listingId": "listing-1",
            "rank": 1,
            "aggregateId": "recommendation-exposure-1",
            "aggregateVersion": 1,
            "eventId": "recommendation-event-1",
        },
        "app.recommendation.click": {
            "sessionId": SESSION_ID,
            "decisionToken": terminal["recommendation"]["decisionToken"],
            "listingId": "listing-1",
            "rank": 1,
            "aggregateId": "recommendation-click-1",
            "aggregateVersion": 2,
            "eventId": "recommendation-event-2",
        },
        "app.community.feed": {
            "list": [{"contentId": "content-1"}],
            "total": 1,
            "pageNo": 1,
            "pageSize": 20,
        },
        "app.community.detail": {
            "contentId": "content-1",
            "authorPrincipalId": "principal-creator-1",
            "body": "真实种草正文",
            "likeCount": 1,
            "commentCount": 1,
            "likedByCurrentUser": False,
            "createdAt": "2026-07-25T11:40:00Z",
            "productLink": {
                "listingId": "listing-1",
                "listingOfferId": "offer-1",
                "canonicalSpuId": "spu-1",
                "canonicalSkuId": "sku-1",
            },
        },
        "app.community.like": {
            "contentId": "content-1",
            "authorPrincipalId": "principal-creator-1",
            "body": "真实种草正文",
            "likeCount": 2,
            "commentCount": 1,
            "likedByCurrentUser": True,
            "createdAt": "2026-07-25T11:40:00Z",
            "productLink": {
                "listingId": "listing-1",
                "listingOfferId": "offer-1",
                "canonicalSpuId": "spu-1",
                "canonicalSkuId": "sku-1",
            },
        },
        "app.community.comment_create": {
            "contentId": "content-1",
            "authorPrincipalId": "principal-creator-1",
            "body": "真实种草正文",
            "likeCount": 2,
            "commentCount": 2,
            "likedByCurrentUser": True,
            "createdAt": "2026-07-25T11:40:00Z",
            "productLink": {
                "listingId": "listing-1",
                "listingOfferId": "offer-1",
                "canonicalSpuId": "spu-1",
                "canonicalSkuId": "sku-1",
            },
        },
        "app.address.snapshot_create": {
            "addressRef": ADDRESS_REF,
            "snapshotVersion": 1,
            "destinationRegionCode": "310000",
            "receiverSummary": "张*",
            "mobileSummary": "138****0000",
            "duplicate": False,
        },
        "app.address.snapshot_replay": {
            "addressRef": ADDRESS_REF,
            "snapshotVersion": 1,
            "destinationRegionCode": "310000",
            "receiverSummary": "张*",
            "mobileSummary": "138****0000",
            "duplicate": True,
        },
        "app.address.snapshot_get": {
            "addressRef": ADDRESS_REF,
            "snapshotVersion": 1,
            "destinationRegionCode": "310000",
            "receiverSummary": "张*",
            "mobileSummary": "138****0000",
        },
        "app.products.list": {
            "list": [{"listingId": "listing-1"}],
            "total": 1,
            "pageNo": 1,
            "pageSize": 10,
        },
        "app.behavior.search_requested": {
            "behaviorId": "behavior-search-1",
            "sessionId": SESSION_ID,
            "behaviorType": "SEARCH_REQUESTED",
            "eventId": "behavior-event-1",
        },
        "app.behavior.search_exposed": {
            "behaviorId": "behavior-search-2",
            "sessionId": SESSION_ID,
            "behaviorType": "SEARCH_RESULT_EXPOSED",
            "eventId": "behavior-event-2",
        },
        "app.behavior.search_clicked": {
            "behaviorId": "behavior-search-3",
            "sessionId": SESSION_ID,
            "behaviorType": "SEARCH_RESULT_CLICKED",
            "eventId": "behavior-event-3",
        },
        "app.product.detail": {
            "listingId": "listing-1",
            "listingNo": "LIST-1",
            "title": "CloudMold Sneaker",
            "primaryImageUrl": "https://example.com/p.png",
            "media": [{"type": "image"}],
            "merchantId": "merchant-1",
            "shopId": "shop-1",
            "canonicalSpuId": "spu-1",
            "listingRevision": 1,
            "listingVersion": 6,
            "qualitySummary": {"status": "QUALIFIED"},
            "skus": [
                {
                    "canonicalSkuId": "sku-1",
                    "skuCode": "YS-SKU-REV2",
                    "barcode": "6901234567893",
                    "listingOfferId": "offer-1",
                }
            ],
        },
        "app.behavior.pdp": {
            "behaviorId": "behavior-pdp-1",
            "sessionId": SESSION_ID,
            "behaviorType": "PDP_VIEWED",
            "eventId": "behavior-event-4",
        },
        "app.behavior.cart_added": {
            "behaviorId": "behavior-cart-1",
            "sessionId": SESSION_ID,
            "behaviorType": "CART_ADDED",
            "eventId": "behavior-event-5",
        },
        "app.cart.get": {
            "cartId": "cart-1",
            "principalId": "principal-1",
            "aggregateVersion": 0,
            "lineCount": 0,
            "selectedLineCount": 0,
            "duplicate": False,
            "lines": [],
        },
        "app.cart.add": {
            "cartId": "cart-1",
            "principalId": "principal-1",
            "aggregateVersion": 2,
            "lineCount": 1,
            "selectedLineCount": 1,
            "duplicate": False,
            "lines": [
                {
                    "lineId": "line-1",
                    "listingId": "listing-1",
                    "listingOfferId": "offer-1",
                    "canonicalSkuId": "sku-1",
                    "selected": True,
                }
            ],
        },
        "app.cart.preview_selected": {
            "checkoutToken": "checkout-1",
            "principalId": "principal-1",
            "addressRef": ADDRESS_REF,
            "addressSnapshotVersion": 1,
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "canonicalSkuId": "sku-1",
            "quantity": 2,
            "unitPriceMinor": 19900,
            "productAmountMinor": 39800,
            "shippingAmountMinor": 0,
            "discountAmountMinor": 0,
            "payableAmountMinor": 39800,
            "currencyCode": "CNY",
            "availableQuantity": 10,
            "expiresAt": "2026-07-25T12:30:00Z",
        },
        "app.checkout.preview": {
            "checkoutToken": "checkout-1",
            "principalId": "principal-1",
            "addressRef": ADDRESS_REF,
            "addressSnapshotVersion": 1,
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "canonicalSkuId": "sku-1",
            "quantity": 2,
            "unitPriceMinor": 19900,
            "productAmountMinor": 39800,
            "shippingAmountMinor": 0,
            "discountAmountMinor": 0,
            "payableAmountMinor": 39800,
            "currencyCode": "CNY",
            "availableQuantity": 10,
            "expiresAt": "2026-07-25T12:30:00Z",
        },
        "app.behavior.checkout": {
            "behaviorId": "behavior-checkout-1",
            "sessionId": SESSION_ID,
            "behaviorType": "CHECKOUT_STARTED",
            "eventId": "behavior-event-6",
        },
        "app.order.create": {
            "orderId": "order-1",
            "orderNo": "ORDER-1",
            "orderItemId": "order-item-1",
            "buyerPrincipalId": "principal-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "canonicalSkuId": "sku-1",
            "quantity": 2,
            "payableAmountMinor": 39800,
            "currencyCode": "CNY",
            "aggregateVersion": 1,
            "status": "CREATED",
            "outboxEventIds": ["order-event-1"],
        },
        "app.order.get": {
            "orderId": "order-1",
            "aggregateVersion": 1,
            "status": "RETURNED",
            "items": [{"orderItemId": "order-item-1"}],
        },
        "app.payment.capture": {
            "paymentId": "payment-1",
            "currentStatus": "REFUNDED",
            "capturedAmountMinor": 39800,
            "currencyCode": "CNY",
            "behaviorVersion": 3,
            "outboxEventIds": ["payment-event-1"],
        },
        "operator.fulfillment.complete": {
            "fulfillmentId": "fulfillment-1",
            "shipmentId": "shipment-1",
            "status": "DELIVERED",
            "aggregateVersion": 4,
            "orderId": "order-1",
            "outboxEventIds": ["fulfillment-event-1"],
        },
        "app.fulfillment.by_order": {
            "orderId": "order-1",
            "fulfillmentId": "fulfillment-1",
            "shipmentId": "shipment-1",
            "fulfillmentStatus": "DELIVERED",
            "trackingEvents": [{"status": "SIGNED"}],
        },
        "app.product_review.eligibility": {
            "eligible": True,
            "reasonCode": "",
            "existingReviewId": "",
            "existingModerationStatus": "",
            "orderId": "order-1",
            "orderItemId": "order-item-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "merchantId": "merchant-1",
            "shopId": "shop-1",
            "canonicalSpuId": "spu-1",
            "canonicalSkuId": "sku-1",
        },
        "app.product_review.create": {
            "reviewId": "review-1",
            "orderId": "order-1",
            "orderItemId": "order-item-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "merchantId": "merchant-1",
            "shopId": "shop-1",
            "canonicalSpuId": "spu-1",
            "canonicalSkuId": "sku-1",
            "overallScore": 4,
            "moderationStatus": "APPROVED",
            "duplicate": False,
        },
        "app.product_review.listing": {
            "total": 1,
            "pageNo": 1,
            "pageSize": 20,
            "list": [{"reviewId": "review-1"}],
        },
        "app.after_sale.create": {
            "afterSaleId": "after-sale-1",
            "afterSaleNo": "AS-1",
            "orderId": "order-1",
            "orderItemId": "order-item-1",
            "caseStatus": "REQUESTED",
            "aggregateVersion": 1,
            "outboxEventIds": ["after-sale-event-1"],
        },
        "operator.after_sale.complete": {
            "afterSaleId": "after-sale-1",
            "returnFulfillmentId": "return-fulfillment-1",
            "inspectionId": "inspection-1",
            "refundTransactionId": "refund-1",
            "inventoryReturnLedgerTransactionId": "inventory-return-1",
            "afterSaleStatus": "COMPLETED",
            "paymentStatus": "REFUNDED",
            "orderStatus": "RETURNED",
            "returnedQuantity": 2,
            "refundedAmountMinor": 39800,
            "outboxEventIds": ["after-sale-event-2"],
        },
        "app.after_sale.get": {
            "afterSaleId": "after-sale-1",
            "orderId": "order-1",
            "caseStatus": "COMPLETED",
            "refundStatus": "SUCCEEDED",
            "returnFulfillmentStatus": "INSPECTION_ACCEPTED",
        },
        "app.customer_service.ticket_create": {
            "ticketId": "ticket-1",
            "ticketNo": "TICKET-1",
            "ticketStatus": "OPEN",
            "ticketVersion": 1,
            "outboxEventIds": ["ticket-event-1"],
        },
        "app.customer_service.ticket_get": {
            "ticketId": "ticket-1",
            "ticketStatus": "OPEN",
            "ticketVersion": 1,
        },
        "reconcile.lakehouse": {
            **terminal["lakehouse"],
            "dataFreshnessAt": "2026-07-25T11:59:00Z",
        },
    }
    return evidence[stage_id]


def runtime_receipts(contracts, recorded_at="2026-07-25T11:58:00Z"):
    terminal = valid_terminal()
    receipts = []
    write_ids = []
    for stage in contracts["scenario"]["stages"]:
        if stage["operation"] == "WRITE":
            write_ids.append(stage["id"])
        receipt = MODULE._receipt_template(stage, contracts, RUN_ID, "test")
        receipt["runtime"]["recordedAt"] = recorded_at
        receipt["requestEnvelope"] = {"stageId": stage["id"], "kind": "request"}
        receipt["responseEnvelope"] = {"stageId": stage["id"], "kind": "response"}
        if stage["operation"] == "WRITE":
            receipt["effectEnvelope"] = {
                "stageId": stage["id"],
                "kind": "effect",
                "eventIds": [f"event:{stage['id']}"],
            }
        else:
            receipt["effectEnvelope"] = {}
        receipt["evidence"] = _stage_evidence(stage["id"], terminal)
        receipt["linkage"] = _lineage(stage["id"])
        receipts.append(receipt)
    terminal["replay"]["duplicateStageIds"] = write_ids
    return receipts, terminal


def build_valid_runtime_ledger(contracts):
    receipts, terminal = runtime_receipts(contracts)
    with tempfile.TemporaryDirectory() as directory:
        runtime_root = Path(directory)
        MODULE.initialize_runtime(
            RUN_ID,
            "test",
            approval(),
            contracts,
            runtime_root=runtime_root,
            now=NOW,
        )
        runtime_dir = MODULE._runtime_dir(runtime_root, RUN_ID)
        MODULE.record_runtime_receipts(runtime_dir, receipts, contracts, now=NOW)
        ledger = MODULE.build_runtime_ledger(runtime_dir, terminal, contracts, now=NOW)
    return ledger


class CrossChannelAgentCtlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts = MODULE.validate_contracts()

    def test_contracts_and_real_model_references_validate(self):
        self.assertEqual(self.contracts["stageCount"], 48)
        self.assertEqual(self.contracts["blockers"], [])
        blockers = {item["stageId"] for item in self.contracts["blockers"]}
        self.assertNotIn("app.identity.me", blockers)
        self.assertNotIn("app.recommendation.home", blockers)
        self.assertNotIn("app.community.feed", blockers)
        self.assertNotIn("app.cart.add", blockers)
        self.assertNotIn("app.product_review.create", blockers)
        self.assertNotIn("app.address.snapshot_create", blockers)
        self.assertNotIn("app.checkout.preview", blockers)
        self.assertNotIn("operator.quality.release", blockers)
        self.assertNotIn("reconcile.lakehouse", blockers)

    def test_quality_release_binding_is_the_complete_fail_closed_admin_sequence(self):
        binding = self.contracts["bindings"]["external_evidence_bindings"][
            "operator.quality.release"
        ]
        self.assertEqual(binding["adapter"], "admin_rest_sequence")
        self.assertEqual(binding["path"], "/admin-api/cloudmold/quality/command")
        self.assertEqual(binding["permission"], "cloudmold:quality:command")
        self.assertEqual(
            [operation["operation"] for operation in binding["operations"]],
            [operation[0] for operation in MODULE.QUALITY_RELEASE_OPERATIONS],
        )
        self.assertEqual(binding["operations"][6]["required_decision"], "PASS")
        self.assertEqual(binding["event_evidence"]["delivery_status"], 20)
        self.assertTrue(binding["response_contract"]["immutable_replay_required"])

    def test_lakehouse_binding_uses_only_real_fail_closed_lakehousectl_commands(self):
        binding = self.contracts["bindings"]["external_evidence_bindings"][
            "reconcile.lakehouse"
        ]
        self.assertEqual(binding["adapter"], "lakehousectl_sequence")
        self.assertEqual(
            [command["command"] for command in binding["commands"]],
            MODULE.LAKEHOUSE_RECONCILE_COMMANDS,
        )
        executable = Path(__file__).resolve().parents[1] / binding["executable"]
        self.assertTrue(executable.is_file())
        self.assertEqual(
            set(binding["required_zero_checks"]),
            set(MODULE.ZERO_CHECK_NAME_MAP),
        )
        self.assertFalse(binding["acceptance"]["simulated"])
        self.assertFalse(binding["acceptance"]["production_credit"])

    def test_skill_remains_partial_despite_local_execute_bindings(self):
        root = Path(__file__).resolve().parents[1]
        registry = MODULE.load_json(root / "skills" / "registry.json")
        entries = {entry["skill_id"]: entry for entry in registry["skills"]}
        entry = entries["skill.cloudmold.cross-channel.local-demo.v1"]
        self.assertEqual(entry["status"], "partial")
        manifest = MODULE.load_json(root / "skills" / entry["manifest"])
        self.assertEqual(manifest["default_mode"], "plan")
        self.assertEqual(
            set(manifest["allowed_execute_environments"]),
            {"local", "demo", "test"},
        )

    def test_frozen_app_facade_paths_and_address_contract(self):
        bindings = self.contracts["bindings"]["bindings"]
        expected_paths = {
            "app.identity.me": "/app-api/cloudmold/app/me",
            "app.session.link_identity": "/app-api/cloudmold/app/behavior/sessions/link",
            "app.address.snapshot_create": "/app-api/cloudmold/app/addresses/snapshots",
            "app.address.snapshot_get": "/app-api/cloudmold/app/addresses/snapshots/{addressRef}",
            "app.recommendation.home": "/app-api/cloudmold/app/recommendations",
            "app.recommendation.exposure": "/app-api/cloudmold/app/recommendations/exposures",
            "app.recommendation.click": "/app-api/cloudmold/app/recommendations/clicks",
            "app.community.feed": "/app-api/cloudmold/app/community/feed",
            "app.community.detail": "/app-api/cloudmold/app/community/posts/{contentId}",
            "app.community.like": "/app-api/cloudmold/app/community/posts/{contentId}/like",
            "app.community.comment_create": "/app-api/cloudmold/app/community/posts/{contentId}/comments",
            "app.products.list": "/app-api/cloudmold/app/products",
            "app.product.detail": "/app-api/cloudmold/app/products/{listingId}",
            "app.cart.get": "/app-api/cloudmold/app/cart",
            "app.cart.add": "/app-api/cloudmold/app/cart/items",
            "app.cart.preview_selected": "/app-api/cloudmold/app/cart/checkout/preview",
            "app.checkout.preview": "/app-api/cloudmold/app/checkout/preview",
            "app.order.create": "/app-api/cloudmold/app/orders",
            "app.order.get": "/app-api/cloudmold/app/orders/{orderId}",
            "app.payment.capture": "/app-api/cloudmold/app/payments/internal-test/capture-with-attribution",
            "app.fulfillment.by_order": "/app-api/cloudmold/app/fulfillments/by-order/{orderId}",
            "app.product_review.eligibility": "/app-api/cloudmold/app/product-reviews/eligibility",
            "app.product_review.create": "/app-api/cloudmold/app/product-reviews",
            "app.product_review.listing": "/app-api/cloudmold/app/product-reviews/listings/{listingId}",
            "app.after_sale.create": "/app-api/cloudmold/app/after-sales",
            "app.after_sale.get": "/app-api/cloudmold/app/after-sales/{afterSaleId}",
            "app.customer_service.ticket_create": "/app-api/cloudmold/app/customer-service/tickets",
            "app.customer_service.ticket_get": "/app-api/cloudmold/app/customer-service/tickets/{ticketId}",
        }
        self.assertEqual({key: bindings[key]["path"] for key in expected_paths}, expected_paths)
        self.assertEqual(
            set(bindings["app.address.snapshot_create"]["forbidden_request_fields"]),
            MODULE.RAW_DELIVERY_PII_FIELDS,
        )
        self.assertEqual(
            bindings["app.checkout.preview"]["response_fields"][:4],
            ["checkoutToken", "principalId", "addressRef", "addressSnapshotVersion"],
        )

    def test_contract_validation_rejects_fake_availability(self):
        root = Path(__file__).resolve().parents[1]
        scenario_path = root / "contracts" / "cross-channel-agent-scenario-v1.json"
        reconciliation_path = (
            root
            / "yml"
            / "yshopping-lakehouse"
            / "contracts"
            / "yshopping-cross-channel-agent-reconciliation-v1.json"
        )
        invalid_bindings = deepcopy(self.contracts["bindings"])
        invalid_bindings["bindings"]["app.identity.me"]["availability"] = "SYNTHETIC_READY"
        with tempfile.TemporaryDirectory() as directory:
            bindings_path = Path(directory) / "bindings.json"
            bindings_path.write_text(
                json.dumps(invalid_bindings, ensure_ascii=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "availability is invalid"):
                MODULE.validate_contracts(scenario_path, bindings_path, reconciliation_path)

    def test_plan_is_deterministic_and_fail_closed(self):
        first = MODULE.build_plan(RUN_ID, "test", self.contracts)
        second = MODULE.build_plan(RUN_ID, "test", self.contracts)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "READY_FOR_APPROVED_EXECUTE")
        self.assertFalse(first["simulated"])
        self.assertTrue(
            all(step["idempotencyKey"].startswith(f"cca:{RUN_ID}:") for step in first["steps"])
        )
        self.assertEqual(first["steps"][0]["bindingDefinitionSha256"], self.contracts["bindingDigests"]["app.identity.me"])
        steps = {step["stageId"]: step for step in first["steps"]}
        self.assertEqual(steps["operator.quality.release"]["invocation"]["adapter"], "admin_rest_sequence")
        self.assertEqual(steps["reconcile.lakehouse"]["invocation"]["adapter"], "lakehousectl_sequence")

    def test_execute_resume_replay_and_validate_ledger(self):
        receipts, terminal = runtime_receipts(self.contracts)
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory)
            state = MODULE.initialize_runtime(
                RUN_ID,
                "test",
                approval(),
                self.contracts,
                runtime_root=runtime_root,
                now=NOW,
            )
            self.assertEqual(state["status"], "READY_TO_RECORD")
            runtime_dir = MODULE._runtime_dir(runtime_root, RUN_ID)
            summary = MODULE.record_runtime_receipts(runtime_dir, receipts, self.contracts, now=NOW)
            self.assertEqual(summary["status"], "READY_TO_REPLAY")
            self.assertEqual(len(summary["recordedStages"]), 48)
            ledger = MODULE.build_runtime_ledger(runtime_dir, terminal, self.contracts, now=NOW)
            self.assertEqual(ledger["schema_version"], 2)
            self.assertEqual(len(ledger["runtimeReceipts"]), 48)
            result = MODULE.validate_terminal_ledger(ledger, self.contracts, now=NOW)
            self.assertEqual(result["status"], "valid")
            self.assertEqual(result["stageCount"], 48)
            self.assertFalse(result["productionCredit"])

    def test_resume_rejects_unregistered_or_stale_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = Path(directory)
            MODULE.initialize_runtime(
                RUN_ID,
                "test",
                approval(),
                self.contracts,
                runtime_root=runtime_root,
                now=NOW,
            )
            runtime_dir = MODULE._runtime_dir(runtime_root, RUN_ID)
            invalid = {
                "schema_version": 2,
                "stageId": "unknown.stage",
            }
            with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "unregistered runtime receipt stage"):
                MODULE.record_runtime_receipts(runtime_dir, [invalid], self.contracts, now=NOW)

            receipts, _ = runtime_receipts(self.contracts, recorded_at="2026-05-01T00:00:00Z")
            with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "older than 30 days"):
                MODULE.record_runtime_receipts(runtime_dir, [receipts[0]], self.contracts, now=NOW)

    def test_approval_is_run_environment_scope_and_expiry_bound(self):
        value = approval()
        value["runId"] = "different-run"
        value["approvalDigest"] = MODULE.approval_digest(value)
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "runId mismatch"):
            MODULE.validate_approval(value, RUN_ID, "test", "cross-channel:execute", now=NOW)
        expired = approval()
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "expired"):
            MODULE.validate_approval(
                expired,
                RUN_ID,
                "test",
                "cross-channel:execute",
                now=datetime(2026, 7, 25, 14, 0, tzinfo=timezone.utc),
            )

    def test_unsigned_or_synthetic_terminal_ledger_is_rejected(self):
        ledger = build_valid_runtime_ledger(self.contracts)
        unsigned = deepcopy(ledger)
        unsigned.pop("terminalSignature")
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "terminalSignature"):
            MODULE.validate_terminal_ledger(unsigned, self.contracts, now=NOW)

        synthetic = deepcopy(ledger)
        synthetic["runtimeReceipts"][0]["requestEnvelope"]["tampered"] = True
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "runtimeReceiptManifestSha256"):
            MODULE.validate_terminal_ledger(synthetic, self.contracts, now=NOW)

    def test_money_quantity_lakehouse_and_replay_are_hard_gates(self):
        money = build_valid_runtime_ledger(self.contracts)
        money["terminalEvidence"]["payment"]["capturedAmountMinor"] = 39799
        money["terminalEvidenceSha256"] = MODULE.digest(money["terminalEvidence"])
        money["terminalSignature"] = MODULE._sign_runtime_ledger(money, signed_at=NOW)
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "captured mismatch"):
            MODULE.validate_terminal_ledger(money, self.contracts, now=NOW)

        quantity = build_valid_runtime_ledger(self.contracts)
        quantity["terminalEvidence"]["inventory"]["restockedQuantity"] = 1
        quantity["terminalEvidenceSha256"] = MODULE.digest(quantity["terminalEvidence"])
        quantity["terminalSignature"] = MODULE._sign_runtime_ledger(quantity, signed_at=NOW)
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "restocked quantity mismatch"):
            MODULE.validate_terminal_ledger(quantity, self.contracts, now=NOW)

        lakehouse = build_valid_runtime_ledger(self.contracts)
        lakehouse["terminalEvidence"]["lakehouse"]["nonempty"] = False
        lakehouse["terminalEvidenceSha256"] = MODULE.digest(lakehouse["terminalEvidence"])
        lakehouse["terminalSignature"] = MODULE._sign_runtime_ledger(lakehouse, signed_at=NOW)
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "non-empty"):
            MODULE.validate_terminal_ledger(lakehouse, self.contracts, now=NOW)

        replay = build_valid_runtime_ledger(self.contracts)
        replay["terminalEvidence"]["replay"]["duplicateStageIds"] = []
        replay["terminalEvidenceSha256"] = MODULE.digest(replay["terminalEvidence"])
        replay["terminalSignature"] = MODULE._sign_runtime_ledger(replay, signed_at=NOW)
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "replay missing"):
            MODULE.validate_terminal_ledger(replay, self.contracts, now=NOW)

    def test_address_quality_and_lakehouse_receipts_cannot_claim_a_different_result(self):
        address = build_valid_runtime_ledger(self.contracts)
        address_receipt = next(
            item for item in address["runtimeReceipts"] if item["stageId"] == "app.address.snapshot_replay"
        )
        address_receipt["evidence"]["duplicate"] = False
        stage = next(
            item for item in self.contracts["scenario"]["stages"] if item["id"] == "app.address.snapshot_replay"
        )
        address["runtimeReceipts"][
            address["runtimeReceipts"].index(address_receipt)
        ] = MODULE._normalize_runtime_receipt(
            address_receipt,
            stage,
            self.contracts,
            RUN_ID,
            "test",
            now=NOW,
        )
        address["runtimeReceiptManifestSha256"] = MODULE.digest(address["runtimeReceipts"])
        address["terminalSignature"] = MODULE._sign_runtime_ledger(address, signed_at=NOW)
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "address replay duplicate"):
            MODULE.validate_terminal_ledger(address, self.contracts, now=NOW)

        quality = build_valid_runtime_ledger(self.contracts)
        quality_step = next(
            item for item in quality["runtimeReceipts"] if item["stageId"] == "operator.quality.release"
        )
        quality_step["evidence"]["inspectionDecision"] = "FAIL"
        stage = next(
            item for item in self.contracts["scenario"]["stages"] if item["id"] == "operator.quality.release"
        )
        quality["runtimeReceipts"][
            quality["runtimeReceipts"].index(quality_step)
        ] = MODULE._normalize_runtime_receipt(
            quality_step,
            stage,
            self.contracts,
            RUN_ID,
            "test",
            now=NOW,
        )
        quality["runtimeReceiptManifestSha256"] = MODULE.digest(quality["runtimeReceipts"])
        quality["terminalSignature"] = MODULE._sign_runtime_ledger(quality, signed_at=NOW)
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "inspectionDecision"):
            MODULE.validate_terminal_ledger(quality, self.contracts, now=NOW)

        lakehouse = build_valid_runtime_ledger(self.contracts)
        lakehouse_step = next(
            item for item in lakehouse["runtimeReceipts"] if item["stageId"] == "reconcile.lakehouse"
        )
        lakehouse_step["evidence"]["dqcViolationCount"] = 1
        stage = next(
            item for item in self.contracts["scenario"]["stages"] if item["id"] == "reconcile.lakehouse"
        )
        lakehouse["runtimeReceipts"][
            lakehouse["runtimeReceipts"].index(lakehouse_step)
        ] = MODULE._normalize_runtime_receipt(
            lakehouse_step,
            stage,
            self.contracts,
            RUN_ID,
            "test",
            now=NOW,
        )
        lakehouse["runtimeReceiptManifestSha256"] = MODULE.digest(lakehouse["runtimeReceipts"])
        lakehouse["terminalSignature"] = MODULE._sign_runtime_ledger(lakehouse, signed_at=NOW)
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "lakehouse receipt"):
            MODULE.validate_terminal_ledger(lakehouse, self.contracts, now=NOW)


if __name__ == "__main__":
    unittest.main()
