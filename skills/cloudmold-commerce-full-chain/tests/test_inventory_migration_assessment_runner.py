import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "canonical_inventory_migration_assessment_runner.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("canonical_inventory_migration_assessment_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class InventoryMigrationAssessmentRunnerTest(unittest.TestCase):
    def test_migration_run_and_command_are_deterministic_and_evidence_backed(self):
        first = RUNNER.command("cmig15assess")
        second = RUNNER.command("cmig15assess")
        self.assertEqual(first, second)
        self.assertEqual(first["migrationRunId"], RUNNER.migration_run_id("cmig15assess"))
        self.assertTrue(first["evidenceRef"].startswith("run:"))
        self.assertTrue(first["occurredAt"].endswith("Z"))

    def test_plan_is_assess_only_and_declares_future_gates(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = RUNNER.main(["--mode", "plan", "--run-id", "cmig15assess"])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["stages"], ["ASSESS"])
        self.assertEqual(result["opening_writes"], 0)
        self.assertEqual(result["future_gates"], ["QUALIFY", "MIGRATE"])

    def test_result_validation_enforces_counts_and_blocked_expectation(self):
        valid = {"candidateCount": 18, "eligibleCount": 0, "blockedCount": 18,
                 "rejectedCount": 0, "status": "ASSESSED", "sourceSnapshotHash": "a" * 64}
        RUNNER.validate_result(valid, 18, True)
        with self.assertRaises(RUNNER.ScenarioError):
            RUNNER.validate_result({**valid, "blockedCount": 17}, 18, True)


if __name__ == "__main__":
    unittest.main()
