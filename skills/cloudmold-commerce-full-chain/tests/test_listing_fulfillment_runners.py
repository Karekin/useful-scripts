import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


SKILL_DIR = Path(__file__).parents[1]
SCRIPTS = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HAPPY = load("canonical_listing_fulfillment_runner")
CANCEL = load("canonical_order_cancellation_runner")
VERTICAL = load("yshopping_listing_fulfillment_vertical_runner")


class FakeClient:
    def __init__(self):
        self.token = "must-never-enter-ledger"

    def request(self, method, route, payload):
        return {"operationId": 7, "duplicate": False}


class ListingFulfillmentRunnerUnitTest(unittest.TestCase):
    def test_happy_plan_locks_governed_listing_and_fulfillment_operations(self):
        plan = HAPPY.scenario_plan()
        self.assertEqual(len(plan), 23)
        self.assertEqual(
            [step["operation"] for step in plan[:6]],
            ["CREATE_DRAFT", "SUBMIT", "PASS_COMPLETION", "APPROVE_BUSINESS",
             "APPROVE_RISK", "PUBLISH"],
        )
        self.assertIn("SHIP_WITH_FULFILLMENT", [step["operation"] for step in plan])
        self.assertIn("COMPLETE_AFTER_DELIVERY", [step["operation"] for step in plan])
        self.assertEqual(plan[-1]["expected"], "RETURNED/v7")

    def test_cancellation_plan_releases_before_cancel_and_never_plans_money_or_fulfillment(self):
        plan = CANCEL.scenario_plan()
        self.assertEqual(len(plan), 12)
        operations = [step["operation"] for step in plan]
        self.assertLess(operations.index("RELEASE"), operations.index("CANCEL"))
        self.assertFalse(any(step["domain"] in {"payment", "fulfillment"} for step in plan))
        self.assertEqual(plan[-2]["expected"], "10/0/10/v3")
        self.assertEqual(plan[-1]["expected"], "CANCELLED/v3")

    def test_listing_and_order_payloads_preserve_exact_offer_contract(self):
        listing = HAPPY.listing_create_payload("runner01", 1, "sku-1", "spu-1")
        self.assertEqual(listing["channelCode"], "YSHOPPING_INTERNAL")
        self.assertEqual(listing["offers"], [{
            "canonicalSkuId": "sku-1",
            "priceMinor": 19900,
            "currencyCode": "CNY",
            "enabled": True,
            "externalOfferId": "internal-offer:runner01",
        }])
        order = HAPPY.place_from_listing_payload("runner01", 8, "sku-1", "listing-1", "offer-1")
        self.assertEqual(order["operation"], "PLACE_FROM_LISTING")
        self.assertEqual(order["items"][0]["listingId"], "listing-1")
        self.assertEqual(order["items"][0]["listingOfferId"], "offer-1")
        self.assertEqual(order["items"][0]["unitPriceMinor"], 19900)

    def test_listing_publication_start_is_never_after_safe_local_test_cutoff(self):
        listing = HAPPY.listing_create_payload("ycan-001", 1, "sku-1", "spu-1")
        self.assertLessEqual(listing["publishStartAt"], "2026-06-30T00:00:00Z")
        self.assertGreater(HAPPY.event_time("ycan-001", 1), listing["publishStartAt"])

    def test_inventory_release_keeps_exact_trade_order_identity(self):
        payload = HAPPY.inventory_payload(
            "runner01", 11, "RELEASE", "sku-1", "warehouse-1", "owner-1",
            "2.000000", "TRADE_ORDER", "order-1", "item-1", "ORDER-1", "reservation-1",
        )
        self.assertEqual(payload["businessType"], "TRADE_ORDER")
        self.assertEqual(payload["businessId"], "order-1")
        self.assertEqual(payload["businessItemId"], "item-1")
        self.assertEqual(payload["reservationId"], "reservation-1")
        self.assertNotIn("runId", payload)

    def test_fulfillment_create_freezes_a_versioned_delivery_promise(self):
        payload = HAPPY.fulfillment_create_payload(
            "runner01", 13, "order-1", "item-1", "sku-1", "reservation-1", "warehouse-1"
        )
        self.assertEqual(payload["deliveryPromiseVersionRef"], "LOCAL_TEST_DELIVERY_V1")
        self.assertGreater(payload["promisedDeliveryAt"], payload["occurredAt"])

    def test_active_catalog_ledger_resolves_same_tenant_spu_and_sorted_sku(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.json"
            ledger.write_text(json.dumps({
                "scenario": "canonical-catalog-first-slice-v1",
                "tenant": 1,
                "final": {"catalog_status": "ACTIVE", "spu_id": "spu-1",
                          "sku_ids": ["sku-b", "sku-a"]},
            }), encoding="utf-8")
            args = argparse.Namespace(catalog_ledger=str(ledger), tenant=1, sku_id=None, spu_id=None)
            sku_id, spu_id, resolved = HAPPY.load_catalog_identity(args)
            self.assertEqual((sku_id, spu_id), ("sku-a", "spu-1"))
            self.assertEqual(resolved, str(ledger.resolve()))

            args.sku_id = "sku-b"
            sku_id, spu_id, resolved = HAPPY.load_catalog_identity(args)
            self.assertEqual((sku_id, spu_id), ("sku-b", "spu-1"))
            self.assertEqual(resolved, str(ledger.resolve()))

            args.sku_id = "sku-outside-ledger"
            with self.assertRaisesRegex(HAPPY.ScenarioError, "not proven by --catalog-ledger"):
                HAPPY.load_catalog_identity(args)

    def test_credentials_are_not_cli_arguments_and_calls_are_redacted(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            HAPPY.parse_args(["--mode", "plan", "--run-id", "runner01", "--token", "secret"])
        recorder = HAPPY.RunRecorder(FakeClient())
        recorder.call("order", "/route", {"operation": "PLACE", "fixture": "value"})
        encoded = json.dumps(recorder.redacted_calls())
        self.assertNotIn("must-never-enter-ledger", encoded)
        self.assertNotIn("fixture", encoded)
        self.assertNotIn("payload", encoded)

    def test_scenario_contracts_contain_no_secret_values(self):
        for name in ("canonical-listing-fulfillment-first-slice-v1.json",
                     "canonical-order-cancellation-compensation-v1.json",
                     "yshopping-listing-fulfillment-vertical-v1.json"):
            text = (SKILL_DIR / "references" / "scenarios" / name).read_text(encoding="utf-8")
            lowered = text.lower()
            self.assertNotIn("accesskeysecret", lowered)
            self.assertNotIn("bearer ", lowered)
            self.assertNotIn("password\":", lowered)

    def test_vertical_plan_and_child_ids_are_deterministic(self):
        run_ids = VERTICAL.child_run_ids("vertical01")
        self.assertEqual(run_ids, {
            "catalog": "vertical01-cat",
            "projection": "vertical01-proj",
            "commerce_v2": "vertical01-commerce-v2",
        })
        self.assertEqual(len(VERTICAL.scenario_plan()), 8)
        self.assertIn("reconcile-canonical-commerce-v2", VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS)

    def test_vertical_lakehouse_capability_detection_fails_closed(self):
        complete = "usage: lakehousectl {" + "|".join(VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS) + "}"
        self.assertEqual(VERTICAL.parse_lakehouse_capabilities(complete),
                         set(VERTICAL.REQUIRED_LAKEHOUSE_COMMANDS))
        incomplete = complete.replace("reconcile-canonical-commerce-v2", "")
        capabilities = VERTICAL.parse_lakehouse_capabilities(incomplete)
        self.assertNotIn("reconcile-canonical-commerce-v2", capabilities)


if __name__ == "__main__":
    unittest.main()
