import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "erp_scenario_runner.py"
SPEC = importlib.util.spec_from_file_location("erp_scenario_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class RunnerUnitTest(unittest.TestCase):
    def test_run_id_rejects_unsafe_path_text(self):
        for value in ("short", "../escape", "contains space", "中文编号"):
            with self.subTest(value=value), self.assertRaises(RUNNER.ScenarioError):
                RUNNER.require_run_id(value)

    def test_plan_is_non_mutating_and_declares_cleanup(self):
        plan = RUNNER.scenario_plan("20260712-test")
        self.assertEqual(plan[0]["step"], "preflight")
        self.assertTrue(any(step["step"] == "cleanup" for step in plan))
        self.assertIn("run_id=20260712-test", plan[-1]["effect"])

    def test_request_hash_is_stable_and_sensitive_to_payload(self):
        first = RUNNER.request_hash("POST", "/x", {"a": 1, "b": 2})
        reordered = RUNNER.request_hash("POST", "/x", {"b": 2, "a": 1})
        changed = RUNNER.request_hash("POST", "/x", {"a": 2, "b": 1})
        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)

    def test_ledger_never_requires_or_stores_token(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            ledger = RUNNER.Ledger(path, {"run_id": "20260712-test", "tenant_id": "1"})
            ledger.record("create", "POST", "/resource", {"name": "fixture"}, 42)
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("token", json.dumps(stored).lower())
            self.assertEqual(stored["entries"][0]["response"], 42)

    def test_status_and_stock_contract_values_are_locked(self):
        self.assertEqual((RUNNER.PROCESS, RUNNER.APPROVE), (10, 20))
        self.assertEqual((RUNNER.PURCHASE_IN, RUNNER.PURCHASE_IN_CANCEL), (70, 71))

    def test_openapi_drift_fails_closed(self):
        with self.assertRaises(RUNNER.ScenarioError):
            RUNNER.verify_openapi({"paths": {}})


if __name__ == "__main__":
    unittest.main()
