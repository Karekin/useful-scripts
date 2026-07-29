import json
import unittest
from pathlib import Path


class BondedCustomsSkillDefinitionTest(unittest.TestCase):

    @staticmethod
    def _path(value, expression):
        current = value
        for segment in expression.split("."):
            current = current[int(segment)] if isinstance(current, list) else current[segment]
        return current

    @staticmethod
    def _pointer(value, pointer):
        current = value
        for raw in pointer.removeprefix("/").split("/"):
            segment = raw.replace("~1", "/").replace("~0", "~")
            current = current[int(segment)] if isinstance(current, list) else current[segment]
        return current

    @classmethod
    def setUpClass(cls):
        skill_root = Path(__file__).resolve().parents[1]
        cls.definition = json.loads(
            (skill_root / "skill-task.json").read_text(encoding="utf-8")
        )

    def test_models_role_level_multi_stage_bonded_customs_chain(self):
        expected_codes = [
            "submit_paid_in_transit_order",
            "wait_paid_in_transit_order",
            "create_bonded_case",
            "assess_eligibility",
            "classify_goods",
            "match_triple_orders",
            "calculate_tax",
            "approve_declaration",
            "submit_declaration",
            "accept_customs",
            "release_bonded_stock",
            "confirm_delivery",
            "close_case",
            "verify_bonded_case_closed",
        ]

        self.assertEqual(
            self.definition["skill_id"],
            "skill.cloudmold.crossborder.bonded-customs-lifecycle.v1",
        )
        self.assertEqual(self.definition["workflow_level"], "BUSINESS_ROLE")
        self.assertEqual(
            self.definition["owner_role"], "bonded-customs-operations"
        )
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
            11,
        )

    def test_starts_from_a_fresh_paid_in_transit_child_order(self):
        submit_child = self.definition["steps"][0]
        wait_child = self.definition["steps"][1]
        create_case = self.definition["steps"][2]

        self.assertEqual(submit_child["step_kind"], "SUBMIT_CHILD")
        self.assertEqual(
            submit_child["child_skill_id"],
            "skill.cloudmold.consumer.in-transit-order-scenario.v1",
        )
        self.assertEqual(submit_child["child_run_id"], "$input.inTransitRunId")
        self.assertEqual(wait_child["step_kind"], "WAIT_CHILD")
        self.assertEqual(
            wait_child["arguments"],
            ["$steps.submit_paid_in_transit_order.result.childTaskId"],
        )
        self.assertEqual(
            create_case["arguments"][0]["$overrides"]["/canonicalOrderId"],
            "$steps.wait_paid_in_transit_order.result.outputs.order_place.orderId",
        )

    def test_write_steps_chain_case_id_and_expected_versions(self):
        write_steps = [
            step
            for step in self.definition["steps"]
            if step.get("operation_type") == "WRITE"
        ]

        for index, step in enumerate(write_steps):
            directive = step["arguments"][0]
            self.assertEqual(
                step["capability_id"],
                "capability.cloudmold.crossborder.bonded-customs-command.execute.v1",
            )
            self.assertEqual(
                directive["$overrides"]["/idempotencyKey"],
                "$task.stepIdempotencyKey",
            )
            self.assertEqual(
                directive["$overrides"]["/runId"],
                "$task.runId",
            )
            self.assertEqual(step["arguments"][1], "$input.operatorPrincipalId")
            if index == 0:
                self.assertNotIn("/caseId", directive["$overrides"])
                self.assertNotIn("/expectedVersion", directive["$overrides"])
                continue
            self.assertEqual(
                directive["$overrides"]["/caseId"],
                "$steps.create_bonded_case.result.caseId",
            )
            self.assertEqual(directive["$overrides"]["/expectedVersion"], index)

    def test_only_irreversible_gates_inject_task_level_approval_evidence(self):
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
            ["approve_declaration", "submit_declaration"],
        )
        for command in self._sample_input()["bondedCommands"]:
            self.assertNotIn("approvalRef", command)

    def test_override_paths_are_valid_without_input_approval_ref(self):
        sample_input = self._sample_input()

        for step in self.definition["steps"]:
            arguments = step.get("arguments")
            directives = arguments if isinstance(arguments, list) else [arguments]
            for directive in directives:
                if not isinstance(directive, dict) or "$object" not in directive:
                    continue
                base_expression = directive["$object"]
                self.assertTrue(base_expression.startswith("$input."))
                base = self._path(sample_input, base_expression.removeprefix("$input."))
                self.assertNotIn("approvalRef", base)
                for path in directive["$overrides"]:
                    if path == "/approvalRef":
                        continue
                    self._pointer(base, path)

    def test_terminal_readback_requires_closed_bonded_delivery_state(self):
        terminal = self.definition["steps"][-1]

        self.assertEqual(terminal["step_kind"], "WAIT_CAPABILITY")
        self.assertEqual(terminal["operation_type"], "READ")
        self.assertEqual(
            terminal["capability_id"],
            "capability.cloudmold.crossborder.bonded-customs-query.get.v1",
        )
        self.assertEqual(
            terminal["wait_success"],
            {
                "/status": "CLOSED",
                "/tripleMatchStatus": "TRIPLE_MATCHED",
                "/customsStatus": "CUSTOMS_ACCEPTED",
                "/bondedReleaseStatus": "BONDED_RELEASED",
                "/deliveryStatus": "DELIVERED",
            },
        )
        self.assertEqual(terminal["wait_failure"], {"/status": ["FAILED"]})

    @staticmethod
    def _sample_input():
        return {
            "inTransitRunId": "bonded-customs-001",
            "operatorPrincipalId": "principal-bonded-ops",
            "consumer": {
                "identityReference": {},
                "listingId": "listing-bonded-001",
                "behaviorCommands": [{}, {}, {}, {}, {}, {}, {}, {}],
                "favoriteCommand": {},
                "commands": [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}],
            },
            "bondedCommands": [
                {
                    "runId": "",
                    "canonicalOrderId": "",
                    "idempotencyKey": "placeholder",
                },
                *[
                    {
                        "runId": "",
                        "caseId": "",
                        "expectedVersion": 0,
                        "idempotencyKey": "placeholder",
                    }
                    for _ in range(10)
                ],
            ],
        }


if __name__ == "__main__":
    unittest.main()
