import json
import unittest
from pathlib import Path


class ProcurementOrderSkillDefinitionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        skill_root = Path(__file__).resolve().parents[1]
        cls.definition = json.loads(
            (skill_root / "skill-task.json").read_text(encoding="utf-8")
        )

    def test_releases_approved_award_then_executes_result_orders(self):
        steps = self.definition["steps"]
        self.assertEqual(11, len(steps))
        self.assertEqual(
            [
                "award_release", "purchase_order_a_submit",
                "purchase_order_a_approve", "purchase_order_a_release",
                "purchase_order_a_dispatch", "purchase_order_a_supplier_confirm",
                "purchase_order_b_submit",
                "purchase_order_b_approve", "purchase_order_b_release",
                "purchase_order_b_dispatch", "purchase_order_b_supplier_confirm",
            ],
            [step["step_code"] for step in steps],
        )
        release = steps[0]
        self.assertEqual(
            "capability.cloudmold.procurement.award-release-command.release-approved-award.v1",
            release["capability_id"],
        )
        self.assertEqual("$input.awardRelease.command", release["arguments"][0]["$object"])

        for index, step in enumerate(steps[1:]):
            with self.subTest(step=step["step_code"]):
                plan_index = 0 if index < 5 else 1
                command_index = index % 5
                self.assertEqual("WRITE", step["operation_type"])
                self.assertTrue(step["approval_required"])
                self.assertEqual(
                    "capability.cloudmold.procurement.procurement-command.execute.v1",
                    step["capability_id"],
                )
                self.assertEqual(
                    f"$input.purchaseOrders.{plan_index}.commands.{command_index}.command",
                    step["arguments"][0]["$object"],
                )
                self.assertEqual(
                    f"$input.purchaseOrders.{plan_index}.commands.{command_index}.actorPrincipalId",
                    step["arguments"][1],
                )

        self.assertNotIn("purchase_order_a_create", [step["step_code"] for step in steps])
        self.assertNotIn("purchase_order_b_create", [step["step_code"] for step in steps])


if __name__ == "__main__":
    unittest.main()
