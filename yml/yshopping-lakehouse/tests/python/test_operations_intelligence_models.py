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
        "risk.intelligence_event_taxonomy.version_published",
        "risk.intelligence_event_taxonomy.retired",
    }

    def test_all_governed_events_are_manifested(self):
        self.assertTrue(self.EVENTS.issubset(MANIFEST["events"]))
        for event_type in self.EVENTS:
            entry = MANIFEST["events"][event_type]
            versions = entry.get("versions", [entry])
            for version in versions:
                self.assertTrue((ROOT / "contracts" / version["payload_schema"]).is_file())
                self.assertTrue((ROOT / "contracts" / version["example"]).is_file())
        self.assertEqual(
            [1, 2],
            [version["schema_version"] for version in
             MANIFEST["events"]["operations_intelligence.observation.recorded"]["versions"]],
        )

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

    def test_intelligence_taxonomy_is_versioned_source_backed_and_never_coerced_to_severity(self):
        dwd = (ROOT / "models/dwd/dwd-canonical-risk-event.sql").read_text(encoding="utf-8")
        dim = (ROOT / "models/dim/dim-canonical-risk-current.sql").read_text(encoding="utf-8")
        dws = (ROOT / "models/dws/dws-canonical-operations-intelligence-current.sql").read_text(
            encoding="utf-8"
        )
        ads = (ROOT / "models/ads/ads-canonical-operations-intelligence-readiness.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("dwd_canonical_intelligence_taxonomy_version_event", dwd)
        self.assertIn("dim_canonical_intelligence_taxonomy_version", dim)
        self.assertIn("next_effective_from", dim)
        self.assertIn("JSON_CONTAINS", dws)
        self.assertIn("taxonomy_reference_valid", dws)
        self.assertIn("GOVERNED_SEMANTICS_READY", ads)
        taxonomy_slice = dwd[
            dwd.index("dwd_canonical_intelligence_taxonomy_version_event"):
            dwd.index("dwd_canonical_risk_signal_event")
        ]
        self.assertNotIn(" AS severity", taxonomy_slice)
        self.assertNotIn(" AS risk_level", taxonomy_slice)

    def test_intelligence_taxonomy_dqc_covers_correction_retirement_lineage_and_observation_time(self):
        dqc = (ROOT / "tests/sql/37-canonical-intelligence-taxonomy-contract.sql").read_text(
            encoding="utf-8"
        )
        for check in (
            "intelligence_taxonomy_definition_version_gap",
            "intelligence_taxonomy_effective_time_invalid",
            "intelligence_taxonomy_head_version_mismatch",
            "intelligence_taxonomy_source_lineage_invalid",
            "classified_observation_reference_invalid",
            "classified_observation_post_retirement",
            "intelligence_taxonomy_automatic_enforcement_enabled",
        ):
            self.assertIn(check, dqc)


if __name__ == "__main__":
    unittest.main()
