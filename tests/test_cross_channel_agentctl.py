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
            "sessionId": "00000000-0000-4000-8000-000000000001",
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
        "checkout": {
            "principalId": "principal-1",
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
            "sessionId": "00000000-0000-4000-8000-000000000001",
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


def valid_ledger(contracts):
    terminal = valid_terminal()
    write_ids = [
        stage["id"]
        for stage in contracts["scenario"]["stages"]
        if stage["operation"] == "WRITE"
    ]
    terminal["replay"]["duplicateStageIds"] = write_ids
    steps = []
    for stage in contracts["scenario"]["stages"]:
        evidence = {field: f"{stage['id']}:{field}" for field in stage["required_evidence"]}
        step = {
            "stageId": stage["id"],
            "status": "SUCCEEDED",
            "idempotencyKey": MODULE.stable_idempotency_key(RUN_ID, stage["id"]),
            "responseSha256": "b" * 64,
            "evidence": evidence,
        }
        if stage["operation"] == "WRITE":
            step.update(
                {
                    "requestSha256": "c" * 64,
                    "effectSha256": "d" * 64,
                    "eventIds": [f"event:{stage['id']}"],
                }
            )
        steps.append(step)
    by_id = {step["stageId"]: step["evidence"] for step in steps}
    by_id["app.identity.me"]["principalId"] = "principal-1"
    by_id["app.session.start"]["sessionId"] = "00000000-0000-4000-8000-000000000001"
    behavior_types = {
        "app.behavior.search_requested": "SEARCH_REQUESTED",
        "app.behavior.search_exposed": "SEARCH_RESULT_EXPOSED",
        "app.behavior.search_clicked": "SEARCH_RESULT_CLICKED",
        "app.behavior.pdp": "PDP_VIEWED",
        "app.behavior.cart_added": "CART_ADDED",
        "app.behavior.checkout": "CHECKOUT_STARTED",
    }
    for stage_id, behavior_type in behavior_types.items():
        by_id[stage_id]["sessionId"] = "00000000-0000-4000-8000-000000000001"
        by_id[stage_id]["behaviorType"] = behavior_type
    by_id["app.product.detail"].update(
        {
            "listingId": "listing-1",
            "canonicalSpuId": "spu-1",
            "skus": [
                {
                    "canonicalSkuId": "sku-1",
                    "listingOfferId": "offer-1",
                }
            ],
        }
    )
    by_id["app.checkout.preview"].update(
        {
            "principalId": "principal-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "canonicalSkuId": "sku-1",
            "payableAmountMinor": 39800,
        }
    )
    by_id["app.order.create"].update(
        {
            "orderId": "order-1",
            "buyerPrincipalId": "principal-1",
            "listingId": "listing-1",
            "listingOfferId": "offer-1",
            "canonicalSkuId": "sku-1",
            "payableAmountMinor": 39800,
        }
    )
    by_id["app.payment.capture"].update(
        {
            "paymentId": "payment-1",
            "capturedAmountMinor": 39800,
        }
    )
    by_id["app.fulfillment.by_order"].update(
        {
            "orderId": "order-1",
            "fulfillmentId": "fulfillment-1",
            "shipmentId": "shipment-1",
        }
    )
    by_id["app.after_sale.get"].update(
        {
            "afterSaleId": "after-sale-1",
            "orderId": "order-1",
        }
    )
    by_id["app.customer_service.ticket_get"].update(
        {
            "ticketId": "ticket-1",
            "referenceType": "AFTER_SALE",
            "referenceId": "after-sale-1",
        }
    )
    return {
        "schema_version": 1,
        "scenarioId": contracts["scenario"]["scenario_id"],
        "scenarioVersion": contracts["scenario"]["scenario_version"],
        "mode": "EXECUTE",
        "status": "SUCCEEDED",
        "simulated": False,
        "evidenceScope": "TEST",
        "runId": RUN_ID,
        "environment": "test",
        "scenarioDigest": contracts["scenarioDigest"],
        "bindingsDigest": contracts["bindingsDigest"],
        "reconciliationDigest": contracts["reconciliationDigest"],
        "approval": approval(),
        "steps": steps,
        "terminalEvidence": terminal,
        "terminalEvidenceSha256": MODULE.digest(terminal),
    }


def ready_contracts(contracts):
    value = deepcopy(contracts)
    for binding in value["bindings"]["bindings"].values():
        binding["availability"] = MODULE.EXECUTABLE_AVAILABILITY
    for binding in value["bindings"]["external_evidence_bindings"].values():
        binding["availability"] = MODULE.EXECUTABLE_AVAILABILITY
    value["bindingsDigest"] = MODULE.digest(value["bindings"])
    value["blockers"] = []
    return value


class CrossChannelAgentCtlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts = MODULE.validate_contracts()
        cls.ready_contracts = ready_contracts(cls.contracts)

    def test_contracts_and_real_model_references_validate(self):
        self.assertEqual(self.contracts["stageCount"], 28)
        self.assertGreater(len(self.contracts["blockers"]), 0)
        blockers = {item["stageId"] for item in self.contracts["blockers"]}
        self.assertIn("app.identity.me", blockers)
        self.assertIn("app.checkout.preview", blockers)
        self.assertIn("operator.quality.release", blockers)
        self.assertIn("reconcile.lakehouse", blockers)

    def test_skill_is_registered_as_partial_until_execute_blockers_close(self):
        root = Path(__file__).resolve().parents[1]
        registry = MODULE.load_json(root / "skills" / "registry.json")
        entries = {
            entry["skill_id"]: entry for entry in registry["skills"]
        }
        entry = entries["skill.cloudmold.cross-channel.local-demo.v1"]
        self.assertEqual(entry["status"], "partial")
        manifest = MODULE.load_json(
            root / "skills" / entry["manifest"]
        )
        self.assertEqual(manifest["default_mode"], "plan")
        self.assertEqual(
            set(manifest["allowed_execute_environments"]),
            {"local", "demo", "test"},
        )

    def test_frozen_app_facade_paths_and_product_contract(self):
        bindings = self.contracts["bindings"]["bindings"]
        expected_paths = {
            "app.identity.me": "/app-api/cloudmold/app/me",
            "app.products.list": "/app-api/cloudmold/app/products",
            "app.product.detail": "/app-api/cloudmold/app/products/{listingId}",
            "app.checkout.preview": "/app-api/cloudmold/app/checkout/preview",
            "app.order.create": "/app-api/cloudmold/app/orders",
            "app.order.get": "/app-api/cloudmold/app/orders/{orderId}",
            "app.payment.capture": "/app-api/cloudmold/app/payments/internal-test/capture",
            "app.fulfillment.by_order": "/app-api/cloudmold/app/fulfillments/by-order/{orderId}",
            "app.after_sale.create": "/app-api/cloudmold/app/after-sales",
            "app.after_sale.get": "/app-api/cloudmold/app/after-sales/{afterSaleId}",
            "app.customer_service.ticket_create": "/app-api/cloudmold/app/customer-service/tickets",
            "app.customer_service.ticket_get": "/app-api/cloudmold/app/customer-service/tickets/{ticketId}",
        }
        self.assertEqual(
            {key: bindings[key]["path"] for key in expected_paths},
            expected_paths,
        )
        self.assertIn("qualitySummary", bindings["app.product.detail"]["response_fields"])
        self.assertIn("availableQuantity", bindings["app.product.detail"]["sku_response_fields"])
        self.assertIn("qualityStatus", bindings["app.product.detail"]["sku_response_fields"])
        self.assertEqual(
            bindings["app.order.create"]["request_fields"],
            ["idempotencyKey", "checkoutToken"],
        )
        self.assertEqual(
            set(bindings["app.order.create"]["forbidden_request_fields"]),
            MODULE.RAW_DELIVERY_PII_FIELDS,
        )
        self.assertEqual(
            set(bindings["app.identity.me"]["response_fields"]),
            {
                "memberUserId",
                "principalId",
                "principalStatus",
                "sourceSystem",
                "sourceType",
            },
        )
        self.assertTrue(
            MODULE.RESTRICTED_CONSUMER_FIELDS.issubset(
                set(bindings["app.product.detail"]["forbidden_response_fields"])
            )
        )

    def test_contract_validation_rejects_raw_pii_and_restricted_evidence(self):
        root = Path(__file__).resolve().parents[1]
        scenario_path = root / "contracts" / "cross-channel-agent-scenario-v1.json"
        reconciliation_path = (
            root
            / "yml"
            / "yshopping-lakehouse"
            / "contracts"
            / "yshopping-cross-channel-agent-reconciliation-v1.json"
        )
        invalid_variants = []
        raw_pii = deepcopy(self.contracts["bindings"])
        raw_pii["bindings"]["app.order.create"]["request_fields"].append(
            "receiverMobile"
        )
        invalid_variants.append((raw_pii, "raw delivery PII"))
        restricted = deepcopy(self.contracts["bindings"])
        restricted["bindings"]["app.product.detail"]["response_fields"].append(
            "inspectionTaskId"
        )
        invalid_variants.append((restricted, "restricted consumer fields"))

        for invalid_bindings, expected_error in invalid_variants:
            with self.subTest(expected_error=expected_error):
                with tempfile.TemporaryDirectory() as directory:
                    bindings_path = Path(directory) / "bindings.json"
                    bindings_path.write_text(
                        json.dumps(invalid_bindings, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        MODULE.CrossChannelAgentError,
                        expected_error,
                    ):
                        MODULE.validate_contracts(
                            scenario_path,
                            bindings_path,
                            reconciliation_path,
                        )

    def test_plan_is_deterministic_and_fail_closed(self):
        first = MODULE.build_plan(RUN_ID, "test", self.contracts)
        second = MODULE.build_plan(RUN_ID, "test", self.contracts)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "BLOCKED_DEPENDENCY")
        self.assertFalse(first["simulated"])
        self.assertTrue(
            all(step["idempotencyKey"].startswith(f"cca:{RUN_ID}:") for step in first["steps"])
        )

    def test_execute_gate_requires_implemented_bindings(self):
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "execute blocked"):
            MODULE.build_execute_gate(
                RUN_ID,
                "test",
                approval(),
                self.contracts,
                now=NOW,
            )

    def test_terminal_ledger_cannot_bypass_current_binding_blockers(self):
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "bindings are unavailable"):
            MODULE.validate_terminal_ledger(
                valid_ledger(self.contracts),
                self.contracts,
                now=NOW,
            )

    def test_approval_is_run_environment_scope_and_expiry_bound(self):
        value = approval()
        value["runId"] = "different-run"
        value["approvalDigest"] = MODULE.approval_digest(value)
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "runId mismatch"):
            MODULE.validate_approval(
                value,
                RUN_ID,
                "test",
                "cross-channel:execute",
                now=NOW,
            )
        expired = approval()
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "expired"):
            MODULE.validate_approval(
                expired,
                RUN_ID,
                "test",
                "cross-channel:execute",
                now=datetime(2026, 7, 25, 14, 0, tzinfo=timezone.utc),
            )

    def test_complete_non_simulated_terminal_ledger_is_accepted(self):
        result = MODULE.validate_terminal_ledger(
            valid_ledger(self.ready_contracts),
            self.ready_contracts,
            now=NOW,
        )
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["stageCount"], 28)
        self.assertFalse(result["productionCredit"])

    def test_simulated_or_cross_channel_identity_mismatch_is_rejected(self):
        simulated = valid_ledger(self.ready_contracts)
        simulated["simulated"] = True
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "simulated"):
            MODULE.validate_terminal_ledger(simulated, self.ready_contracts, now=NOW)

        mismatch = valid_ledger(self.ready_contracts)
        mismatch["terminalEvidence"]["order"]["buyerPrincipalId"] = "another-principal"
        mismatch["terminalEvidenceSha256"] = MODULE.digest(mismatch["terminalEvidence"])
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "buyerPrincipalId"):
            MODULE.validate_terminal_ledger(mismatch, self.ready_contracts, now=NOW)

    def test_money_quantity_lakehouse_and_replay_are_hard_gates(self):
        money = valid_ledger(self.ready_contracts)
        money["terminalEvidence"]["payment"]["capturedAmountMinor"] = 39799
        money["terminalEvidenceSha256"] = MODULE.digest(money["terminalEvidence"])
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "captured mismatch"):
            MODULE.validate_terminal_ledger(money, self.ready_contracts, now=NOW)

        quantity = valid_ledger(self.ready_contracts)
        quantity["terminalEvidence"]["inventory"]["restockedQuantity"] = 1
        quantity["terminalEvidenceSha256"] = MODULE.digest(quantity["terminalEvidence"])
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "restocked quantity mismatch"):
            MODULE.validate_terminal_ledger(quantity, self.ready_contracts, now=NOW)

        lakehouse = valid_ledger(self.ready_contracts)
        lakehouse["terminalEvidence"]["lakehouse"]["dqcViolationCount"] = 1
        lakehouse["terminalEvidenceSha256"] = MODULE.digest(lakehouse["terminalEvidence"])
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "dqcViolationCount"):
            MODULE.validate_terminal_ledger(lakehouse, self.ready_contracts, now=NOW)

        replay = valid_ledger(self.ready_contracts)
        replay["terminalEvidence"]["replay"]["duplicateStageIds"] = []
        replay["terminalEvidenceSha256"] = MODULE.digest(replay["terminalEvidence"])
        with self.assertRaisesRegex(MODULE.CrossChannelAgentError, "replay missing"):
            MODULE.validate_terminal_ledger(replay, self.ready_contracts, now=NOW)


if __name__ == "__main__":
    unittest.main()
