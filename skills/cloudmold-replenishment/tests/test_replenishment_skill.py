import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReplenishmentSkillDefinitionTest(unittest.TestCase):

    def test_skill_definition_revalidates_proposal_before_governed_conversion(self):
        definition = json.loads((ROOT / "skill-task.json").read_text(encoding="utf-8"))
        self.assertEqual(definition["skill_id"], "skill.cloudmold.supply-planning.prepare.v1")
        self.assertEqual(definition["skill_version"], "1.0.0")
        self.assertEqual(definition["risk_level"], "R2")
        self.assertEqual(len(definition["steps"]), 2)
        resolve_step, conversion_step = definition["steps"]
        self.assertEqual(resolve_step["step_code"], "resolve_execution_proposal")
        self.assertEqual(resolve_step["operation_type"], "READ")
        self.assertIs(resolve_step["approval_required"], False)
        self.assertEqual(resolve_step["arguments"], ["$input.proposalId"])
        self.assertEqual(conversion_step["step_code"], "convert_replenishment")
        self.assertIs(conversion_step["approval_required"], True)
        self.assertEqual(
            conversion_step["capability_id"],
            "capability.cloudmold.supplyplanning.supply-planning-command.execute.sig-1ca9b1370b9e.v1",
        )
        command = conversion_step["arguments"][0]
        self.assertEqual(command["operation"], "CONVERT_REPLENISHMENT")
        self.assertEqual(command["correlationId"], "$input.proposalId")
        self.assertEqual(command["occurredAt"], "$input.occurredAt")
        self.assertEqual(
            command["replenishmentConversion"]["recommendationId"],
            "$steps.resolve_execution_proposal.result.recommendationId",
        )
        self.assertEqual(
            conversion_step["arguments"][1],
            "$steps.resolve_execution_proposal.result.proposedByPrincipalId",
        )

    def test_wait_events_truthfully_stop_at_prepare(self):
        wait_events = json.loads((ROOT / "references" / "wait-events.json").read_text(encoding="utf-8"))
        codes = {item["nextWaitingEventCode"] for item in wait_events["events"]}
        self.assertEqual(codes, {"SUPPLIER_CONFIRMATION", "TRANSFER_OUTBOUND"})
        for item in wait_events["events"]:
            self.assertEqual(item["currentDocumentStatus"], "PREPARE")
            self.assertIn("PUTAWAY_COMPLETED", item["followOnEvents"])


if __name__ == "__main__":
    unittest.main()
