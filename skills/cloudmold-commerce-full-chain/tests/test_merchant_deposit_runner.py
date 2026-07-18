import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "canonical_merchant_deposit_runner.py"
SPEC = importlib.util.spec_from_file_location("canonical_merchant_deposit_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class MerchantDepositRunnerTest(unittest.TestCase):
    def test_plan_is_read_only_and_locks_exact_thresholds(self):
        self.assertEqual(RUNNER.main(["--mode", "plan", "--run-id", "cmdp001"]), 0)

    def test_context_is_deterministic(self):
        self.assertEqual(RUNNER.scenario_context("cmdp001"), RUNNER.scenario_context("cmdp001"))

    def test_execute_requires_prior_physical_unpublish_ledger(self):
        with self.assertRaisesRegex(RUNNER.ScenarioError, "requires --prior-eligibility-ledger"):
            RUNNER.load_prior_state(None, {}, 1)

    def test_loads_evidence_derived_versions(self):
        master = {"merchant_id": "merchant", "shop_id": "shop", "listing_id": "listing",
                  "listing_offer_id": "offer", "canonical_sku_id": "sku"}
        ledger = {
            "scenario": "canonical-merchant-sales-eligibility-v1", "status": "SUCCEEDED", "tenant": 7,
            "canonical_refs": master,
            "final": {"merchant_status": "ACTIVE", "merchant_version": 6,
                      "listing_status": "PUBLISHED", "listing_version": 10},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            result = RUNNER.load_prior_state(str(path), master, 7)
        self.assertEqual(result["merchant_version"], 6)
        self.assertEqual(result["listing_version"], 10)

    def test_rejects_prior_ledger_for_different_entities(self):
        master = {"merchant_id": "merchant", "shop_id": "shop", "listing_id": "listing",
                  "listing_offer_id": "offer", "canonical_sku_id": "sku"}
        ledger = {
            "scenario": "canonical-merchant-sales-eligibility-v1", "status": "SUCCEEDED", "tenant": 1,
            "canonical_refs": {**master, "merchant_id": "other"},
            "final": {"merchant_status": "ACTIVE", "merchant_version": 6,
                      "listing_status": "PUBLISHED", "listing_version": 10},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            with self.assertRaisesRegex(RUNNER.ScenarioError, "different canonical entities"):
                RUNNER.load_prior_state(str(path), master, 1)

    def test_scenario_spec_forbids_floating_point_money_and_auto_recovery(self):
        spec_path = Path(__file__).parents[1] / "references" / "scenarios" / "canonical-merchant-deposit-v1.json"
        scenario = json.loads(spec_path.read_text(encoding="utf-8"))
        self.assertIn("minor units", scenario["money_contract"])
        forbidden = " ".join(scenario["forbidden_shortcuts"])
        self.assertIn("floating-point money", forbidden)
        self.assertIn("automatic Merchant resume", forbidden)


if __name__ == "__main__":
    unittest.main()
