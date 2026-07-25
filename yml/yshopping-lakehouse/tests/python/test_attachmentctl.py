import copy
import importlib.machinery
import importlib.util
import unittest
from collections import Counter
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "attachmentctl"
LOADER = importlib.machinery.SourceFileLoader("attachmentctl", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
ATTACHMENTS = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(ATTACHMENTS)


class AttachmentCtlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        attachment_root = (
            ATTACHMENTS.DEFAULT_REFERENCE_ROOT / ATTACHMENTS.ATTACHMENT_DIRECTORY
        )
        if not attachment_root.exists():
            raise unittest.SkipTest(
                "canonical Obsidian attachment directory is not available in this checkout"
            )
        cls.snapshot = ATTACHMENTS.extract_snapshot()
        cls.contract = ATTACHMENTS.load_contract()

    def test_complete_reference_directory_attachment_snapshot_validates(self):
        self.assertEqual([], ATTACHMENTS.validate_contract(self.snapshot, self.contract))
        self.assertEqual(247, self.snapshot["attachment_count"])
        self.assertEqual(247, self.snapshot["reference_occurrence_count"])
        self.assertEqual(247, self.snapshot["unique_reference_count"])
        self.assertEqual(
            {item["name"] for item in self.snapshot["files"]},
            {item["name"] for item in self.snapshot["references"]},
        )
        self.assertTrue(
            all(count == 1 for count in Counter(
                item["name"] for item in self.snapshot["references"]
            ).values())
        )

    def test_semantic_review_expands_the_true_source_universe(self):
        universe = self.contract["governed_universe"]
        self.assertEqual(718, universe["markdown_source_candidate_count"])
        self.assertEqual(1, universe["visual_source_dependency_count"])
        self.assertEqual(719, universe["total_source_candidate_count"])
        self.assertEqual(2, universe["visual_derived_target_count"])
        flagged = self.contract["semantic_review"]["flagged_images"]
        self.assertEqual(20, len(flagged))
        self.assertEqual(
            {"ads_ux_ai_overview_target", "ads_ai_intelligence_target"},
            {
                identifier
                for item in flagged
                if item["classification"] == "visual_derived_target"
                for identifier in item["ocr_identifiers"]
                if identifier.startswith("ads_") and not identifier.endswith("_")
            },
        )
        self.assertEqual(
            ["ods_yx_base_employee_base"],
            [
                identifier
                for item in flagged
                if item["classification"] == "visual_source_dependency"
                for identifier in item["ocr_identifiers"]
            ],
        )

    def test_byte_drift_invalidates_the_reviewed_snapshot(self):
        drifted = copy.deepcopy(self.snapshot)
        drifted["attachment_aggregate_sha256"] = "0" * 64
        errors = ATTACHMENTS.validate_contract(drifted, self.contract)
        self.assertTrue(any("snapshot attachment_aggregate_sha256 drift" in error for error in errors))
        self.assertTrue(any("semantic review is not bound" in error for error in errors))

    def test_unreviewed_visual_source_cannot_change_the_denominator(self):
        contract = copy.deepcopy(self.contract)
        contract["governed_universe"]["visual_source_dependency_count"] = 0
        contract["governed_universe"]["total_source_candidate_count"] = 718
        errors = ATTACHMENTS.validate_contract(self.snapshot, contract)
        self.assertTrue(any("visual source dependency count" in error for error in errors))
        self.assertTrue(any("total governed source universe" in error for error in errors))

    def test_reference_binary_is_content_addressed_and_never_admitted(self):
        disposition = self.contract["binary_attachment_disposition"]
        self.assertEqual("reference_binary_rejected", disposition["decision"])
        self.assertFalse(disposition["executable_admission"])
        target = next(
            item for item in self.snapshot["files"] if item["path"] == disposition["path"]
        )
        self.assertEqual("binary", target["kind"])
        self.assertEqual(disposition["sha256"], target["sha256"])


if __name__ == "__main__":
    unittest.main()
