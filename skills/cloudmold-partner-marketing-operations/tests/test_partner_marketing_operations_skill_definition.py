import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PartnerMarketingOperationsSkillDefinitionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.definition = json.loads((ROOT / "skill-task.json").read_text())

    def test_is_role_level_r3_workflow(self):
        self.assertEqual(
            self.definition["skill_id"],
            "skill.cloudmold.partner-marketing.kol-media-operations.v1",
        )
        self.assertEqual(self.definition["workflow_level"], "BUSINESS_ROLE")
        self.assertEqual(
            self.definition["owner_role"], "partner-marketing-operations"
        )
        self.assertEqual(self.definition["risk_level"], "R3")

    def test_contains_complete_partner_marketing_spine(self):
        steps = self.definition["steps"]
        self.assertEqual(len(steps), 22)
        child_steps = [
            step for step in steps if step.get("step_kind") == "SUBMIT_CHILD"
        ]
        self.assertEqual(
            [step["child_skill_id"] for step in child_steps],
            [
                "skill.cloudmold.commerce.product-to-listing.v1",
                "skill.cloudmold.engagement.promotion-campaign-operations.v1",
                "skill.cloudmold.consumer.shopping-journey.v1",
            ],
        )

    def test_uses_real_consumer_order_and_payment_for_attribution(self):
        reconcile = next(
            step
            for step in self.definition["steps"]
            if step["step_code"] == "reconcile_attribution"
        )
        overrides = reconcile["arguments"][0]["$overrides"]
        self.assertEqual(
            overrides["/attribution/attributedOrderId"],
            "$steps.wait_consumer_validation.result.outputs.order_place.orderId",
        )
        self.assertEqual(
            overrides["/attribution/attributedPaymentId"],
            "$steps.wait_consumer_validation.result.outputs.payment_capture.paymentId",
        )

    def test_waits_for_publication_attribution_and_settlement_terminal(self):
        terminal = self.definition["steps"][-1]
        self.assertEqual(terminal["step_kind"], "WAIT_CAPABILITY")
        self.assertEqual(terminal["wait_success"]["/status"], "SUCCEEDED")
        self.assertEqual(terminal["wait_success"]["/currentStatus"], "CLOSED")
        self.assertTrue(terminal["wait_success"]["/terminal"])
        self.assertEqual(terminal["wait_success"]["/aggregateVersion"], 12)

    def test_enforces_independent_review_and_payment_roles(self):
        by_code = {step["step_code"]: step for step in self.definition["steps"]}
        self.assertEqual(
            by_code["approve_brief"]["arguments"][0]["$overrides"][
                "actorPrincipalId"
            ],
            "$input.independentReviewerPrincipalId",
        )
        self.assertEqual(
            by_code["approve_content"]["arguments"][0]["$overrides"][
                "actorPrincipalId"
            ],
            "$input.independentReviewerPrincipalId",
        )
        self.assertEqual(
            by_code["mark_settlement_paid"]["arguments"][0]["$overrides"][
                "actorPrincipalId"
            ],
            "$input.financePrincipalId",
        )


if __name__ == "__main__":
    unittest.main()
