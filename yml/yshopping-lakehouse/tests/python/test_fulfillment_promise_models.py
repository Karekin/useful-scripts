import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = json.loads((ROOT / "contracts/event-manifest-v1.json").read_text(encoding="utf-8"))


class FulfillmentPromiseModelsTest(unittest.TestCase):
    def test_fulfillment_promise_contract_is_registered(self):
        versions = MANIFEST["events"]["fulfillment.status.changed"]["versions"]
        self.assertTrue(any(version["schema_version"] == 3 for version in versions))

    def test_fulfillment_promise_models_freeze_deadline_without_procurement_mix(self):
        dwd = (ROOT / "models/dwd/dwd-canonical-fulfillment-status-event.sql").read_text(encoding="utf-8")
        dws = (ROOT / "models/dws/dws-canonical-fulfillment-promise-current.sql").read_text(
            encoding="utf-8"
        )
        ads = (ROOT / "models/ads/ads-canonical-fulfillment-promise-readiness.sql").read_text(
            encoding="utf-8"
        )
        metrics = (ROOT / "models/ads/ads-canonical-fulfillment-promise-metrics.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("delivery_promise_version_ref", dwd)
        self.assertIn("promised_delivery_at", dws)
        self.assertIn("PROMISED_DELIVERED_ON_TIME", ads)
        self.assertIn("fulfillment_on_time_delivery_rate", metrics)
        self.assertIn("buyer_delivery_promise_hit_rate", metrics)
        self.assertNotIn("procurement", dws.lower())
        self.assertNotIn("otif", ads.lower())

    def test_dqc_covers_promise_pair_and_on_time_readiness(self):
        dqc = (ROOT / "tests/sql/42-canonical-fulfillment-promise-contract.sql").read_text(
            encoding="utf-8"
        )
        for check in (
            "fulfillment_promise_pair_incomplete",
            "fulfillment_promise_frozen_after_deadline",
            "fulfillment_promise_on_time_state_invalid",
            "fulfillment_promise_metric_rate_mismatch",
        ):
            self.assertIn(check, dqc)


if __name__ == "__main__":
    unittest.main()
