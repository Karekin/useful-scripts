import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "models" / "apply-order-v1.txt"
DQC = ROOT / "tests" / "sql" / "22-legacy-coupon-activity-collect-current-state-contract.sql"
DOMAINS = ("coupon", "activity", "collect")
LAYERS = ("dwd", "dim", "dws", "ads")
EXPECTED_ACTIVITY_SOURCES = {
    "promotion_bargain_activity",
    "promotion_combination_activity",
    "promotion_discount_activity",
    "promotion_point_activity",
    "promotion_reward_activity",
    "promotion_seckill_activity",
}


class LegacyCurrentStateModelsTest(unittest.TestCase):
    def model_path(self, layer, domain):
        return ROOT / "models" / layer / f"{layer}-legacy-{domain}-current.sql"

    def test_all_twelve_models_are_manifested_once_in_dependency_order(self):
        entries = [
            line.strip()
            for line in MANIFEST.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        positions = {entry: index for index, entry in enumerate(entries)}
        for domain in DOMAINS:
            domain_entries = [f"models/{layer}/{layer}-legacy-{domain}-current.sql" for layer in LAYERS]
            for entry in domain_entries:
                self.assertEqual(entries.count(entry), 1)
                self.assertTrue((ROOT / entry).is_file())
            self.assertEqual(sorted(positions[entry] for entry in domain_entries),
                             [positions[entry] for entry in domain_entries])

    def test_every_model_declares_legacy_current_state_semantics(self):
        for layer in LAYERS:
            for domain in DOMAINS:
                text = self.model_path(layer, domain).read_text(encoding="utf-8")
                expected_target = f"yshopping_{layer}.{layer}_legacy_{domain}_current"
                self.assertIn(f"CREATE OR REPLACE VIEW {expected_target}", text)
                self.assertIn("LEGACY_CURRENT_STATE", text)
                self.assertNotIn(f"yshopping_{layer}.{layer}_canonical_", text)

    def test_activity_union_has_the_exact_six_bounded_sources(self):
        text = self.model_path("dwd", "activity").read_text(encoding="utf-8")
        sources = set(re.findall(r"FROM yshopping_ods\.(promotion_[a-z_]+activity)", text))
        self.assertEqual(EXPECTED_ACTIVITY_SOURCES, sources)
        self.assertIn("'promotion_point_activity'", text)
        self.assertRegex(
            text,
            re.compile(r"'POINT'.*?FALSE.*?FALSE, 'LEGACY_CURRENT_STATE_ROW'", re.DOTALL),
        )

    def test_ads_capability_flags_are_explicitly_false(self):
        expected_flags = {
            "coupon": ("canonical_coupon_identity_available", "allocation_event_history_available", "refund_semantics_available"),
            "activity": ("canonical_activity_identity_available", "activity_event_history_available"),
            "collect": ("canonical_member_identity_available", "favorite_event_history_available", "preference_score_available", "reminder_effect_available"),
        }
        for domain, flags in expected_flags.items():
            text = self.model_path("ads", domain).read_text(encoding="utf-8")
            for flag in flags:
                self.assertIn(f"FALSE AS {flag}", text)

    def test_dqc_requires_activity_anomaly_exposure_not_source_cleanliness(self):
        text = DQC.read_text(encoding="utf-8")
        self.assertIn("WHERE unexposed_invalid_time_window_count <> 0", text)
        self.assertNotRegex(
            text,
            r"WHERE\s+(?:source_|exposed_)?invalid_time_window_count\s*(?:=|<>|!=|>)\s*0",
        )
        self.assertIn("source_invalid_time_window_count", self.model_path("ads", "activity").read_text(encoding="utf-8"))
        self.assertIn("exposed_invalid_time_window_count", self.model_path("ads", "activity").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
