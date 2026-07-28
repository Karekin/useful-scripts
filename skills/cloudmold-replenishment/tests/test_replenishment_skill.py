import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReplenishmentSkillDefinitionTest(unittest.TestCase):

    def test_skill_definition_is_single_prepare_step(self):
        definition = json.loads((ROOT / "skill-task.json").read_text(encoding="utf-8"))
        self.assertEqual(definition["skill_id"], "skill.cloudmold.supply-planning.prepare.v1")
        self.assertEqual(definition["skill_version"], "1.0.0")
        self.assertEqual(definition["risk_level"], "R2")
        self.assertEqual(len(definition["steps"]), 1)
        step = definition["steps"][0]
        self.assertEqual(step["step_code"], "convert_replenishment")
        self.assertIs(step["approval_required"], True)
        self.assertEqual(
            step["capability_id"],
            "capability.cloudmold.supplyplanning.supply-planning-command.execute.sig-1ca9b1370b9e.v1",
        )
        self.assertEqual(step["arguments"][1], "$input.actorPrincipalId")

    def test_wait_events_truthfully_stop_at_prepare(self):
        wait_events = json.loads((ROOT / "references" / "wait-events.json").read_text(encoding="utf-8"))
        codes = {item["nextWaitingEventCode"] for item in wait_events["events"]}
        self.assertEqual(codes, {"SUPPLIER_CONFIRMATION", "TRANSFER_OUTBOUND"})
        for item in wait_events["events"]:
            self.assertEqual(item["currentDocumentStatus"], "PREPARE")
            self.assertIn("PUTAWAY_COMPLETED", item["followOnEvents"])


if __name__ == "__main__":
    unittest.main()
