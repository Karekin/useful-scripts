import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from decimal import Decimal


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "seed_replenishment_proposal.py"
)
SPEC = importlib.util.spec_from_file_location("seed_replenishment_proposal", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SeedReplenishmentProposalTest(unittest.TestCase):

    def test_rotates_scenarios_by_business_date(self):
        document = {
            "scenarios": [
                self.scenario("A", "sku-a"),
                self.scenario("B", "sku-b"),
                self.scenario("C", "sku-c"),
            ]
        }
        start = dt.date(2026, 7, 29)
        chosen = [
            MODULE.choose_scenario(document, start + dt.timedelta(days=offset))
            for offset in range(3)
        ]

        self.assertEqual(len({item["canonicalSkuId"] for item in chosen}), 3)

    def test_requires_pool_unless_bounded_proof_is_explicit(self):
        document = {"scenarios": [self.scenario("A", "sku-a")]}

        with self.assertRaisesRegex(ValueError, "at least two scenarios"):
            MODULE.choose_scenario(document, dt.date(2026, 7, 29))
        self.assertEqual(
            MODULE.choose_scenario(
                document, dt.date(2026, 7, 29), allow_single_scenario=True
            )["canonicalSkuId"],
            "sku-a",
        )

    def test_builds_full_domain_chain_ending_in_ready_proposal(self):
        scenario = self.scenario("A", "sku-a")
        commands, ids = MODULE.build_commands(
            162, dt.date(2026, 7, 29), "2026-07-29-A", scenario
        )

        self.assertEqual(
            [command["operation"] for command in commands],
            [
                "CREATE_FORECAST",
                "PUBLISH_FORECAST",
                "CREATE_SUPPLY_PLAN",
                "EVALUATE_PLAN_SCENARIO",
                "SELECT_PLAN_SCENARIO",
                "APPROVE_SUPPLY_PLAN",
                "CREATE_REPLENISHMENT",
                "DECIDE_REPLENISHMENT",
                "PROPOSE_REPLENISHMENT_EXECUTION",
            ],
        )
        proposal = commands[-1]["replenishmentExecutionProposal"]
        self.assertEqual(commands[0]["forecast"]["bucketType"], "DAY")
        self.assertEqual(proposal["recommendationId"], ids["recommendationId"])
        self.assertEqual(proposal["expectedRecommendationVersion"], 2)
        self.assertEqual(proposal["targetType"], "TRANSFER_REQUEST")
        self.assertEqual(proposal["sourceWarehouseId"], 99150105)
        self.assertNotIn("replenishmentConversion", commands[-1])

    def test_adapts_transfer_quantity_to_live_inventory_and_capacity(self):
        scenario = self.scenario("A", "sku-a")
        scenario.update(
            {
                "minimumOrderQuantity": "6",
                "sourceReserveQuantity": "6",
                "maxTransferFraction": "0.25",
                "capacityQuantity": "260",
                "safetyStockQuantity": "24",
            }
        )

        adapted, preflight = MODULE.adapt_transfer_scenario(
            scenario, Decimal("43"), Decimal("57")
        )

        self.assertEqual(adapted["suggestedQuantity"], "6")
        self.assertEqual(adapted["onHandQuantity"], "57")
        self.assertEqual(adapted["inboundQuantity"], "0")
        self.assertEqual(adapted["capacityQuantity"], "203")
        self.assertEqual(
            Decimal(adapted["forecastQuantity"])
            + Decimal(adapted["safetyStockQuantity"])
            - Decimal(adapted["onHandQuantity"]),
            Decimal("6"),
        )
        self.assertEqual(preflight["safeTransferQuantity"], "6")
        self.assertEqual(preflight["sourceAvailableQuantity"], "43")

    def test_rejects_transfer_when_safe_quantity_is_below_minimum(self):
        scenario = self.scenario("A", "sku-a")
        scenario.update(
            {
                "minimumOrderQuantity": "6",
                "sourceReserveQuantity": "6",
                "capacityQuantity": "260",
            }
        )

        with self.assertRaisesRegex(ValueError, "no safe transfer quantity"):
            MODULE.adapt_transfer_scenario(
                scenario, Decimal("11"), Decimal("259")
            )

    @staticmethod
    def scenario(code, sku):
        return {
            "scenarioCode": code,
            "canonicalSkuId": sku,
            "canonicalWarehouseId": "warehouse-a",
            "targetType": "TRANSFER_REQUEST",
            "mappingEvidenceSha256": "a" * 64,
            "sourceWarehouseId": 99150105,
            "targetWarehouseId": 99150107,
            "wmsSkuId": 2,
        }


if __name__ == "__main__":
    unittest.main()
