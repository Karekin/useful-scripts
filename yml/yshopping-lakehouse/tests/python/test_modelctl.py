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

    def test_aftersales_models_extend_manifest_to_sixty_two(self):
        order = MODEL.load_order()
        self.assertEqual(len(order), 62)
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


if __name__ == "__main__":
    unittest.main()
