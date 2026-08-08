import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))
ENVELOPE = json.loads(
    (ROOT / "contracts/events/domain-event-envelope-v1.schema.json").read_text(encoding="utf-8")
)
ORDER = [
    line.strip()
    for line in (ROOT / "models/apply-order-v1.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]


class CrmModelsTest(unittest.TestCase):
    def test_crm_contracts_are_registered_and_source_system_is_allowed(self):
        expected = {
            "crm.customer.status_changed",
            "crm.customer.owner_changed",
            "crm.lead.status_changed",
            "crm.contact.status_changed",
            "crm.opportunity.stage_changed",
            "crm.follow_up.recorded",
            "crm.sales_contract.status_changed",
        }
        self.assertTrue(expected.issubset(MANIFEST["events"]))
        self.assertIn("cloudmold-crm", ENVELOPE["properties"]["source_system"]["enum"])

    def test_crm_payloads_are_pii_minimized(self):
        forbidden = {
            "mobile",
            "phone",
            "telephone",
            "email",
            "wechat",
            "qq",
            "detail_address",
            "contact_last_content",
            "content",
            "body",
        }
        for path in (ROOT / "contracts/events").glob("crm-*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(forbidden.isdisjoint(schema["properties"]), path.name)
        follow_up_schema = json.loads(
            (ROOT / "contracts/events/crm-follow-up-recorded-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("content_token", follow_up_schema["properties"])
        example = json.loads(
            (ROOT / "contracts/examples/crm-follow-up-recorded-v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("cloudmold-crm", example["source_system"])

    def test_crm_models_are_dependency_ordered(self):
        positions = {entry: index for index, entry in enumerate(ORDER)}
        dwd = "models/dwd/dwd-canonical-crm-event.sql"
        dim = "models/dim/dim-canonical-crm-current.sql"
        dws = "models/dws/dws-canonical-crm-current.sql"
        ads = "models/ads/ads-canonical-crm-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[dwd])
        self.assertLess(positions[dwd], positions[dim])
        self.assertLess(positions[dim], positions[dws])
        self.assertLess(positions[dws], positions[ads])
        self.assertLess(
            positions["models/dws/dws-canonical-customer-service-service-metrics-current.sql"],
            positions[dws],
        )

    def test_crm_rollups_expose_portrait_funnel_and_performance_metrics(self):
        dws = (ROOT / "models/dws/dws-canonical-crm-current.sql").read_text(encoding="utf-8")
        ads = (ROOT / "models/ads/ads-canonical-crm-readiness.sql").read_text(encoding="utf-8")
        for needle in (
            "dws_canonical_crm_customer_profile_current",
            "weighted_pipeline_amount_minor",
            "dws_canonical_crm_funnel_current",
            "customer_transfer_in_count",
            "dws_canonical_crm_owner_performance_current",
            "win_rate_basis_points",
        ):
            self.assertIn(needle, dws)
        for needle in (
            "customer_profile_count",
            "funnel_owner_count",
            "performance_owner_count",
            "CANONICAL_CRM_PII_SAFE_PIPELINE_FIRST_SLICE",
        ):
            self.assertIn(needle, ads)

    def test_crm_dqc_covers_orphans_privacy_and_rate_guards(self):
        dqc = (ROOT / "tests/sql/55-canonical-crm-contract.sql").read_text(encoding="utf-8")
        for check in (
            "crm_customer_owner_event_orphan_customer",
            "crm_lead_converted_customer_missing",
            "crm_follow_up_entity_missing",
            "crm_follow_up_raw_locator_leak",
            "crm_owner_performance_rate_invalid",
            "crm_readiness_semantics_invalid",
        ):
            self.assertIn(check, dqc)


if __name__ == "__main__":
    unittest.main()
