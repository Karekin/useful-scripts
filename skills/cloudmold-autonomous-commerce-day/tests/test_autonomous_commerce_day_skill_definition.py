import json
import unittest
from pathlib import Path


class AutonomousCommerceDaySkillDefinitionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        skill_root = Path(__file__).resolve().parents[1]
        cls.definition = json.loads(
            (skill_root / "skill-task.json").read_text(encoding="utf-8")
        )

    def test_is_a_role_level_closed_loop_instead_of_a_composition_shell(self):
        self.assertEqual(self.definition["skill_version"], "1.1.0")
        self.assertEqual(self.definition["workflow_level"], "BUSINESS_ROLE")
        self.assertEqual(self.definition["owner_role"], "operations-control")
        self.assertEqual(
            [step["step_code"] for step in self.definition["steps"]],
            [
                "open_operations_day",
                "notice_operations_day",
                "claim_operations_day",
                "submit_product",
                "wait_product",
                "submit_consumer",
                "wait_consumer",
                "resolve_operations_day",
                "verify_operations_day_resolved",
            ],
        )
        self.assertEqual(
            sum(
                step.get("operation_type") == "WRITE"
                for step in self.definition["steps"]
            ),
            4,
        )

    def test_children_are_bracketed_by_the_operations_business_case(self):
        steps = {step["step_code"]: step for step in self.definition["steps"]}

        self.assertEqual(
            steps["submit_product"]["child_skill_id"],
            "skill.cloudmold.commerce.product-to-listing.v1",
        )
        self.assertEqual(
            steps["submit_consumer"]["child_skill_id"],
            "skill.cloudmold.consumer.shopping-journey.v1",
        )
        self.assertEqual(steps["open_operations_day"]["step_order"], 1)
        self.assertLess(
            steps["claim_operations_day"]["step_order"],
            steps["submit_product"]["step_order"],
        )
        self.assertGreater(
            steps["resolve_operations_day"]["step_order"],
            steps["wait_consumer"]["step_order"],
        )

    def test_every_operations_write_uses_task_idempotency(self):
        writes = [
            step
            for step in self.definition["steps"]
            if step.get("operation_type") == "WRITE"
        ]

        for step in writes:
            self.assertTrue(step["approval_required"])
            self.assertEqual(
                step["capability_id"],
                "capability.cloudmold.operationsintelligence."
                "operations-intelligence-command.execute.v1",
            )
            self.assertEqual(
                step["arguments"][0]["$overrides"]["/runId"],
                "$task.runId",
            )
            self.assertEqual(
                step["arguments"][0]["$overrides"]["/idempotencyKey"],
                "$task.stepIdempotencyKey",
            )

    def test_terminal_readback_requires_the_role_case_to_be_resolved(self):
        terminal = self.definition["steps"][-1]

        self.assertEqual(terminal["step_kind"], "WAIT_CAPABILITY")
        self.assertEqual(
            terminal["capability_id"],
            "capability.cloudmold.operationsintelligence."
            "operations-intelligence-query.get-alert.v1",
        )
        self.assertEqual(
            terminal["wait_success"],
            {"/status": "RESOLVED", "/aggregateVersion": 4},
        )
        self.assertEqual(
            terminal["wait_failure"],
            {"/status": ["INVALID", "CLOSED_NO_ACTION"]},
        )


if __name__ == "__main__":
    unittest.main()
