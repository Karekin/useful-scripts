import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
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


SAGA = load("canonical_order_cancellation_saga_runner")
VERTICAL = load("yshopping_order_cancellation_saga_vertical_runner")


class SequenceClient:
    def __init__(self, values):
        self.values = iter(values)
        self.paths = []

    def request(self, method, path, payload=None):
        self.paths.append((method, path, payload))
        return next(self.values)


class DurableCancellationSagaRunnerUnitTest(unittest.TestCase):
    def test_plan_uses_saga_and_keeps_release_finalize_as_duplicate_proofs(self):
        plan = SAGA.scenario_plan()
        operations = [step["operation"] for step in plan]
        self.assertEqual(len(plan), 15)
        self.assertEqual(operations.count("START"), 1)
        self.assertLess(operations.index("START"), operations.index("POLL"))
        self.assertNotIn("CANCEL", operations)
        self.assertIn("REPLAY_INTERNAL_RELEASE", operations)
        self.assertIn("REPLAY_INTERNAL_FINALIZE", operations)
        self.assertEqual(plan[-1]["expected"], "all 11 duplicate")

    def test_start_payload_contains_no_fault_injection_surface(self):
        payload = SAGA.saga_start_payload("sagarun01", 11, "order-1")
        self.assertEqual(payload["operation"], "START")
        self.assertEqual(payload["orderId"], "order-1")
        lowered = {key.lower() for key in payload}
        self.assertFalse(any("fault" in key or "fail" in key or "crash" in key for key in lowered))
        self.assertNotIn("sagaId", payload)
        self.assertNotIn("expectedVersion", payload)

    def test_start_validation_accepts_fresh_and_recovery_replay(self):
        started = {"status": "REQUESTED", "aggregateVersion": 1, "duplicate": False}
        SAGA.validate_started_saga(started)
        started["duplicate"] = True
        SAGA.validate_started_saga(started)
        started["aggregateVersion"] = 2
        with self.assertRaisesRegex(SAGA.ScenarioError, "START invariant"):
            SAGA.validate_started_saga(started)

    def test_internal_proof_payloads_match_backend_stable_identities(self):
        start = SAGA.saga_start_payload("sagarun01", 11, "order-1")
        release = SAGA.internal_release_replay_payload(
            start, "saga-1", "reservation-1", "sku-1", "warehouse-1", "owner-1",
            "order-1", "item-1", "CMO1")
        self.assertEqual(release["idempotencyKey"], "cancel-saga:saga-1:release:reservation-1")
        self.assertEqual(release["businessType"], "TRADE_ORDER")
        self.assertEqual(release["occurredAt"], SAGA.add_seconds(start["occurredAt"], 1))
        saga = {"sagaId": "saga-1", "runId": "sagarun01", "orderId": "order-1",
                "orderVersionAtRequest": 2, "reason": start["reason"], "items": [{}]}
        finalize = SAGA.internal_finalize_replay_payload(start, saga)
        self.assertEqual(finalize["operation"], "FINALIZE_CANCELLATION")
        self.assertEqual(finalize["expectedVersion"], 3)
        self.assertEqual(finalize["occurredAt"], SAGA.add_seconds(start["occurredAt"], 3))

    def test_poll_records_recovery_then_completes(self):
        client = SequenceClient([
            {"status": "REQUESTED", "activeStep": "RELEASE_RESERVATIONS",
             "attemptCount": 0, "aggregateVersion": 1, "releasedReservationCount": 0},
            {"status": "RETRY_SCHEDULED", "activeStep": "RELEASE_RESERVATIONS",
             "attemptCount": 1, "aggregateVersion": 3, "releasedReservationCount": 0,
             "lastErrorCode": "SocketTimeoutException"},
            {"status": "COMPLETED", "activeStep": "NONE", "attemptCount": 2,
             "aggregateVersion": 7, "releasedReservationCount": 1},
        ])
        final, observations = SAGA.poll_saga(
            client, "saga-1", timeout=1, interval=0, sleep=lambda _: None, monotonic=lambda: 0)
        self.assertEqual(final["status"], "COMPLETED")
        self.assertEqual([item["status"] for item in observations],
                         ["REQUESTED", "RETRY_SCHEDULED", "COMPLETED"])
        self.assertTrue(all(method == "GET" and "sagaId=saga-1" in path and payload is None
                            for method, path, payload in client.paths))

    def test_poll_fails_closed_on_manual_review(self):
        client = SequenceClient([{"status": "MANUAL_REVIEW", "activeStep": "CANCEL_ORDER",
                                  "lastErrorCode": "OrderVersionConflict"}])
        with self.assertRaisesRegex(SAGA.ScenarioError, "manual review"):
            SAGA.poll_saga(client, "saga-1", timeout=1, interval=0,
                           sleep=lambda _: None, monotonic=lambda: 0)

    def test_completed_saga_requires_exact_released_reservation(self):
        saga = {"status": "COMPLETED", "activeStep": "NONE", "orderId": "order-1",
                "orderStatusAtRequest": "INVENTORY_RESERVED", "orderVersionAtRequest": 2,
                "expectedReservationCount": 1, "releasedReservationCount": 1,
                "items": [{"reservationId": "reservation-1", "status": "RELEASED"}],
                "completedAt": "2026-07-12T00:00:00Z", "lastErrorCode": None}
        SAGA.validate_completed_saga(saga, "order-1", "reservation-1")
        saga["items"][0]["status"] = "RETRY_SCHEDULED"
        with self.assertRaisesRegex(SAGA.ScenarioError, "exact reservation"):
            SAGA.validate_completed_saga(saga, "order-1", "reservation-1")

    def test_cli_rejects_fault_injection_arguments(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            SAGA.parse_args(["--mode", "plan", "--run-id", "sagarun01",
                             "--fail-after-step", "release"])

    def test_scenario_contract_contains_no_secret_or_fault_request(self):
        path = SKILL_DIR / "references" / "scenarios" / "canonical-order-cancellation-saga-v1.json"
        contract = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(contract["scenario"], "canonical-order-cancellation-saga-v1")
        self.assertIn("not exposed", contract["fault_injection"])
        lowered = path.read_text(encoding="utf-8").lower()
        self.assertNotIn("accesskeysecret", lowered)
        self.assertNotIn("bearer ", lowered)
        self.assertNotIn('"password":', lowered)

    def test_vertical_routes_saga_child_to_dedicated_lakehouse_reconcile(self):
        ids = VERTICAL.child_run_ids("vertical01")
        self.assertEqual(ids, {"catalog": "vertical01-cat", "projection": "vertical01-proj",
                               "cancellation_saga": "vertical01-csaga"})
        self.assertIn("reconcile-canonical-cancellation-saga",
                      VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS)
        usage = "usage: lakehousectl {" + "|".join(VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS) + "}"
        self.assertEqual(VERTICAL.parse_lakehouse_capabilities(usage),
                         set(VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS))
        self.assertTrue(any("START durable Saga" in step for step in VERTICAL.scenario_plan()))


if __name__ == "__main__":
    unittest.main()
