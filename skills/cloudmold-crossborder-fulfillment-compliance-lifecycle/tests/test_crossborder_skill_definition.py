import json
import unittest
from pathlib import Path


class CrossBorderSkillDefinitionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        skill_root = Path(__file__).resolve().parents[1]
        cls.definition = json.loads(
            (skill_root / "skill-task.json").read_text(encoding="utf-8")
        )

    def test_models_a_complete_role_level_crossborder_main_chain(self):
        expected_codes = [
            "submit_paid_in_transit_order",
            "wait_paid_in_transit_order",
            "create_crossborder_case",
            "assess_trade_compliance",
            "select_ai_recommended_route",
            "approve_compliance_plan",
            "assemble_customs_declaration",
            "validate_order_payment_logistics",
            "book_international_carrier",
            "record_carrier_label",
            "handover_export_shipment",
            "submit_customs_declaration",
            "record_customs_release",
            "record_last_mile_delivery",
            "close_crossborder_case",
            "verify_crossborder_case_closed",
        ]

        self.assertEqual(
            self.definition["skill_id"],
            "skill.cloudmold.crossborder.fulfillment-compliance-lifecycle.v1",
        )
        self.assertEqual(self.definition["workflow_level"], "BUSINESS_ROLE")
        self.assertEqual(self.definition["owner_role"], "crossborder-operations")
        self.assertEqual(self.definition["risk_level"], "R3")
        self.assertEqual(
            [step["step_code"] for step in self.definition["steps"]],
            expected_codes,
        )
        self.assertEqual(
            sum(
                step.get("operation_type") == "WRITE"
                for step in self.definition["steps"]
            ),
            13,
        )

    def test_only_injects_governed_approval_evidence_at_irreversible_gates(self):
        approval_steps = [
            step
            for step in self.definition["steps"]
            if any(
                "$task.approvalEvidenceRef" in str(value)
                for directive in (
                    step.get("arguments")
                    if isinstance(step.get("arguments"), list)
                    else [step.get("arguments")]
                )
                if isinstance(directive, dict)
                for value in directive.get("$overrides", {}).values()
            )
        ]

        self.assertEqual(
            [step["step_code"] for step in approval_steps],
            ["approve_compliance_plan", "submit_customs_declaration"],
        )
        for step in self.definition["steps"]:
            if step.get("operation_type") != "WRITE":
                continue
            directive = step["arguments"][0]
            self.assertEqual(
                directive["$overrides"]["/idempotencyKey"],
                "$task.stepIdempotencyKey",
            )
            self.assertEqual(directive["$overrides"]["/runId"], "$task.runId")
            self.assertEqual(step["arguments"][1], "$input.operatorPrincipalId")

    def test_terminal_readback_requires_closed_released_and_delivered(self):
        terminal = self.definition["steps"][-1]

        self.assertEqual(terminal["step_kind"], "WAIT_CAPABILITY")
        self.assertEqual(terminal["operation_type"], "READ")
        self.assertEqual(
            terminal["capability_id"],
            "capability.cloudmold.crossborder.cross-border-query.get.v1",
        )
        self.assertEqual(
            terminal["wait_success"],
            {
                "/status": "CLOSED",
                "/customsStatus": "RELEASED",
                "/deliveryStatus": "DELIVERED",
            },
        )
        self.assertEqual(terminal["wait_failure"], {"/status": ["FAILED"]})


if __name__ == "__main__":
    unittest.main()
