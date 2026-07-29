import json
import unittest
from pathlib import Path


class ReplenishmentLifecycleSkillDefinitionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        skill_root = Path(__file__).resolve().parents[1]
        cls.definition = json.loads(
            (skill_root / "skill-task.json").read_text(encoding="utf-8")
        )

    def test_wraps_the_three_business_children_in_its_own_role_case(self):
        self.assertEqual(self.definition["skill_version"], "1.1.0")
        self.assertEqual(self.definition["workflow_level"], "BUSINESS_ROLE")
        self.assertEqual(self.definition["owner_role"], "replenishment-operator")
        self.assertEqual(
            [step["step_code"] for step in self.definition["steps"]],
            [
                "open_replenishment_day",
                "notice_replenishment_day",
                "claim_replenishment_day",
                "submit_supplier_sourcing",
                "wait_supplier_sourcing",
                "submit_purchase_order",
                "wait_purchase_order",
                "submit_physical_warehouse_cycle",
                "wait_physical_warehouse_cycle",
                "resolve_replenishment_day",
                "verify_replenishment_day_resolved",
            ],
        )

    def test_has_direct_role_writes_and_a_terminal_readback(self):
        writes = [
            step
            for step in self.definition["steps"]
            if step.get("operation_type") == "WRITE"
        ]
        self.assertEqual(len(writes), 4)
        for step in writes:
            self.assertTrue(step["approval_required"])
            self.assertEqual(
                step["capability_id"],
                "capability.cloudmold.operationsintelligence."
                "operations-intelligence-command.execute.v1",
            )
            self.assertEqual(
                step["arguments"][0]["$overrides"]["/idempotencyKey"],
                "$task.stepIdempotencyKey",
            )

        terminal = self.definition["steps"][-1]
        self.assertEqual(terminal["step_kind"], "WAIT_CAPABILITY")
        self.assertEqual(
            terminal["wait_success"],
            {"/status": "RESOLVED", "/aggregateVersion": 4},
        )
        self.assertEqual(
            terminal["wait_failure"],
            {"/status": ["INVALID", "CLOSED_NO_ACTION"]},
        )

    def test_resolves_only_after_sourcing_procurement_and_physical_cycle(self):
        orders = {
            step["step_code"]: step["step_order"]
            for step in self.definition["steps"]
        }
        self.assertLess(
            orders["claim_replenishment_day"],
            orders["submit_supplier_sourcing"],
        )
        self.assertGreater(
            orders["resolve_replenishment_day"],
            orders["wait_physical_warehouse_cycle"],
        )


if __name__ == "__main__":
    unittest.main()
