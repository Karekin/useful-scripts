import json
import unittest
from pathlib import Path


class ProductToListingSkillDefinitionTest(unittest.TestCase):

    @staticmethod
    def _path(value, expression):
        current = value
        for segment in expression.split("."):
            current = current[int(segment)] if isinstance(current, list) else current[segment]
        return current

    @staticmethod
    def _pointer(value, pointer):
        current = value
        for raw in pointer.removeprefix("/").split("/"):
            segment = raw.replace("~1", "/").replace("~0", "~")
            current = current[int(segment)] if isinstance(current, list) else current[segment]
        return current

    @classmethod
    def setUpClass(cls):
        cls.skill_root = Path(__file__).resolve().parents[1]
        cls.skill = json.loads((cls.skill_root / "skill.json").read_text(encoding="utf-8"))
        cls.definition = json.loads((cls.skill_root / "skill-task.json").read_text(encoding="utf-8"))

    def test_skill_version_matches_skill_task_version(self):
        self.assertEqual(self.skill["skill_id"], "skill.cloudmold.commerce.product-to-listing.v1")
        self.assertEqual(self.skill["version"], self.definition["skill_version"])
        self.assertEqual(self.definition["risk_level"], "R3")

    def test_step_sequence_and_override_paths_are_valid(self):
        expected_codes = [
            "submit_catalog",
            "wait_catalog",
            "submit_master",
            "wait_master",
            "listing_create",
            "listing_submit",
            "listing_completion",
            "listing_business",
            "listing_risk",
            "listing_publish",
            "listing_channel_receipt",
            "listing_terminal_readback",
        ]
        self.assertEqual([step["step_code"] for step in self.definition["steps"]], expected_codes)
        self.assertEqual(self.definition["steps"][-1]["step_kind"], "WAIT_CAPABILITY")
        self.assertEqual(self.definition["steps"][-1]["operation_type"], "READ")
        self.assertEqual(
            self.definition["steps"][-1]["capability_id"],
            "capability.cloudmold.listing.listing-query.get-listing-terminal-readback.v1",
        )
        self.assertEqual(
            self.definition["steps"][-1]["wait_success"],
            {"/overallResultCode": "CONFIRMED_PUBLISHED"},
        )
        self.assertEqual(
            self.definition["steps"][-1]["wait_failure"],
            {"/overallResultCode": ["CHANNEL_PUBLISH_FAILED"]},
        )

        sample_input = {
            "runIds": {"catalog": "ptl-001-catalog", "master": "ptl-001-master"},
            "catalog": {"definitions": [{}, {}, {}, {}, {}, {}], "lifecycle": [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}]},
            "master": {"erpWarehouseSourceId": 3, "identityReference": {}, "merchantCommands": [{}, {}, {}, {}, {}, {}], "warehouseCommands": [{}, {}, {}, {}, {}, {}, {}], "warehouseReference": {}, "eligibilityAt": "2026-07-27T12:00:00Z"},
            "listing": {
                "commands": [
                    {
                        "merchantId": "",
                        "shopId": "",
                        "canonicalSpuId": "",
                        "publisherRef": "",
                        "offers": [{"canonicalSkuId": ""}, {"canonicalSkuId": ""}, {"canonicalSkuId": ""}, {"canonicalSkuId": ""}, {"canonicalSkuId": ""}, {"canonicalSkuId": ""}],
                        "idempotencyKey": "placeholder"
                    },
                    {"listingId": "", "expectedVersion": 0, "idempotencyKey": "placeholder"},
                    {"listingId": "", "expectedVersion": 0, "idempotencyKey": "placeholder"},
                    {"listingId": "", "expectedVersion": 0, "idempotencyKey": "placeholder"},
                    {"listingId": "", "expectedVersion": 0, "idempotencyKey": "placeholder"},
                    {"listingId": "", "expectedVersion": 0, "publisherRef": "", "idempotencyKey": "placeholder"},
                ]
            },
            "listingReceipt": {
                "idempotencyKey": "placeholder",
                "listingId": "placeholder",
                "expectedVersion": 6,
                "outcome": "CONFIRMED_PUBLISHED",
                "channelListingId": "internal-channel:sample",
                "channelStatus": "ONLINE",
                "confirmedAt": "2026-07-27T12:00:00Z",
                "evidenceRef": "synthetic:yshopping-internal:sample",
                "correlationId": "00000000-0000-0000-0000-000000000000",
                "occurredAt": "2026-07-27T12:00:00Z",
            },
            "readback": {"listingId": "placeholder"},
        }

        for step in self.definition["steps"]:
            arguments = step.get("arguments")
            directives = arguments if isinstance(arguments, list) else [arguments]
            for directive in directives:
                if not isinstance(directive, dict) or "$object" not in directive:
                    continue
                base_expression = directive["$object"]
                self.assertTrue(base_expression.startswith("$input."))
                base = self._path(sample_input, base_expression.removeprefix("$input."))
                for path in directive["$overrides"]:
                    if path.startswith("/"):
                        self._pointer(base, path)
                    else:
                        self.assertTrue(
                            path in base or path in {"runId", "idempotencyKey", "approvalRef"},
                            f"override path {path} is absent from the business input",
                        )


if __name__ == "__main__":
    unittest.main()
