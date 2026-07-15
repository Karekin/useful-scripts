import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "modelctl"
LOADER = importlib.machinery.SourceFileLoader("modelctl", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODEL = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODEL)


class ModelCtlTest(unittest.TestCase):
    def test_checked_in_manifest_has_every_sql_exactly_once(self):
        order = MODEL.load_order()
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(len(order), len(list((MODEL.ROOT / "models").rglob("*.sql"))))

    def test_duplicate_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "models").mkdir()
            (root / "models" / "one.sql").write_text("SELECT 1;", encoding="utf-8")
            manifest = root / "order.txt"
            manifest.write_text("models/one.sql\nmodels/one.sql\n", encoding="utf-8")
            with self.assertRaisesRegex(MODEL.ModelManifestError, "duplicate"):
                MODEL.load_order(manifest, root)

    def test_missing_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "models").mkdir()
            (root / "models" / "one.sql").write_text("SELECT 1;", encoding="utf-8")
            manifest = root / "order.txt"
            manifest.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(MODEL.ModelManifestError, "missing"):
                MODEL.load_order(manifest, root)

    def test_cancellation_saga_models_follow_their_dependencies(self):
        order = MODEL.load_order()
        positions = {entry: index for index, entry in enumerate(order)}
        self.assertLess(
            positions["models/dwd/dwd-domain-event.sql"],
            positions["models/dwd/dwd-canonical-order-cancellation-saga-event.sql"],
        )
        self.assertLess(
            positions["models/dwd/dwd-canonical-order-cancellation-saga-event.sql"],
            positions["models/dwd/dwd-canonical-order-cancellation-saga-reservation-event.sql"],
        )
        self.assertLess(
            positions["models/dim/dim-canonical-order-cancellation-saga-current.sql"],
            positions["models/dws/dws-canonical-order-cancellation-saga-current.sql"],
        )
        self.assertLess(
            positions["models/dws/dws-canonical-order-cancellation-saga-current.sql"],
            positions["models/ads/ads-canonical-order-cancellation-saga-readiness.sql"],
        )
        self.assertLess(
            positions["models/dws/dws-canonical-fulfillment-item-current.sql"],
            positions["models/dws/dws-canonical-paid-order-cancellation-saga-current.sql"],
        )

    def test_models_extend_manifest_to_one_hundred_thirty_in_dependency_order(self):
        order = MODEL.load_order()
        self.assertEqual(len(order), 130)
        positions = {entry: index for index, entry in enumerate(order)}
        paid_dws = "models/dws/dws-canonical-paid-order-cancellation-saga-current.sql"
        paid_ads = "models/ads/ads-canonical-paid-order-cancellation-saga-readiness.sql"
        self.assertLess(
            positions["models/dim/dim-canonical-order-cancellation-saga-current.sql"],
            positions[paid_dws],
        )
        self.assertLess(positions[paid_dws], positions[paid_ads])
        after_sale_dwd = "models/dwd/dwd-canonical-after-sale-status-event.sql"
        after_sale_dim = "models/dim/dim-canonical-after-sale-current.sql"
        after_sale_dws = "models/dws/dws-canonical-after-sale-resolution-current.sql"
        after_sale_ads = "models/ads/ads-canonical-after-sale-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[after_sale_dwd])
        self.assertLess(positions[after_sale_dwd], positions[after_sale_dim])
        self.assertLess(positions[after_sale_dim], positions[after_sale_dws])
        self.assertLess(positions[after_sale_dws], positions[after_sale_ads])

        migration_qualification_dwd = "models/dwd/dwd-canonical-inventory-migration-qualification-event.sql"
        migration_qualification_dim = "models/dim/dim-canonical-inventory-migration-qualification-current.sql"
        migration_dws = "models/dws/dws-canonical-inventory-migration-run.sql"
        migration_ads = "models/ads/ads-canonical-inventory-migration-readiness.sql"
        self.assertLess(positions[migration_qualification_dwd], positions[migration_qualification_dim])
        self.assertLess(positions[migration_qualification_dim], positions[migration_dws])
        self.assertLess(positions[migration_dws], positions[migration_ads])

        identity_dwd = "models/dwd/dwd-canonical-identity-source-link-event.sql"
        principal_dim = "models/dim/dim-canonical-principal-current.sql"
        merchant_dws = "models/dws/dws-canonical-merchant-shop-current.sql"
        merchant_ads = "models/ads/ads-canonical-merchant-readiness.sql"
        merchant_source_dwd = "models/dwd/dwd-canonical-merchant-source-mapping-event.sql"
        merchant_source_dim = "models/dim/dim-canonical-merchant-source-mapping-current.sql"
        warehouse_dwd = "models/dwd/dwd-canonical-warehouse-entity-status-event.sql"
        warehouse_dim = "models/dim/dim-canonical-warehouse-current.sql"
        warehouse_dws = "models/dws/dws-canonical-warehouse-network-current.sql"
        warehouse_ads = "models/ads/ads-canonical-warehouse-network-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[identity_dwd])
        self.assertLess(positions[identity_dwd], positions[principal_dim])
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[merchant_source_dwd])
        self.assertLess(positions[merchant_source_dwd], positions[merchant_source_dim])
        self.assertLess(positions[principal_dim], positions[merchant_dws])
        self.assertLess(positions[merchant_dws], positions[merchant_ads])
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[warehouse_dwd])
        self.assertLess(positions[warehouse_dwd], positions[warehouse_dim])
        self.assertLess(positions[warehouse_dim], positions[warehouse_dws])
        self.assertLess(positions[warehouse_dws], positions[warehouse_ads])

        listing_saga_dwd = "models/dwd/dwd-canonical-listing-unpublish-saga-event.sql"
        listing_saga_dim = "models/dim/dim-canonical-listing-unpublish-saga-current.sql"
        listing_saga_dws = "models/dws/dws-canonical-listing-unpublish-saga-current.sql"
        listing_saga_ads = "models/ads/ads-canonical-listing-unpublish-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[listing_saga_dwd])
        self.assertLess(positions[listing_saga_dwd], positions[listing_saga_dim])
        self.assertLess(positions["models/dwd/dwd-canonical-merchant-entity-status-event.sql"],
                        positions[listing_saga_dws])
        self.assertLess(positions["models/dwd/dwd-canonical-listing-status-event.sql"],
                        positions[listing_saga_dws])
        self.assertLess(positions[listing_saga_dim], positions[listing_saga_dws])
        self.assertLess(positions[listing_saga_dws], positions[listing_saga_ads])

        deposit_dwd = "models/dwd/dwd-canonical-merchant-deposit-ledger-event.sql"
        deposit_dim = "models/dim/dim-canonical-merchant-deposit-account-current.sql"
        deposit_dws = "models/dws/dws-canonical-merchant-deposit-current.sql"
        deposit_ads = "models/ads/ads-canonical-merchant-deposit-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[deposit_dwd])
        self.assertLess(positions[deposit_dwd], positions[deposit_dim])
        self.assertLess(positions[deposit_dim], positions[deposit_dws])
        self.assertLess(positions[listing_saga_dws], positions[deposit_dws])
        self.assertLess(positions[deposit_dws], positions[deposit_ads])

        lot_lifecycle_dwd = "models/dwd/dwd-canonical-inventory-lot-lifecycle-event.sql"
        lot_mapping_dwd = "models/dwd/dwd-canonical-inventory-lot-source-mapping-event.sql"
        lot_dim = "models/dim/dim-canonical-inventory-lot-current.sql"
        lot_mapping_dim = "models/dim/dim-canonical-inventory-lot-source-mapping-current.sql"
        lot_dws = "models/dws/dws-canonical-inventory-lot-current.sql"
        lot_ads = "models/ads/ads-canonical-inventory-lot-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[lot_lifecycle_dwd])
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[lot_mapping_dwd])
        self.assertLess(positions[lot_lifecycle_dwd], positions[lot_dim])
        self.assertLess(positions[lot_mapping_dwd], positions[lot_mapping_dim])
        self.assertLess(positions["models/dws/dws-canonical-inventory-balance-current.sql"], positions[lot_dws])
        self.assertLess(positions[lot_dim], positions[lot_dws])
        self.assertLess(positions[lot_mapping_dim], positions[lot_dws])
        self.assertLess(positions[lot_dws], positions[lot_ads])

        migration_dwd = "models/dwd/dwd-canonical-inventory-migration-assessment-event.sql"
        migration_dim = "models/dim/dim-canonical-inventory-migration-assessment-current.sql"
        migration_dws = "models/dws/dws-canonical-inventory-migration-run.sql"
        migration_ads = "models/ads/ads-canonical-inventory-migration-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[migration_dwd])
        self.assertLess(positions[migration_dwd], positions[migration_dim])
        self.assertLess(positions[migration_dim], positions[migration_dws])
        self.assertLess(positions[migration_dws], positions[migration_ads])

        pilot_batch_dwd = "models/dwd/dwd-canonical-inventory-migration-pilot-batch-event.sql"
        pilot_item_dwd = "models/dwd/dwd-canonical-inventory-migration-pilot-item-event.sql"
        pilot_batch_dim = "models/dim/dim-canonical-inventory-migration-pilot-batch-current.sql"
        pilot_item_dim = "models/dim/dim-canonical-inventory-migration-pilot-item-current.sql"
        pilot_dws = "models/dws/dws-canonical-inventory-migration-pilot-batch.sql"
        pilot_ads = "models/ads/ads-canonical-inventory-migration-pilot-readiness.sql"
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[pilot_batch_dwd])
        self.assertLess(positions["models/dwd/dwd-domain-event.sql"], positions[pilot_item_dwd])
        self.assertLess(positions[pilot_batch_dwd], positions[pilot_batch_dim])
        self.assertLess(positions[pilot_item_dwd], positions[pilot_item_dim])
        self.assertLess(positions[pilot_batch_dim], positions[pilot_dws])
        self.assertLess(positions[pilot_item_dim], positions[pilot_dws])
        self.assertLess(positions[pilot_dws], positions[pilot_ads])

    def test_shadow_models_follow_historical_admission_and_full_denominator_dependencies(self):
        positions = {entry: index for index, entry in enumerate(MODEL.load_order())}
        pilot_batch = "models/dwd/dwd-canonical-inventory-migration-pilot-batch-event.sql"
        pilot_item = "models/dwd/dwd-canonical-inventory-migration-pilot-item-event.sql"
        window_dwd = "models/dwd/dwd-canonical-inventory-migration-shadow-window-event.sql"
        round_dwd = "models/dwd/dwd-canonical-inventory-migration-shadow-round-event.sql"
        comparison_dwd = "models/dwd/dwd-canonical-inventory-migration-shadow-item-comparison-event.sql"
        window_dim = "models/dim/dim-canonical-inventory-migration-shadow-window-current.sql"
        round_dws = "models/dws/dws-canonical-inventory-migration-shadow-round.sql"
        window_dws = "models/dws/dws-canonical-inventory-migration-shadow-window.sql"
        readiness = "models/ads/ads-canonical-inventory-migration-shadow-readiness.sql"
        self.assertLess(positions[pilot_batch], positions[round_dws])
        self.assertLess(positions[pilot_item], positions[round_dws])
        self.assertLess(positions[window_dwd], positions[window_dim])
        self.assertLess(positions[round_dwd], positions[round_dws])
        self.assertLess(positions[comparison_dwd], positions[round_dws])
        self.assertLess(positions[window_dim], positions[round_dws])
        self.assertLess(positions[round_dws], positions[window_dws])
        self.assertLess(positions[window_dws], positions[readiness])


if __name__ == "__main__":
    unittest.main()
