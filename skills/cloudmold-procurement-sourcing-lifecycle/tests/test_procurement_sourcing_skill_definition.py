import json
import unittest
from pathlib import Path


class ProcurementSourcingSkillDefinitionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        skill_root = Path(__file__).resolve().parents[1]
        cls.definition = json.loads(
            (skill_root / "skill-task.json").read_text(encoding="utf-8")
        )

    def test_executes_the_complete_canonical_procurement_sourcing_lifecycle(self):
        self.assertEqual(
            "skill.cloudmold.procurement.sourcing-lifecycle.v1",
            self.definition["skill_id"],
        )
        self.assertEqual("procurement-sourcing-operator", self.definition["owner_role"])
        self.assertEqual(
            [
                "purchase_requisition",
                "event_create",
                "event_publish",
                "invite_supplier_a",
                "invite_supplier_b",
                "open_quoting",
                "quotation_a_submit",
                "quotation_b_submit",
                "close_quoting",
                "evaluation_policy_create",
                "evaluation_a_record",
                "evaluation_b_record",
                "award_draft_create",
                "award_submit",
                "award_approve",
                "event_close",
            ],
            [step["step_code"] for step in self.definition["steps"]],
        )

    def test_every_write_uses_the_typed_envelope_and_governed_identity(self):
        steps = self.definition["steps"]
        self.assertEqual(
            "capability.cloudmold.procurement.purchase-requisition-command.create-approved.v1",
            steps[0]["capability_id"],
        )
        self.assertEqual(
            {"$object": "$input.purchaseRequisition.command", "$overrides": {
                "/idempotencyKey": "$task.stepIdempotencyKey",
                "/runId": "$task.runId",
            }},
            steps[0]["arguments"][0],
        )
        for index, step in enumerate(steps):
            with self.subTest(step=step["step_code"]):
                self.assertEqual("WRITE", step["operation_type"])
                self.assertTrue(step["approval_required"])
                self.assertEqual(
                    {"argument_index": 0, "json_pointer": "/idempotencyKey"},
                    step["idempotency_binding"],
                )
                if index > 0:
                    self.assertEqual(
                        "capability.cloudmold.procurement.sourcing-command.execute.v1",
                        step["capability_id"],
                    )
                    self.assertEqual(
                        f"$input.sourcingCommands.{index - 1}.actorPrincipalId",
                        step["arguments"][1],
                    )


if __name__ == "__main__":
    unittest.main()
