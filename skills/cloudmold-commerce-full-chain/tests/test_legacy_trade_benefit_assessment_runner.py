import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "legacy_trade_benefit_assessment_runner.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("legacy_trade_benefit_assessment_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class LegacyTradeBenefitAssessmentRunnerTest(unittest.TestCase):
    def test_command_is_deterministic_and_evidence_backed(self):
        first = RUNNER.command("cmtrade17assess3")
        self.assertEqual(first, RUNNER.command("cmtrade17assess3"))
        self.assertEqual(first["migrationRunId"], RUNNER.migration_run_id("cmtrade17assess3"))
        self.assertEqual(first["policyVersion"], "legacy-trade-benefit-v2")
        self.assertTrue(first["evidenceRef"].startswith("run:"))
        self.assertTrue(first["occurredAt"].endswith("Z"))

    def test_plan_is_assessment_only(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = RUNNER.main(["--mode", "plan", "--run-id", "cmtrade17assess3"])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["stages"], ["ASSESS"])
        self.assertEqual(result["import_writes"], 0)
        self.assertEqual(result["future_gates"],
                         ["MAP_ORDER_ITEMS", "RESOLVE_BENEFIT_VERSIONS", "NAME_FUNDERS"])

    def test_result_validation_requires_exact_fail_closed_conservation(self):
        valid = {
            "sourceOrderCount": 238, "nonDeletedOrderCount": 230, "deletedExcludedCount": 8,
            "noBenefitOrderCount": 104, "benefitEvidencePendingOrderCount": 115,
            "quarantinedOrderCount": 11, "benefitComponentCount": 128,
            "sourceBenefitAmountMinor": 16845818, "componentAmountMinor": 16845818,
            "unresolvedIdentityCount": 128, "unresolvedFundingCount": 128,
            "importAllowedComponentCount": 0, "productionMigrationEnabled": False,
            "status": RUNNER.EXPECTED_STATUS, "sourceSnapshotHash": "a" * 64,
        }
        RUNNER.validate_result(valid)
        with self.assertRaises(RUNNER.ScenarioError):
            RUNNER.validate_result({**valid, "importAllowedComponentCount": 1})
        with self.assertRaises(RUNNER.ScenarioError):
            RUNNER.validate_result({**valid, "componentAmountMinor": 16845817})


if __name__ == "__main__":
    unittest.main()
