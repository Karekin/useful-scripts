import argparse
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest


SKILL_DIR = Path(__file__).parents[1]
SCRIPTS = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORE = load("aftersales_runner_core")
RUNNER = load("canonical_aftersales_runner")
VERTICAL = load("yshopping_aftersales_vertical_runner")
MANIFEST_PATH = SKILL_DIR / "references" / "scenarios" / "aftersales-endpoints-v1.json"


class SequenceClient:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        return next(self.values)


class ObservationLedger:
    def __init__(self):
        self.observations = []
        self.irreversible = None

    def record_observation(self, domain, result):
        self.observations.append((domain, result))

    def mark_irreversible(self, aftersales_id, refund_id):
        self.irreversible = (aftersales_id, refund_id)


class SequenceRecorder:
    def __init__(self, values, terminal):
        self.values = iter(values)
        self.calls = []
        self.client = SequenceClient([terminal])
        self.ledger = ObservationLedger()

    def call(self, domain, endpoint, payload, ambiguity_query=None):
        self.calls.append((domain, endpoint, payload, ambiguity_query))
        return next(self.values)


class AfterSalesRunnerUnitTest(unittest.TestCase):
    def setUp(self):
        self.manifest = CORE.load_endpoint_manifest(MANIFEST_PATH)

    def test_manifest_matches_actual_admin_contract_and_is_fingerprinted(self):
        self.assertEqual(CORE.route(self.manifest, "aftersales_command"),
                         "/admin-api/cloudmold/aftersale/command")
        self.assertEqual(CORE.route(self.manifest, "aftersales_query"),
                         "/admin-api/cloudmold/aftersale/get")
        self.assertEqual(CORE.route(self.manifest, "aftersales_query_by_order_item"),
                         "/admin-api/cloudmold/aftersale/get-by-order-item")
        self.assertEqual(self.manifest["endpoints"]["aftersales_query"]["id_parameter"],
                         "afterSaleId")
        self.assertEqual(self.manifest["operations"]["accept_inspection"],
                         "ACCEPT_INSPECTION")
        self.assertEqual(len(CORE.endpoint_fingerprint(self.manifest)), 64)

    def test_plan_reuses_first_19_steps_and_agent_has_only_six_aftersale_writes(self):
        plan = RUNNER.scenario_plan(self.manifest)
        self.assertEqual(plan[18], {
            "step": 19,
            "domain": "order",
            "operation": "COMPLETE_AFTER_DELIVERY",
            "expected": "COMPLETED/v5",
        })
        client_writes = [step for step in plan if step["domain"] not in {"proof", "safety"}
                         and step["operation"] != "POLL"]
        self.assertEqual(len(client_writes), 25)
        self.assertEqual([step["operation"] for step in client_writes[-6:]], [
            "REQUEST", "APPROVE", "HAND_OVER_RETURN", "MARK_RETURN_IN_TRANSIT",
            "RECEIVE_RETURN", "ACCEPT_INSPECTION",
        ])
        self.assertFalse(any(step["operation"] in {
            "REFUND", "CONFIRM_REFUND", "RETURN", "START_RESOLUTION"
        } for step in plan[19:]))

    def test_entitlement_plan_governs_promotion_lifecycle_and_all_replays(self):
        plan = RUNNER.scenario_plan(self.manifest, benefit_mode="entitlement-backed")
        promotion = [step for step in plan if step["domain"] == "promotion"]
        client_writes = [step for step in plan if step["domain"] not in {"proof", "safety"}
                         and step["operation"] != "POLL"]

        self.assertEqual(len(promotion), 8)
        self.assertEqual([step["expected"] for step in promotion], [
            "DRAFT/v1", "ACTIVE/v2", "DRAFT/v1", "ACTIVE/v2",
            "ISSUED/v1", "AVAILABLE/v2", "RESERVED/v3", "USED/v4",
        ])
        self.assertEqual(len(client_writes), 33)
        self.assertIn("33 immutable duplicates", plan[-2]["expected"])
        self.assertEqual(CORE.route(self.manifest, "promotion_command"),
                         "/admin-api/cloudmold/promotion/command")

    def test_partial_then_full_plan_runs_two_cases_and_replays_thirty_one_writes(self):
        plan = RUNNER.scenario_plan(
            self.manifest, benefit_mode="none", return_plan="partial-then-full")
        client_writes = [step for step in plan if step["domain"] not in {"proof", "safety"}
                         and step["operation"] != "POLL"]

        self.assertEqual(len(client_writes), 31)
        self.assertEqual(sum(step["operation"] == "REQUEST" for step in client_writes), 2)
        self.assertTrue(any(step["operation"] == "VERIFY_PARTIAL" for step in plan))
        self.assertIn("31 immutable duplicates", plan[-2]["expected"])

    def test_multi_line_plan_uses_two_forward_lines_and_replays_thirty_four_writes(self):
        plan = RUNNER.scenario_plan(
            self.manifest, benefit_mode="none", return_plan="multi-line-full")
        client_writes = [step for step in plan if step["domain"] not in {"proof", "safety"}
                         and step["operation"] != "POLL"]

        self.assertEqual(len(client_writes), 34)
        self.assertEqual(sum(step["operation"] == "REQUEST" for step in client_writes), 2)
        self.assertEqual(sum("LINE_1" in step["operation"] for step in client_writes), 3)
        self.assertEqual(sum("LINE_2" in step["operation"] for step in client_writes), 3)
        self.assertIn("34 immutable duplicates", plan[-2]["expected"])

    def test_multi_line_skus_are_distinct_and_derived_from_catalog_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "catalog.json"
            ledger.write_text(json.dumps({
                "final": {"sku_ids": ["sku-1", "sku-2", "sku-3"]}
            }), encoding="utf-8")
            args = SimpleNamespace(second_sku_id=None)

            self.assertEqual(
                RUNNER.resolve_multi_line_skus(args, "sku-1", str(ledger)),
                ["sku-1", "sku-2"],
            )
            args.second_sku_id = "sku-1"
            with self.assertRaisesRegex(Exception, "distinct second canonical SKU"):
                RUNNER.resolve_multi_line_skus(args, "sku-1", str(ledger))

    def test_stacked_entitlement_plan_has_two_exact_lifecycles_and_39_replays(self):
        plan = RUNNER.scenario_plan(self.manifest, benefit_mode="stacked-entitlements")
        promotion = [step for step in plan if step["domain"] == "promotion"]
        client_writes = [step for step in plan if step["domain"] not in {"proof", "safety"}
                         and step["operation"] != "POLL"]

        self.assertEqual(len(promotion), 14)
        self.assertEqual(sum(step["operation"] == "ISSUE_COUPON_ENTITLEMENT"
                             for step in promotion), 2)
        self.assertEqual(sum(step["operation"] == "REDEEM_COUPON_ENTITLEMENT"
                             for step in promotion), 2)
        self.assertEqual(len(client_writes), 39)
        self.assertIn("39 immutable duplicates", plan[-2]["expected"])

    def test_aftersales_payloads_use_strictly_derived_ids_and_required_metadata(self):
        one = RUNNER.aftersales_payload(
            "after01", 20, "REQUEST", "order-completed",
            orderId="order-1", orderItemId="item-1", reason="reason")
        two = RUNNER.aftersales_payload(
            "after01", 20, "REQUEST", "order-completed",
            orderId="order-1", orderItemId="item-1", reason="reason")
        self.assertEqual(one, two)
        self.assertEqual(one["idempotencyKey"], "after01-20-aftersale-request")
        self.assertEqual(one["runId"], "after01")
        self.assertRegex(one["correlationId"], r"^[0-9a-f-]{36}$")
        self.assertRegex(one["causationId"], r"^[0-9a-f-]{36}$")
        self.assertNotIn("paymentId", one)
        self.assertNotIn("inventoryOperationId", one)

    def test_multi_case_return_shipments_use_distinct_deterministic_waybills(self):
        self.assertEqual(RUNNER.return_waybill_no("after01", 20), "RTN-after01")
        self.assertEqual(RUNNER.return_waybill_no("after01", 26), "RTN-after01-26")
        self.assertNotEqual(
            RUNNER.return_waybill_no("after01", 20),
            RUNNER.return_waybill_no("after01", 26),
        )

    def test_atomic_ledger_exists_before_first_request_and_checkpoints_ambiguity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run" / "ledger.json"
            ledger = CORE.AtomicRunLedger(path, {
                "scenario": CORE.SCENARIO_NAME,
                "run_id": "after01",
                "environment": "test",
                "tenant": 1,
            })
            self.assertTrue(path.is_file())
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["status"], "RUNNING")

            class TimeoutClient:
                def request(self, method, route, payload):
                    raise TimeoutError("ambiguous timeout")

            recorder = CORE.CheckpointRecorder(TimeoutClient(), ledger, self.manifest)
            with self.assertRaises(TimeoutError):
                recorder.call("aftersales", "aftersales_command", {
                    "operation": "REQUEST", "idempotencyKey": "after01-20-aftersale-request"
                })
            persisted = json.loads(path.read_text(encoding="utf-8"))
            step = persisted["attempts"][-1]["steps"][-1]
            self.assertEqual(step["status"], "AMBIGUOUS")
            self.assertIn("Do not retry blindly", step["recovery"])
            self.assertNotIn("token", path.read_text(encoding="utf-8").lower())

    def test_request_timeout_recovers_once_by_exact_order_item_without_second_write(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = CORE.AtomicRunLedger(Path(directory) / "ledger.json", {
                "scenario": CORE.SCENARIO_NAME,
                "run_id": "after01",
                "environment": "test",
                "tenant": 1,
            })

            class RecoveringClient:
                def __init__(self):
                    self.calls = []
                    self.post_count = 0

                def request(self, method, path, payload=None):
                    self.calls.append((method, path, payload))
                    if method == "POST":
                        self.post_count += 1
                        if self.post_count == 1:
                            raise TimeoutError("response lost")
                        return {"operationId": 91, "afterSaleId": "as-1",
                                "orderId": "order-1", "orderItemId": "item-1",
                                "caseStatus": "REQUESTED", "aggregateVersion": 1,
                                "duplicate": True}
                    return {"afterSaleId": "as-1", "orderId": "order-1",
                            "orderItemId": "item-1", "caseStatus": "REQUESTED",
                            "aggregateVersion": 1, "duplicate": False}

            client = RecoveringClient()
            recorder = CORE.CheckpointRecorder(client, ledger, self.manifest)
            payload = {"operation": "REQUEST", "idempotencyKey": "key-1",
                       "orderId": "order-1", "orderItemId": "item-1"}
            result = recorder.call(
                "aftersales", "aftersales_command", payload,
                ambiguity_query=("/admin-api/cloudmold/aftersale/get-by-order-item"
                                 "?orderId=order-1&orderItemId=item-1"))
            self.assertEqual(result["afterSaleId"], "as-1")
            self.assertEqual([call[0] for call in client.calls], ["POST", "GET"])
            persisted = json.loads(ledger.path.read_text(encoding="utf-8"))
            step = persisted["attempts"][-1]["steps"][-1]
            self.assertEqual(step["status"], "RECOVERED_BY_READ")
            self.assertEqual(len(recorder.calls), 1)
            replay = recorder.replay_all()
            self.assertEqual(len(replay), 1)
            self.assertTrue(replay[0]["result"]["duplicate"])
            self.assertEqual([call[0] for call in client.calls], ["POST", "GET", "POST"])

    def test_request_timeout_recovery_fails_closed_on_conflicting_item(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = CORE.AtomicRunLedger(Path(directory) / "ledger.json", {
                "scenario": CORE.SCENARIO_NAME, "run_id": "after01",
                "environment": "test", "tenant": 1,
            })

            class ConflictingClient:
                def request(self, method, path, payload=None):
                    if method == "POST":
                        raise TimeoutError("response lost")
                    return {"afterSaleId": "as-other", "orderId": "order-1",
                            "orderItemId": "different-item"}

            recorder = CORE.CheckpointRecorder(ConflictingClient(), ledger, self.manifest)
            with self.assertRaises(TimeoutError):
                recorder.call(
                    "aftersales", "aftersales_command",
                    {"operation": "REQUEST", "idempotencyKey": "key-1",
                     "orderId": "order-1", "orderItemId": "item-1"},
                    ambiguity_query=("/admin-api/cloudmold/aftersale/get-by-order-item"
                                     "?orderId=order-1&orderItemId=item-1"))
            persisted = json.loads(ledger.path.read_text(encoding="utf-8"))
            step = persisted["attempts"][-1]["steps"][-1]
            self.assertEqual(step["status"], "AMBIGUOUS")
            self.assertIn("conflicting", step["ambiguity_query_error"])

    def test_poll_is_read_only_and_fails_closed_on_timeout(self):
        ledger = ObservationLedger()
        client = SequenceClient([
            {"caseStatus": "RESOLUTION_PENDING", "resolutionSagaStatus": "RUNNING",
             "resolutionSagaVersion": 3},
            {"caseStatus": "COMPLETED", "resolutionSagaStatus": "COMPLETED",
             "resolutionSagaVersion": 10},
        ])
        values = iter([0, 0, 0])
        terminal, observations = CORE.poll_aftersales(
            client, ledger, self.manifest, "as-1", 1, 0,
            sleep=lambda _: None, monotonic=lambda: next(values))
        self.assertEqual(terminal["caseStatus"], "COMPLETED")
        self.assertEqual(len(observations), 2)
        self.assertTrue(all(call[0] == "GET" for call in client.calls))
        self.assertEqual(client.calls[0][1],
                         "/admin-api/cloudmold/aftersale/get?afterSaleId=as-1")

        timed_out = SequenceClient([{
            "caseStatus": "RESOLUTION_PENDING", "resolutionSagaStatus": "RUNNING"
        }])
        values = iter([0, 2])
        with self.assertRaisesRegex(CORE.ScenarioError, "read-only reconciliation"):
            CORE.poll_aftersales(
                timed_out, ObservationLedger(), self.manifest, "as-1", 1, 0,
                sleep=lambda _: None, monotonic=lambda: next(values))

    def test_aftersales_flow_never_calls_participant_endpoints_and_marks_refund_irreversible(self):
        values = [
            {"afterSaleId": "as-1", "afterSaleItemId": "asi-1",
             "orderId": "order-1", "orderItemId": "item-1",
             "caseStatus": "REQUESTED", "aggregateVersion": 1},
            {"afterSaleId": "as-1", "caseStatus": "APPROVED", "aggregateVersion": 2,
             "returnFulfillmentId": "rf-1", "returnFulfillmentStatus": "CREATED",
             "approvedAmountMinor": 39800, "grossAmountMinor": 39800,
             "benefitAmountMinor": 0, "netAmountMinor": 39800, "currencyCode": "CNY"},
            {"afterSaleId": "as-1", "caseStatus": "APPROVED", "aggregateVersion": 2,
             "returnFulfillmentId": "rf-1", "returnFulfillmentStatus": "HANDED_OVER",
             "returnShipmentId": "rs-1"},
            {"afterSaleId": "as-1", "caseStatus": "APPROVED", "aggregateVersion": 2,
             "returnFulfillmentStatus": "IN_TRANSIT"},
            {"afterSaleId": "as-1", "caseStatus": "APPROVED", "aggregateVersion": 2,
             "returnFulfillmentStatus": "RECEIVED"},
            {"afterSaleId": "as-1", "caseStatus": "RESOLUTION_PENDING", "aggregateVersion": 3,
             "returnFulfillmentStatus": "INSPECTION_ACCEPTED", "inspectionId": "inspection-1",
             "resolutionSagaId": "saga-1", "resolutionSagaStatus": "REQUESTED"},
        ]
        terminal = {
            "afterSaleId": "as-1", "afterSaleItemId": "asi-1", "orderItemId": "item-1",
            "caseStatus": "COMPLETED", "aggregateVersion": 4,
            "returnFulfillmentStatus": "INSPECTION_ACCEPTED",
            "resolutionSagaStatus": "COMPLETED", "resolutionSagaVersion": 12,
            "refundStatus": "SUCCEEDED", "approvedAmountMinor": 39800,
            "grossAmountMinor": 39800, "benefitAmountMinor": 0, "netAmountMinor": 39800,
            "benefitReversalStatus": "NOT_REQUIRED", "benefitReversalAmountMinor": 0,
            "currencyCode": "CNY", "paymentRefundTransactionId": 99,
            "inventoryOperationId": 100, "inventoryLedgerTransactionId": 101,
            "orderSettlementEffectId": "effect-1", "orderSettlementVersion": 1,
            "orderReturnFull": True,
        }
        recorder = SequenceRecorder(values, terminal)
        args = SimpleNamespace(run_id="after01", saga_timeout=1, poll_interval=0)
        forward = {"order_id": "order-1", "order_item_id": "item-1",
                   "order": {"payableAmountMinor": 39800,
                             "items": [{"orderItemId": "item-1", "quantity": "2.000000",
                                        "lineAmountMinor": 39800, "discountAmountMinor": 0,
                                        "netAmountMinor": 39800}]}}
        result, _ = RUNNER.execute_aftersales(recorder, args, self.manifest, forward)
        self.assertEqual(result, terminal)
        self.assertEqual(len(recorder.calls), 6)
        self.assertTrue(all(endpoint == "aftersales_command"
                            for _, endpoint, _, _ in recorder.calls))
        request_payload = recorder.calls[0][2]
        self.assertEqual((request_payload["afterSaleType"], request_payload["reasonCode"],
                          request_payload["responsibility"]),
                         ("RETURN_AND_REFUND", "SIZE_NOT_FIT", "BUYER"))
        self.assertNotIn("paymentId", request_payload)
        self.assertNotIn("inventoryOperationId", request_payload)
        self.assertEqual(request_payload["requestedQuantity"], "2.000000")
        self.assertEqual(recorder.ledger.irreversible, ("as-1", 99))
        self.assertEqual(
            recorder.calls[0][3],
            "/admin-api/cloudmold/aftersale/get-by-order-item?orderId=order-1&orderItemId=item-1")

    def test_partial_case_uses_incremental_money_and_does_not_terminalize_order(self):
        values = [
            {"afterSaleId": "as-part", "afterSaleItemId": "asi-part",
             "orderId": "order-1", "orderItemId": "item-1",
             "caseStatus": "REQUESTED", "aggregateVersion": 1},
            {"caseStatus": "APPROVED", "aggregateVersion": 2,
             "returnFulfillmentId": "rf-part", "returnFulfillmentStatus": "CREATED",
             "approvedAmountMinor": 19900, "grossAmountMinor": 19900,
             "benefitAmountMinor": 0, "netAmountMinor": 19900, "currencyCode": "CNY"},
            {"caseStatus": "APPROVED", "aggregateVersion": 2,
             "returnFulfillmentId": "rf-part", "returnFulfillmentStatus": "HANDED_OVER",
             "returnShipmentId": "rs-part"},
            {"caseStatus": "APPROVED", "aggregateVersion": 2,
             "returnFulfillmentStatus": "IN_TRANSIT"},
            {"caseStatus": "APPROVED", "aggregateVersion": 2,
             "returnFulfillmentStatus": "RECEIVED"},
            {"caseStatus": "RESOLUTION_PENDING", "aggregateVersion": 3,
             "returnFulfillmentStatus": "INSPECTION_ACCEPTED", "inspectionId": "inspection-part",
             "resolutionSagaId": "saga-part", "resolutionSagaStatus": "REQUESTED"},
        ]
        terminal = {
            "afterSaleId": "as-part", "afterSaleItemId": "asi-part", "orderItemId": "item-1",
            "caseStatus": "COMPLETED", "aggregateVersion": 4,
            "returnFulfillmentStatus": "INSPECTION_ACCEPTED",
            "resolutionSagaStatus": "COMPLETED", "resolutionSagaVersion": 8,
            "refundStatus": "SUCCEEDED", "approvedAmountMinor": 19900,
            "grossAmountMinor": 19900, "benefitAmountMinor": 0, "netAmountMinor": 19900,
            "benefitReversalStatus": "NOT_REQUIRED", "benefitReversalAmountMinor": 0,
            "currencyCode": "CNY", "paymentRefundTransactionId": 199,
            "inventoryOperationId": 200, "inventoryLedgerTransactionId": 201,
            "orderSettlementEffectId": "effect-part", "orderSettlementVersion": 1,
            "orderReturnFull": False,
        }
        recorder = SequenceRecorder(values, terminal)
        args = SimpleNamespace(run_id="after01", saga_timeout=1, poll_interval=0)
        forward = {"order_id": "order-1", "order_item_id": "item-1",
                   "order": {"payableAmountMinor": 39800,
                             "items": [{"orderItemId": "item-1", "quantity": "2.000000",
                                        "lineAmountMinor": 39800, "discountAmountMinor": 0,
                                        "netAmountMinor": 39800}]}}

        result, _ = RUNNER.execute_aftersales(
            recorder, args, self.manifest, forward,
            requested_quantity=RUNNER.Decimal("1"), expect_full=False)

        self.assertFalse(result["orderReturnFull"])
        self.assertEqual(recorder.calls[0][2]["requestedQuantity"], "1")
        self.assertEqual(recorder.ledger.irreversible, ("as-part", 199))

    def test_existing_order_evidence_runs_only_six_aftersale_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "completed.json"
            path.write_text(json.dumps({
                "scenario": RUNNER.EXISTING_ORDER_EVIDENCE_SCENARIO,
                "environment": "test", "tenant": 1,
                "canonical_sku_id": "sku-1", "canonical_spu_id": "spu-1",
                "final": {
                    "listing": {"listingId": "listing-1", "currentStatus": "PUBLISHED",
                                "aggregateVersion": 6},
                    "order": {"orderId": "order-1", "currentStatus": "COMPLETED",
                              "aggregateVersion": 5,
                              "items": [{"orderItemId": "item-1",
                                         "canonicalSkuId": "sku-1"}]},
                    "payment": {"paymentId": "payment-1", "currentStatus": "CAPTURED",
                                "aggregateVersion": 1, "capturedAmountMinor": 39800},
                    "fulfillment": {"fulfillmentId": "fulfillment-1",
                                    "currentStatus": "DELIVERED", "aggregateVersion": 4},
                    "inventory": {"onHandQuantity": "8.000000",
                                  "reservedQuantity": "0.000000",
                                  "availableQuantity": "8.000000", "aggregateVersion": 3},
                },
            }), encoding="utf-8")
            args = SimpleNamespace(completed_order_evidence=str(path), tenant=1,
                                   environment="test", flow_mode="existing-order")
            sku, spu, source, forward = RUNNER.resolve_execution_input(args)
            self.assertEqual((sku, spu), ("sku-1", "spu-1"))
            self.assertEqual(source, str(path.resolve()))
            self.assertEqual(forward["order_item_id"], "item-1")
            plan = RUNNER.scenario_plan(self.manifest, "existing-order")
            writes = [step for step in plan if step["domain"] == "aftersales"
                      and step["operation"] != "POLL"]
            self.assertEqual(len(writes), 6)

    def test_manual_review_stops_without_automatic_retry(self):
        client = SequenceClient([{
            "caseStatus": "MANUAL_REVIEW", "lastErrorCode": "PAYMENT_TIMEOUT"
        }])
        with self.assertRaisesRegex(CORE.ScenarioError, "explicit authorization"):
            CORE.poll_aftersales(
                client, ObservationLedger(), self.manifest, "as-1", 1, 0,
                sleep=lambda _: None, monotonic=lambda: 0)
        self.assertEqual(len(client.calls), 1)

    def test_scenario_contracts_are_versioned_secret_free_and_no_destructive_cleanup(self):
        for name in (
            "aftersales-endpoints-v1.json",
            "canonical-aftersales-return-refund-v1.json",
            "canonical-aftersales-completed-order-evidence-v1.json",
            "yshopping-aftersales-vertical-v1.json",
        ):
            path = SKILL_DIR / "references" / "scenarios" / name
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(value)
            lowered = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("accesskeysecret", lowered)
            self.assertNotIn("bearer ", lowered)
            self.assertNotIn('"password":', lowered)
        contract = json.loads((SKILL_DIR / "references" / "scenarios"
                               / "canonical-aftersales-return-refund-v1.json").read_text())
        self.assertIn("never delete", contract["safety"]["cleanup"])
        self.assertIn("read-only", contract["safety"]["cdc_timeout"])

    def test_vertical_child_ids_and_dedicated_reconcile_are_deterministic(self):
        self.assertEqual(VERTICAL.child_run_ids("vertical01"), {
            "catalog": "vertical01-cat",
            "projection": "vertical01-proj",
            "master": "vertical01-master",
            "aftersales": "vertical01-aftersale",
        })
        self.assertIn("reconcile-canonical-aftersales", VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS)
        self.assertIn("submit-event-cdc", VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS)
        self.assertIn("reconcile-canonical-merchant", VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS)
        self.assertIn("reconcile-canonical-warehouse-network",
                      VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS)
        usage = "usage: lakehousectl {" + "|".join(VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS) + "}"
        self.assertEqual(VERTICAL.parse_lakehouse_capabilities(usage),
                         set(VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS))

    def test_aftersales_master_ledger_is_required_and_identity_complete(self):
        with self.assertRaisesRegex(CORE.ScenarioError, "requires --master-ledger"):
            RUNNER.load_master_identity(None, 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({
                "scenario": "canonical-merchant-warehouse-first-slice-v1",
                "status": "SUCCEEDED",
                "tenant": 1,
                "final": {
                    "merchant_status": "ACTIVE", "shop_status": "ACTIVE",
                    "warehouse_status": "ACTIVE", "principal_id": "principal-1",
                    "merchant_id": "merchant-1", "shop_id": "shop-1",
                    "warehouse_id": "warehouse-1", "listing_id": "listing-1",
                },
                "steps": [{
                    "domain": "listing", "operation": "PUBLISH",
                    "result": {
                        "listingId": "listing-1", "currentStatus": "PUBLISHED",
                        "aggregateVersion": 6,
                        "offers": [{"listingOfferId": "offer-1", "enabled": True}],
                    },
                }],
            }), encoding="utf-8")
            master = RUNNER.load_master_identity(str(path), 1)
        self.assertEqual(master["merchant_id"], "merchant-1")
        self.assertEqual(master["shop_id"], "shop-1")
        self.assertEqual(master["principal_id"], "principal-1")
        self.assertEqual(master["warehouse_id"], "warehouse-1")
        self.assertEqual(master["published_listing"]["listingId"], "listing-1")

    def test_aftersales_accepts_deferred_master_and_owns_listing_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({
                "scenario": "canonical-merchant-warehouse-first-slice-v1",
                "status": "SUCCEEDED",
                "tenant": 1,
                "final": {
                    "merchant_status": "ACTIVE", "shop_status": "ACTIVE",
                    "warehouse_status": "ACTIVE", "principal_id": "principal-1",
                    "merchant_id": "merchant-1", "shop_id": "shop-1",
                    "warehouse_id": "warehouse-1", "listing_id": None,
                    "listing_mode": "defer", "listing_status": "DEFERRED_TO_COMMERCE",
                },
                "steps": [],
            }), encoding="utf-8")
            master = RUNNER.load_master_identity(str(path), 1)
        self.assertIsNone(master["listing_id"])
        self.assertIsNone(master["published_listing"])


if __name__ == "__main__":
    unittest.main()
