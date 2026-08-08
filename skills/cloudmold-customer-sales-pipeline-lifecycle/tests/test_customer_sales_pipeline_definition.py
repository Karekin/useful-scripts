import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CustomerSalesPipelineDefinitionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.definition = json.loads((ROOT / "skill-task.json").read_text())

    def test_is_governed_customer_sales_business_role(self):
        self.assertEqual(
            self.definition["skill_id"],
            "skill.cloudmold.crm.customer-sales-pipeline-lifecycle.v1",
        )
        self.assertEqual(self.definition["skill_version"], "1.1.0")
        self.assertEqual(self.definition["workflow_level"], "BUSINESS_ROLE")
        self.assertEqual(self.definition["owner_role"], "customer-sales-operator")
        self.assertEqual(self.definition["risk_level"], "R3")

    def test_runs_a_complete_lead_to_receivables_pipeline(self):
        steps = self.definition["steps"]
        self.assertEqual(len(steps), 19)
        self.assertEqual(
            [step["step_code"] for step in steps],
            [
                "create_lead",
                "record_lead_follow_up",
                "qualify_lead",
                "create_customer",
                "convert_lead",
                "create_primary_contact",
                "create_opportunity",
                "record_opportunity_follow_up",
                "advance_to_proposal",
                "advance_to_negotiation",
                "mark_opportunity_won",
                "verify_won_opportunity",
                "create_sales_contract_draft",
                "submit_sales_contract_approval",
                "verify_active_sales_contract",
                "register_receivable_plan",
                "record_customer_receipt",
                "allocate_customer_receipt",
                "verify_receivables_settled",
            ],
        )
        self.assertEqual(
            steps[11]["wait_success"],
            {"/list/0/stage": "CLOSED_WON", "/list/0/version": 4},
        )
        self.assertEqual(steps[14]["wait_success"], {"/status": "ACTIVE", "/version": 3})
        self.assertEqual(steps[-1]["wait_success"]["/0/receiptUnallocatedMinor"], 0)
        self.assertEqual(
            steps[2]["arguments"][0]["$overrides"]["/lead/expectedVersion"],
            2,
        )
        self.assertEqual(
            steps[4]["arguments"][0]["$overrides"]["/lead/expectedVersion"],
            3,
        )

    def test_every_write_is_approved_and_idempotent(self):
        writes = [
            step for step in self.definition["steps"]
            if step.get("operation_type") == "WRITE"
        ]
        self.assertEqual(len(writes), 16)
        self.assertTrue(all(step["approval_required"] for step in writes))
        self.assertTrue(all("idempotency_binding" in step for step in writes))
        self.assertEqual(
            {step["capability_id"] for step in writes},
            {
                "capability.cloudmold.crm.crm-automation-command.execute.v1",
                "capability.cloudmold.crm.sales-contract-automation-command.execute.v1",
                "capability.cloudmold.finance.receivables-automation-command.register-plan.v1",
                "capability.cloudmold.finance.receivables-automation-command.record-receipt.v1",
                "capability.cloudmold.finance.receivables-automation-command.allocate-receipt.v1",
            },
        )

    def test_actor_is_not_supplied_by_workflow_input(self):
        serialized = json.dumps(self.definition, ensure_ascii=False)
        self.assertNotIn("actorPrincipalId", serialized)
        self.assertNotIn("ownerPrincipalId", serialized)


if __name__ == "__main__":
    unittest.main()
