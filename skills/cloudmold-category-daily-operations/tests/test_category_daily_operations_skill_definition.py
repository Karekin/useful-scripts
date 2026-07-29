import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CategoryDailyOperationsSkillDefinitionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.definition = json.loads((ROOT / "skill-task.json").read_text())

    def test_is_a_role_level_r3_workflow(self):
        self.assertEqual(
            self.definition["skill_id"],
            "skill.cloudmold.commerce.category-daily-operations.v1",
        )
        self.assertEqual(self.definition["workflow_level"], "BUSINESS_ROLE")
        self.assertEqual(self.definition["owner_role"], "category-operations")
        self.assertEqual(self.definition["risk_level"], "R3")

    def test_owns_a_business_case_and_terminal(self):
        steps = self.definition["steps"]
        write_steps = [
            step for step in steps if step.get("operation_type") == "WRITE"
        ]
        self.assertEqual(len(steps), 13)
        self.assertEqual(len(write_steps), 4)
        self.assertEqual(
            [step["step_code"] for step in write_steps],
            [
                "open_category_day",
                "notice_category_day",
                "claim_category_day",
                "resolve_category_day",
            ],
        )
        terminal = steps[-1]
        self.assertEqual(terminal["step_kind"], "WAIT_CAPABILITY")
        self.assertEqual(terminal["wait_success"]["/status"], "RESOLVED")
        self.assertEqual(terminal["wait_success"]["/aggregateVersion"], 4)

    def test_contains_four_complete_business_arteries(self):
        child_steps = [
            step for step in self.definition["steps"]
            if step.get("step_kind") == "SUBMIT_CHILD"
        ]
        self.assertEqual(
            [step["child_skill_id"] for step in child_steps],
            [
                "skill.cloudmold.commerce.product-to-listing.v1",
                "skill.cloudmold.growth.experiment-lifecycle.v1",
                "skill.cloudmold.engagement.promotion-campaign-operations.v1",
                "skill.cloudmold.consumer.shopping-journey.v1",
            ],
        )

    def test_consumer_is_bound_to_the_new_listing(self):
        submit = next(
            step for step in self.definition["steps"]
            if step["step_code"] == "submit_consumer_validation"
        )
        overrides = submit["arguments"]["$overrides"]
        self.assertEqual(
            overrides["listingId"],
            "$steps.wait_product_launch.result.outputs.listing_create.listingId",
        )
        self.assertIn("/commands/1/items/0/listingOfferId", overrides)
        self.assertIn("/communityCommands/0/listingId", overrides)


if __name__ == "__main__":
    unittest.main()
