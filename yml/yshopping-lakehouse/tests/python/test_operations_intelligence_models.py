import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))
ORDER = [
    line.strip()
    for line in (ROOT / "models/apply-order-v1.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]


class OperationsIntelligenceModelsTest(unittest.TestCase):
    EVENTS = {
        "operations_intelligence.observation.recorded",
        "operations_intelligence.model_result.recorded",
        "operations_intelligence.clue.recorded",
        "operations_intelligence.clue.reviewed",
        "operations_intelligence.alert.status_changed",
    }

    def test_all_governed_events_are_manifested(self):
        self.assertTrue(self.EVENTS.issubset(MANIFEST["events"]))
        for event_type in self.EVENTS:
            entry = MANIFEST["events"][event_type]
            self.assertEqual(1, entry["schema_version"])
            self.assertTrue((ROOT / "contracts" / entry["payload_schema"]).is_file())
            self.assertTrue((ROOT / "contracts" / entry["example"]).is_file())

    def test_contracts_exclude_raw_and_direct_effect_fields(self):
        forbidden = {
            "title", "description", "content", "prompt", "response", "phone", "email",
            "address", "ip", "device", "business_effect", "automatic_enforcement",
        }
        for path in (ROOT / "contracts/events").glob("operations-intelligence-*.schema.json"):
            properties = json.loads(path.read_text(encoding="utf-8"))["properties"]
            self.assertTrue(forbidden.isdisjoint(properties), path.name)

    def test_model_dependency_order(self):
        positions = {entry: index for index, entry in enumerate(ORDER)}
        dwd = "models/dwd/dwd-canonical-operations-intelligence-event.sql"
        dim = "models/dim/dim-canonical-operations-intelligence-current.sql"
        dws = "models/dws/dws-canonical-operations-intelligence-current.sql"
        ads = "models/ads/ads-canonical-operations-intelligence-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[dwd])
        self.assertLess(positions[dwd], positions[dim])
        self.assertLess(positions[dim], positions[dws])
        self.assertLess(positions[dws], positions[ads])

    def test_visual_ai_target_has_a_governed_replacement(self):
        ads = (ROOT / "models/ads/ads-canonical-operations-intelligence-readiness.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("ads_ai_intelligence_target", ads)
        self.assertIn("automatic_enforcement_enabled", ads)
        self.assertIn("raw_content_stored", ads)

    def test_dqc_covers_review_history_source_and_content_safety(self):
        dqc = (ROOT / "tests/sql/36-canonical-operations-intelligence-contract.sql").read_text(
            encoding="utf-8"
        )
        for check in (
            "operations_intelligence_clue_review_mismatch",
            "operations_intelligence_sensitive_raw_content_leak",
            "operations_intelligence_alert_version_sequence_gap",
            "operations_intelligence_alert_transition_invalid",
            "operations_intelligence_alert_source_invalid",
            "operations_intelligence_automatic_enforcement_enabled",
        ):
            self.assertIn(check, dqc)


if __name__ == "__main__":
    unittest.main()
