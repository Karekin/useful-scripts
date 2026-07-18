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


class NewDomainModelsTest(unittest.TestCase):
    def test_all_new_backend_events_have_exact_lakehouse_contracts(self):
        expected = {
            "promotion.campaign.state_changed",
            "promotion.coupon_template.state_changed",
            "promotion.coupon_entitlement.state_changed",
            "promotion.advertising_placement.state_changed",
            "promotion.advertising_interaction.recorded",
            "promotion.advertising_ledger.recorded",
            "promotion.experiment_result.upserted",
            "engagement.favorite.status_changed",
            "engagement.favorite.behavior_recorded",
            "engagement.notification.campaign_status_changed",
            "engagement.notification.delivery_status_changed",
            "engagement.notification.delivery_attempt_recorded",
            "engagement.notification.delivery_receipt_recorded",
            "engagement.community.content_status_changed",
            "engagement.community.interaction_recorded",
            "engagement.community.moderation_status_changed",
            "customer_service.ticket.status_changed",
            "customer_service.message.recorded",
            "customer_service.attachment.recorded",
            "customer_service.buyer_feedback.recorded",
            "customer_service.quality_review.recorded",
            "customer_service.claim.status_changed",
        }
        self.assertTrue(expected.issubset(MANIFEST["events"]))

    def test_customer_service_contracts_are_pii_minimized(self):
        forbidden = {"message_body", "body", "phone", "mobile", "email", "file_url", "object_url"}
        for path in (ROOT / "contracts/events").glob("customer-service-*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            properties = set(schema["properties"])
            self.assertTrue(forbidden.isdisjoint(properties), path.name)
            self.assertNotIn("tenant_id", properties, path.name)
        message = json.loads(
            (ROOT / "contracts/events/customer-service-message-recorded-v1.schema.json")
            .read_text(encoding="utf-8")
        )
        self.assertIn("content_token", message["properties"])
        attachment = json.loads(
            (ROOT / "contracts/events/customer-service-attachment-recorded-v1.schema.json")
            .read_text(encoding="utf-8")
        )
        self.assertIn("object_token", attachment["properties"])
        self.assertIn("content_sha256", attachment["properties"])

    def test_new_models_are_dependency_ordered(self):
        positions = {entry: index for index, entry in enumerate(ORDER)}
        for domain in ("promotion", "engagement", "customer-service"):
            dwd = f"models/dwd/dwd-canonical-{domain}-event.sql"
            dim = f"models/dim/dim-canonical-{domain}-current.sql"
            dws = f"models/dws/dws-canonical-{domain}-current.sql"
            ads = f"models/ads/ads-canonical-{domain}-readiness.sql"
            self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[dwd])
            self.assertLess(positions[dwd], positions[dim])
            self.assertLess(positions[dim], positions[dws])
            self.assertLess(positions[dws], positions[ads])
        self.assertLess(
            positions["models/dws/dws-canonical-promotion-current.sql"],
            positions["models/dws/dws-canonical-marketing-economics-current.sql"],
        )
        self.assertLess(
            positions["models/dws/dws-canonical-marketing-economics-current.sql"],
            positions["models/ads/ads-canonical-marketing-economics.sql"],
        )

    def test_alignment_surfaces_keep_explicit_first_slice_gaps(self):
        alignment = json.loads(
            (ROOT / "contracts/yshopping-model-alignment-v1.json").read_text(encoding="utf-8")
        )
        units = {item["id"]: item for item in alignment["alignment_units"]}
        for unit_id in ("activity", "coupon", "advertising", "collect", "push", "community", "customer_service"):
            unit = units[unit_id]
            self.assertEqual("partial", unit["backend"]["status"])
            self.assertEqual("partial", unit["lakehouse"]["status"])
            self.assertTrue(unit["backend"]["gaps"])
            self.assertTrue(unit["lakehouse"]["gaps"])

    def test_dqc_covers_money_lineage_references_and_pii(self):
        dqc = (
            (ROOT / "tests/sql/23-canonical-promotion-engagement-customer-service-contract.sql").read_text(
                encoding="utf-8"
            )
            + "\n"
            + (ROOT / "tests/sql/42-canonical-marketing-economics-contract.sql").read_text(
                encoding="utf-8"
            )
            + "\n"
            + (ROOT / "tests/sql/42-canonical-customer-service-buyer-csat-contract.sql").read_text(
                encoding="utf-8"
            )
        )
        for check in (
            "coupon_entitlement_missing_ledger_entry",
            "advertising_attribution_without_click",
            "advertising_revenue_without_attribution_link",
            "notification_progressed_without_attempt",
            "customer_service_attachment_orphan_message",
            "customer_service_claim_amount_invalid",
            "customer_service_raw_locator_leak",
            "promotion_roi_exposed_without_baseline",
            "customer_service_buyer_feedback_identity_mismatch",
            "customer_service_service_metrics_fcr_invalid",
        ):
            self.assertIn(check, dqc)


if __name__ == "__main__":
    unittest.main()
