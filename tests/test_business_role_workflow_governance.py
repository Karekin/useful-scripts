"""Cross-role governance checks for the CloudMold daily operating workflow catalog."""

import json
import unittest
from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"

EXPECTED_OWNER_ROLES = {
    "advertising-settlement-operator",
    "accounts-payable-approver",
    "aftersales-operator",
    "assortment-manager",
    "bonded-customs-operations",
    "campaign-operations",
    "category-operations",
    "consumer-compensation-operator",
    "consumer-experience-operator",
    "crossborder-operations",
    "customer-service-agent",
    "data-ai-operations",
    "finance-operations",
    "growth-experiment-operator",
    "logistics-operations",
    "logistics-settlement-operator",
    "merchant-experience-operator",
    "merchant-managed-growth-operator",
    "merchant-onboarding-operator",
    "merchant-settlement-operator",
    "operations-control",
    "order-exception-operator",
    "partner-marketing-operations",
    "pricing-revenue-operator",
    "procurement-order-operator",
    "procure-to-pay-operator",
    "inventory-count-controller",
    "inventory-transfer-operator",
    "inventory-scrap-operator",
    "inventory-control-manager",
    "supplier-return-operator",
    "supplier-return-accountant",
    "supplier-governance",
    "product-listing-operator",
    "product-operations",
    "production-supervisor",
    "profit-loss-operator",
    "quality-operations",
    "replenishment-operator",
    "risk-operations",
    "procurement-sourcing-operator",
    "supply-chain-operator",
    "supply-planning-manager",
    "synthetic-consumer",
    "warehouse-operations",
}


def load_definitions():
    definitions = {}
    for path in SKILLS_ROOT.glob("*/skill-task.json"):
        definition = json.loads(path.read_text(encoding="utf-8"))
        definitions[definition["skill_id"]] = definition
    return definitions


def business_role_definitions():
    return [
        definition
        for definition in load_definitions().values()
        if definition.get("workflow_level") == "BUSINESS_ROLE"
    ]


def reachable_skill_ids(definitions_by_skill_id):
    pending_skill_ids = [
        definition["skill_id"] for definition in business_role_definitions()
    ]
    reachable = set()
    while pending_skill_ids:
        skill_id = pending_skill_ids.pop()
        if skill_id in reachable:
            continue
        reachable.add(skill_id)
        pending_skill_ids.extend(
            step["child_skill_id"]
            for step in definitions_by_skill_id[skill_id].get("steps", [])
            if step.get("step_kind") == "SUBMIT_CHILD"
        )
    return reachable


class BusinessRoleWorkflowGovernanceTest(unittest.TestCase):

    def test_daily_operating_role_catalog_is_complete_and_unique(self):
        definitions = business_role_definitions()
        owner_roles = [definition.get("owner_role") for definition in definitions]

        self.assertEqual(45, len(definitions))
        self.assertEqual(EXPECTED_OWNER_ROLES, set(owner_roles))
        self.assertEqual(len(owner_roles), len(set(owner_roles)))

    def test_business_role_writes_are_governed_and_child_flows_exist(self):
        definitions_by_skill_id = load_definitions()
        reachable_definitions = [
            definitions_by_skill_id[skill_id]
            for skill_id in reachable_skill_ids(definitions_by_skill_id)
        ]

        for definition in reachable_definitions:
            with self.subTest(skill_id=definition["skill_id"]):
                steps = definition.get("steps", [])
                step_codes = [step.get("step_code") for step in steps]
                self.assertTrue(steps)
                self.assertTrue(all(step_codes))
                self.assertEqual(len(step_codes), len(set(step_codes)))

                writes = [
                    step for step in steps if step.get("operation_type") == "WRITE"
                ]
                submitted_children = [
                    step for step in steps if step.get("step_kind") == "SUBMIT_CHILD"
                ]
                self.assertTrue(
                    all(step.get("approval_required") is True for step in writes)
                )

                for step in submitted_children:
                    self.assertIn(step.get("child_skill_id"), definitions_by_skill_id)

        for definition in business_role_definitions():
            with self.subTest(business_role=definition["owner_role"]):
                self.assertIn(definition.get("risk_level"), {"R2", "R3"})
                self.assertGreater(definition.get("max_attempts", 0), 0)
                self.assertTrue(
                    any(
                        step.get("operation_type") == "WRITE"
                        or step.get("step_kind") == "SUBMIT_CHILD"
                        for step in definition["steps"]
                    )
                )


if __name__ == "__main__":
    unittest.main()
