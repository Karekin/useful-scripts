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


class AiTokenRiskModelsTest(unittest.TestCase):
    def test_all_first_slice_events_are_manifested(self):
        expected = {
            "ai.application.status_changed", "ai.workflow.version.published",
            "ai.workflow.run.status_changed", "ai.model.invocation.recorded",
            "ai.outcome.feedback.recorded", "token_platform.model_offering.status_changed",
            "token_platform.access_credential.status_changed", "token_platform.quota.ledger_posted",
            "token_platform.invocation.usage_recorded", "risk.policy.version_published",
            "risk.signal.detected", "risk.relationship.observed", "risk.cluster.status_changed",
            "risk.review.status_changed", "risk.decision.recorded", "risk.feedback.recorded",
        }
        self.assertTrue(expected.issubset(MANIFEST["events"]))

    def test_sensitive_raw_fields_are_forbidden(self):
        forbidden = {
            "prompt", "response", "graph", "api_key", "secret", "secret_ref", "password",
            "email", "phone", "mobile", "ip", "address", "device", "error_stack",
            "relation_value_start", "relation_value_end",
        }
        patterns = ("ai-*.schema.json", "token-platform-*.schema.json", "risk-*.schema.json")
        for pattern in patterns:
            for path in (ROOT / "contracts/events").glob(pattern):
                schema = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(forbidden.isdisjoint(schema["properties"]), path.name)

    def test_model_dependency_order(self):
        positions = {entry: index for index, entry in enumerate(ORDER)}
        for domain in ("ai-operations", "token-platform", "risk"):
            dwd = f"models/dwd/dwd-canonical-{domain}-event.sql"
            dim = f"models/dim/dim-canonical-{domain}-current.sql"
            dws = f"models/dws/dws-canonical-{domain}-current.sql"
            ads = f"models/ads/ads-canonical-{domain}-readiness.sql"
            self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[dwd])
            self.assertLess(positions[dwd], positions[dim])
            self.assertLess(positions[dim], positions[dws])
            self.assertLess(positions[dws], positions[ads])

    def test_backend_event_vocabulary_is_locked(self):
        def schema(name):
            return json.loads((ROOT / f"contracts/events/{name}").read_text(encoding="utf-8"))

        ai_feedback = schema("ai-outcome-feedback-recorded-v1.schema.json")["properties"]
        self.assertEqual(["QUALITY", "CORRECTNESS", "BUSINESS_OUTCOME", "SAFETY"],
                         ai_feedback["feedback_type"]["enum"])
        self.assertEqual(["POSITIVE", "NEGATIVE", "NEUTRAL", "UNKNOWN"],
                         ai_feedback["outcome_code"]["enum"])

        token_ledger = schema("token-platform-quota-ledger-posted-v1.schema.json")["properties"]
        self.assertEqual(
            ["OPENING", "ALLOCATION", "ADJUSTMENT", "REVERSAL", "EXPIRATION", "INVOCATION_USAGE"],
            token_ledger["entry_type"]["enum"],
        )

        risk_relation = schema("risk-relationship-observed-v1.schema.json")["properties"]
        self.assertEqual(["PHONE", "DEVICE", "IP", "ADDRESS", "PAYMENT_ACCOUNT"],
                         risk_relation["medium_type"]["enum"])
        self.assertEqual("^[0-9a-f]{64}$", risk_relation["medium_token"]["pattern"])
        risk_decision = schema("risk-decision-recorded-v1.schema.json")["properties"]
        self.assertEqual(["DISMISS", "MONITOR", "ESCALATE", "CONFIRM_RISK"],
                         risk_decision["decision_type"]["enum"])
        risk_feedback = schema("risk-feedback-recorded-v1.schema.json")["properties"]
        self.assertEqual(["CONFIRMED", "CORRECTED", "NOT_ACTIONABLE", "NEEDS_REVIEW"],
                         risk_feedback["feedback_type"]["enum"])

    def test_alignment_is_partial_with_explicit_gaps(self):
        alignment = json.loads((ROOT / "contracts/yshopping-model-alignment-v1.json").read_text(encoding="utf-8"))
        units = {item["id"]: item for item in alignment["alignment_units"]}
        for unit_id in ("ai_operations", "token_platform", "user_risk_graph"):
            self.assertEqual("partial", units[unit_id]["backend"]["status"])
            self.assertEqual("partial", units[unit_id]["lakehouse"]["status"])
            self.assertTrue(units[unit_id]["backend"]["gaps"])
            self.assertTrue(units[unit_id]["lakehouse"]["gaps"])

    def test_dqc_covers_tokens_quota_lineage_and_human_review(self):
        dqc = (ROOT / "tests/sql/24-canonical-ai-token-risk-contract.sql").read_text(encoding="utf-8")
        for check in (
            "ai_invocation_token_conservation", "ai_terminal_run_invocation_mismatch",
            "token_usage_without_quota_ledger", "token_credential_sensitive_material_leak",
            "risk_relationship_self_edge", "risk_raw_medium_leak",
            "risk_terminal_review_without_decision", "risk_automatic_enforcement_enabled",
        ):
            self.assertIn(check, dqc)


if __name__ == "__main__":
    unittest.main()
