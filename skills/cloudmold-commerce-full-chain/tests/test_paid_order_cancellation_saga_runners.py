import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


SKILL_DIR = Path(__file__).parents[1]
SCRIPTS = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PAID = load("canonical_paid_order_cancellation_saga_runner")
VERTICAL = load("yshopping_paid_order_cancellation_saga_vertical_runner")


class SequenceClient:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        return next(self.values)


class PaidOrderCancellationSagaRunnerUnitTest(unittest.TestCase):
    def test_plan_locks_14_client_commands_and_five_internal_proofs(self):
        plan = PAID.scenario_plan()
        operations = [step["operation"] for step in plan]
        client = plan[:14]
        proofs = [step for step in plan if step["domain"] == "proof"]
        self.assertEqual(len(plan), 21)
        self.assertEqual(len(client), 14)
        self.assertEqual(client[-1]["operation"], "START PAID_UNSHIPPED")
        self.assertEqual(len([step for step in proofs if step["operation"] != "REPLAY_ALL_CLIENT_COMMANDS"]), 5)
        self.assertLess(operations.index("CREATE"), operations.index("START PAID_UNSHIPPED"))
        self.assertIn("REPLAY_PAYMENT_REFUND", operations)
        self.assertEqual(plan[-1]["expected"], "all 14 duplicate")

    def test_start_payload_reuses_route_mode_and_derives_owned_aggregate_ids_without_fault_fields(self):
        payload = PAID.saga_start_payload("paidrun01", 14, "order-1")
        self.assertEqual(payload["operation"], "START")
        self.assertEqual(payload["cancellationMode"], "PAID_UNSHIPPED")
        self.assertEqual(payload["orderId"], "order-1")
        self.assertNotIn("paymentId", payload)
        self.assertNotIn("fulfillmentId", payload)
        lowered = {key.lower() for key in payload}
        self.assertFalse(any("fault" in key or "fail" in key or "crash" in key for key in lowered))
        self.assertEqual(PAID.SAGA_COMMAND_ROUTE,
                         "/admin-api/cloudmold/order-cancellation-saga/command")

    def test_internal_payloads_match_backend_keys_and_deterministic_times(self):
        start = PAID.saga_start_payload("paidrun01", 14, "order-1")
        request = PAID.fulfillment_request_replay_payload(
            start, "saga-1", "fulfillment-1", "order-1", "paidrun01")
        finalize = PAID.fulfillment_finalize_replay_payload(
            start, "saga-1", "fulfillment-1", "order-1", "paidrun01")
        refund = PAID.payment_refund_replay_payload(start, "saga-1", "payment-1", "order-1", "paidrun01")
        release = PAID.inventory_release_replay_payload(
            start, "saga-1", "reservation-1", "sku-1", "warehouse-1", "owner-1",
            "order-1", "item-1", "CMO1")
        order = PAID.order_finalize_replay_payload(
            start, "saga-1", "order-1", "payment-1", "fulfillment-1", "99", "paidrun01")
        self.assertEqual(request["idempotencyKey"],
                         "cancel-saga:saga-1:fulfillment:fulfillment-1:request")
        self.assertEqual(finalize["idempotencyKey"],
                         "cancel-saga:saga-1:fulfillment:fulfillment-1:finalize")
        self.assertEqual(refund["idempotencyKey"],
                         "cancel-saga:saga-1:payment:payment-1:refund")
        self.assertEqual(refund["providerTransactionId"],
                         "cancel-saga:saga-1:refund:payment-1")
        self.assertEqual(release["idempotencyKey"], "cancel-saga:saga-1:release:reservation-1")
        self.assertEqual(order["idempotencyKey"], "cancel-saga:saga-1:order-finalize")
        self.assertEqual((request["cancellationStepOrdinal"], finalize["cancellationStepOrdinal"],
                          refund["cancellationStepOrdinal"], release["cancellationStepOrdinal"],
                          order["cancellationStepOrdinal"]), (1, 1, 2, 3, 4))
        self.assertEqual((order["paymentId"], order["fulfillmentId"], order["refundId"]),
                         ("payment-1", "fulfillment-1", "99"))
        self.assertEqual(request["occurredAt"], start["occurredAt"])
        self.assertEqual(finalize["occurredAt"], PAID.add_seconds(start["occurredAt"], 1))
        self.assertEqual(refund["occurredAt"], PAID.add_seconds(start["occurredAt"], 2))
        self.assertEqual(release["occurredAt"], PAID.add_seconds(start["occurredAt"], 3))
        self.assertEqual(order["occurredAt"], PAID.add_seconds(start["occurredAt"], 5))

    def test_start_validation_accepts_fresh_and_restart_replay_with_both_fences(self):
        started = {"status": "REQUESTED", "aggregateVersion": 1, "duplicate": False,
                   "cancellationMode": "PAID_UNSHIPPED", "orderId": "order-1",
                   "paymentId": "payment-1", "fulfillmentId": "fulfillment-1",
                   "paymentStatus": "CAPTURED", "fulfillmentStatus": "FENCED",
                   "expectedFulfillmentCount": 1, "cancelledFulfillmentCount": 0}
        PAID.validate_started_saga(started, "order-1", "payment-1", "fulfillment-1")
        started["duplicate"] = True
        PAID.validate_started_saga(started, "order-1", "payment-1", "fulfillment-1")
        started["fulfillmentStatus"] = "CREATED"
        with self.assertRaisesRegex(PAID.ScenarioError, "initial financial/fulfillment fence"):
            PAID.validate_started_saga(started, "order-1", "payment-1", "fulfillment-1")

    def test_completed_validation_requires_paid_terminal_facts_and_version_nine(self):
        completed = {"status": "COMPLETED", "activeStep": "NONE", "aggregateVersion": 9,
                     "cancellationMode": "PAID_UNSHIPPED", "orderId": "order-1",
                     "paymentId": "payment-1", "fulfillmentId": "fulfillment-1",
                     "orderStatusAtRequest": "PAYMENT_CONFIRMED", "orderVersionAtRequest": 3,
                     "paymentStatus": "REFUNDED", "paymentRefundTransactionId": 99,
                     "fulfillmentStatus": "CANCELLED",
                     "expectedFulfillmentCount": 1, "cancelledFulfillmentCount": 1,
                     "expectedReservationCount": 1, "releasedReservationCount": 1,
                     "items": [{"reservationId": "reservation-1", "status": "RELEASED"}],
                     "completedAt": "2026-07-13T00:00:00Z", "lastErrorCode": None}
        PAID.validate_completed_saga(completed, "order-1", "payment-1", "fulfillment-1", "reservation-1")
        completed["aggregateVersion"] = 8
        with self.assertRaisesRegex(PAID.ScenarioError, "completion/version"):
            PAID.validate_completed_saga(
                completed, "order-1", "payment-1", "fulfillment-1", "reservation-1")

    def test_poll_records_paid_recovery_and_fails_closed_on_manual_review(self):
        client = SequenceClient([
            {"status": "REQUESTED", "activeStep": "CANCEL_FULFILLMENT", "aggregateVersion": 1},
            {"status": "PAYMENT_REFUNDED", "activeStep": "RELEASE_RESERVATIONS", "aggregateVersion": 5},
            {"status": "COMPLETED", "activeStep": "NONE", "aggregateVersion": 9},
        ])
        final, observations = PAID.poll_saga(
            client, "saga-1", 1, 0, sleep=lambda _: None, monotonic=lambda: 0)
        self.assertEqual(final["status"], "COMPLETED")
        self.assertEqual([item["aggregate_version"] for item in observations], [1, 5, 9])
        failed = SequenceClient([{"status": "MANUAL_REVIEW", "lastErrorCode": "RefundTimeout"}])
        with self.assertRaisesRegex(PAID.ScenarioError, "manual review"):
            PAID.poll_saga(failed, "saga-1", 1, 0, sleep=lambda _: None, monotonic=lambda: 0)

    def test_five_internal_proofs_require_duplicate_and_exact_terminal_versions(self):
        client = SequenceClient([
            {"duplicate": True, "currentStatus": "CANCELLATION_PENDING", "aggregateVersion": 2},
            {"duplicate": True, "currentStatus": "CANCELLED", "aggregateVersion": 3,
             "shipmentId": None},
            {"duplicate": True, "currentStatus": "REFUNDED", "aggregateVersion": 2,
             "capturedAmountMinor": 39800, "refundedAmountMinor": 39800},
            {"duplicate": True, "onHandQuantity": 10, "reservedQuantity": 0,
             "availableQuantity": 10, "aggregateVersion": 3},
            {"duplicate": True, "currentStatus": "CANCELLED", "aggregateVersion": 5,
             "cancellationSagaId": "saga-1", "paymentId": "payment-1",
             "fulfillmentId": "fulfillment-1", "refundId": "99", "shipmentId": None},
        ])
        recorder = SimpleNamespace(client=client)
        start = PAID.saga_start_payload("paidrun01", 14, "order-1")
        saga = {"sagaId": "saga-1", "runId": "paidrun01", "paymentRefundTransactionId": 99}
        proofs = PAID.proof_internal_commands(
            recorder, start, saga, "payment-1", "fulfillment-1", "reservation-1",
            "sku-1", "warehouse-1", "owner-1", "order-1", "item-1", "CMO1")
        self.assertEqual(set(proofs), {"fulfillment_request", "fulfillment_finalize",
                                      "payment_refund", "inventory_release", "order_finalize"})
        self.assertEqual(len(client.calls), 5)

    def test_cli_has_no_fault_injection_argument_and_start_only_is_explicit(self):
        args = PAID.parse_args(["--mode", "plan", "--completion-mode", "start-only",
                                "--run-id", "paidrun01", "--sku-id", "sku-1", "--spu-id", "spu-1"])
        self.assertEqual(args.completion_mode, "start-only")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            PAID.parse_args(["--mode", "plan", "--run-id", "paidrun01",
                             "--fail-after-step", "refund"])

    def test_scenario_contract_is_versioned_secret_free_and_reuses_worker_switch(self):
        path = SKILL_DIR / "references" / "scenarios" / "canonical-paid-order-cancellation-saga-v1.json"
        contract = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(contract["cancellation_mode"], "PAID_UNSHIPPED")
        self.assertEqual(contract["restart_recovery"]["worker_switch"],
                         "cloudmold.order-cancellation-saga.enabled")
        lowered = path.read_text(encoding="utf-8").lower()
        self.assertNotIn("accesskeysecret", lowered)
        self.assertNotIn("bearer ", lowered)
        self.assertNotIn('"password":', lowered)

    def test_vertical_requires_dedicated_paid_reconcile(self):
        ids = VERTICAL.child_run_ids("paidvertical01")
        self.assertEqual(ids["paid_cancellation_saga"], "paidvertical01-pcsaga")
        self.assertIn("reconcile-canonical-paid-cancellation-saga",
                      VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS)
        usage = "usage: lakehousectl {" + "|".join(VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS) + "}"
        self.assertEqual(VERTICAL.parse_lakehouse_capabilities(usage),
                         set(VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS))


if __name__ == "__main__":
    unittest.main()
