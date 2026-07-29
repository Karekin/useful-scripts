import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AfterSaleSagaSkillDefinitionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.definition = json.loads(
            (ROOT / "skill-task.json").read_text(encoding="utf-8")
        )
        cls.steps = cls.definition["steps"]
        cls.by_code = {step["step_code"]: step for step in cls.steps}

    def test_is_a_governed_business_role_with_one_daily_terminal_path(self):
        self.assertEqual(self.definition["skill_version"], "1.4.0")
        self.assertEqual(self.definition["workflow_level"], "BUSINESS_ROLE")
        self.assertEqual(self.definition["risk_level"], "R3")
        self.assertEqual(len(self.steps), 21)
        self.assertEqual(
            sum(step.get("operation_type") == "WRITE" for step in self.steps), 20
        )
        self.assertEqual(self.steps[-1]["step_kind"], "WAIT_CAPABILITY")
        self.assertNotIn("listing_create", self.by_code)
        self.assertEqual(self.steps[0]["step_code"], "inventory_receive")
        self.assertEqual(
            self.by_code["order_place"]["arguments"][0]["$object"],
            "$input.commands.7",
        )

    def test_ai_assessment_precedes_independent_warehouse_inspection(self):
        assessment = self.by_code["disposition_assess"]
        inspection = self.by_code["inspection_accept"]
        self.assertEqual(assessment["step_order"], 19)
        self.assertEqual(inspection["step_order"], 20)
        overrides = inspection["arguments"][0]["$overrides"]
        self.assertEqual(
            overrides["dispositionAssessmentId"],
            "$steps.disposition_assess.result.dispositionAssessmentId",
        )
        self.assertEqual(
            overrides["dispositionCode"],
            "$steps.disposition_assess.result.recommendedDisposition",
        )
        self.assertEqual(
            overrides["qualityStatus"],
            "$steps.disposition_assess.result.recommendedQualityStatus",
        )


if __name__ == "__main__":
    unittest.main()
