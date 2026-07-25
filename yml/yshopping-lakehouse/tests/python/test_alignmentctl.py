import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "alignmentctl"
LOADER = importlib.machinery.SourceFileLoader("alignmentctl", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
ALIGNMENT = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(ALIGNMENT)
REFERENCE_FIXTURES_AVAILABLE = all(
    (ALIGNMENT.DEFAULT_REFERENCE_ROOT / item["filename"]).exists()
    for item in ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)["source_documents"]
)


class AlignmentCtlTest(unittest.TestCase):
    @unittest.skipUnless(
        REFERENCE_FIXTURES_AVAILABLE,
        "canonical Obsidian source documents are not available in this checkout",
    )
    def test_checked_in_alignment_contract_validates(self):
        ALIGNMENT.validate_all()

    def test_source_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.md"
            source.write_text("original\n", encoding="utf-8")
            manifest = {
                "source_documents": [
                    {
                        "filename": source.name,
                        "sha256": ALIGNMENT.sha256(source),
                        "line_count": 1,
                    }
                ]
            }
            source.write_text("changed\n", encoding="utf-8")
            errors = ALIGNMENT.validate_source_documents(manifest, root)
            self.assertTrue(any("source drift" in error for error in errors))

    def test_source_corrections_are_structured(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        broken["source_corrections"][0]["decision"] = "copy_anyway"
        errors = ALIGNMENT.validate_source_corrections(broken)
        self.assertTrue(any("invalid copy_anyway" in error for error in errors))

    def test_missing_required_unit_is_rejected(self):
        manifest = {"required_alignment_units": ["trade.order"], "alignment_units": []}
        errors = ALIGNMENT.validate_units(manifest)
        self.assertTrue(any("missing required ids" in error for error in errors))

    def test_asset_baseline_totals_and_current_manifest_are_locked(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        self.assertEqual(ALIGNMENT.validate_asset_baseline(manifest), [])
        broken = json.loads(json.dumps(manifest))
        broken["prototype_asset_baseline"]["totals"]["candidate_names"] += 1
        errors = ALIGNMENT.validate_asset_baseline(broken)
        self.assertTrue(any("candidate_names" in error for error in errors))

        broken = json.loads(json.dumps(manifest))
        broken["prototype_asset_baseline"]["current_model_targets"] += 1
        errors = ALIGNMENT.validate_asset_baseline(broken)
        self.assertTrue(any("current_model_targets" in error for error in errors))

    def test_partial_surface_requires_existing_evidence_and_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            errors = ALIGNMENT.validate_surface(
                {"status": "partial", "refs": ["missing.sql"], "gaps": []},
                "backend",
                root,
            )
            self.assertTrue(any("missing missing.sql" in error for error in errors))
            self.assertTrue(any("requires explicit gaps" in error for error in errors))

    def test_similarity_score_is_machine_derived_from_honest_surfaces(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        score = ALIGNMENT.calculate_similarity_score(manifest)
        self.assertEqual(100.0, score["overall_percent"])
        self.assertEqual(100.0, score["backend_percent"])
        self.assertEqual(100.0, score["lakehouse_percent"])
        self.assertEqual(44.0, score["earned_surface_points"])
        self.assertEqual(44, score["eligible_surface_count"])
        self.assertEqual(0, score["excluded_unit_count"])

    def test_similarity_floor_rejects_regression_but_keeps_target_visible(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        self.assertEqual(ALIGNMENT.validate_similarity_score(manifest), [])

        broken = json.loads(json.dumps(manifest))
        broken["alignment_units"][0]["backend"] = {
            "status": "missing",
            "refs": [],
            "gaps": ["regression probe"],
        }
        errors = ALIGNMENT.validate_similarity_score(broken)
        self.assertTrue(any("below baseline floor" in error for error in errors))

        score = ALIGNMENT.calculate_similarity_score(manifest)
        self.assertGreaterEqual(score["overall_percent"], manifest["similarity_score"]["target_percent"])

    def test_strict_semantic_completion_does_not_credit_partial_or_deferred_surfaces(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        self.assertEqual([], ALIGNMENT.validate_semantic_completion_score(manifest))
        score = ALIGNMENT.calculate_semantic_completion_score(manifest)
        self.assertEqual(0.0, score["overall_percent"])
        self.assertEqual(0, score["verified_surface_count"])
        self.assertEqual(44, score["required_surface_count"])
        self.assertEqual(0, score["complete_unit_count"])
        self.assertEqual(22, score["required_unit_count"])
        self.assertFalse(score["target_met"])

    def test_strict_semantic_completion_requires_both_sides_and_full_evidence(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        first = manifest["alignment_units"][0]
        first["backend"] = {"status": "verified", "refs": first["backend"]["refs"], "gaps": []}
        score = ALIGNMENT.calculate_semantic_completion_score(manifest)
        self.assertEqual(0, score["verified_surface_count"])
        self.assertEqual(0, score["complete_unit_count"])
        first["lakehouse"] = {
            "status": "verified",
            "refs": first["lakehouse"]["refs"],
            "gaps": [],
        }
        score = ALIGNMENT.calculate_semantic_completion_score(manifest)
        self.assertEqual(0, score["verified_surface_count"])
        manifest["semantic_completion_evidence"] = [
            {
                "unit_id": first["id"],
                "source_asset_ledger_ref": "asset-ledger.json",
                "decision_context_refs": ["context"],
                "open_gaps": [],
                "backend": {
                    "authority_refs": ["authority"],
                    "contract_refs": ["contract"],
                    "verification_refs": ["verification"],
                    "non_empty_reconciliation_refs": ["runtime"],
                },
                "lakehouse": {
                    "layer_refs": {
                        "ODS": ["ods"],
                        "DIM": ["dim"],
                        "DWD_DWM": ["dwd"],
                        "DWS": ["dws"],
                        "ADS": ["ads"],
                    },
                    "history_policy_refs": ["history"],
                    "delete_policy_refs": ["delete"],
                    "dqc_refs": ["dqc"],
                    "non_empty_reconciliation_refs": ["runtime"],
                },
            }
        ]
        score = ALIGNMENT.calculate_semantic_completion_score(manifest)
        self.assertEqual(2, score["verified_surface_count"])
        self.assertEqual(1, score["complete_unit_count"])

    def test_incomplete_semantic_completion_evidence_is_rejected(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        manifest["semantic_completion_evidence"] = [
            {"unit_id": "trade.order", "open_gaps": []}
        ]
        errors = ALIGNMENT.validate_semantic_completion_evidence(manifest)
        self.assertTrue(any("source_asset_ledger_ref" in error for error in errors))
        self.assertTrue(any("backend" in error for error in errors))
        self.assertTrue(any("lakehouse" in error for error in errors))

    def test_detailed_context_ids_are_closed(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        broken["detailed_alignment"]["required_context_ids"].append("undeclared")
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("ids differ" in error for error in errors))

    def test_shadow_context_freezes_verified_as_evidence_not_execution(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        context = next(
            item for item in manifest["detailed_alignment"]["contexts"]
            if item["id"] == "inventory_migration_shadow_window"
        )
        invariant_ids = {item["id"] for item in context["invariants"]}
        self.assertIn("shadow-expected-items-rounds-denominator", invariant_ids)
        self.assertIn("shadow-gtid-server-containment", invariant_ids)
        self.assertIn("shadow-verified-not-execution", invariant_ids)
        ads = next(item for item in context["layers"] if item["layer"] == "ADS")
        self.assertIn("SHADOW_MATCH_VERIFIED", ads["corrections"][0])
        self.assertIn("execution and cutover remain false", ads["corrections"][0])

    @unittest.skipUnless(
        REFERENCE_FIXTURES_AVAILABLE,
        "canonical Obsidian source documents are not available in this checkout",
    )
    def test_source_anchor_assets_must_exist_in_declared_lines(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        broken["detailed_alignment"]["contexts"][0]["source_anchors"][0]["assets"] = [
            "asset_that_does_not_exist"
        ]
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("not found in declared range" in error for error in errors))

    def test_duplicate_canonical_authority_is_rejected(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        context = broken["detailed_alignment"]["contexts"][0]
        context["sor_decisions"].append(json.loads(json.dumps(context["sor_decisions"][0])))
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("duplicate canonical authority" in error for error in errors))

    def test_sensitive_field_requires_governance_controls(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        context = broken["detailed_alignment"]["contexts"][0]
        sensitive = next(
            field for field in context["field_mappings"] if field["classification"] == "pii"
        )
        sensitive.pop("controls")
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("sensitive fields require" in error for error in errors))

    def test_financial_field_requires_minor_unit_currency_and_rounding(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        context = broken["detailed_alignment"]["contexts"][0]
        financial = next(
            field
            for field in context["field_mappings"]
            if field["classification"] == "restricted_financial"
        )
        financial["money"].pop("currency_field")
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("financial amounts require" in error for error in errors))

    def test_all_five_lakehouse_layers_are_required(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        broken["detailed_alignment"]["contexts"][1]["layers"].pop()
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("expected exactly" in error for error in errors))

    def test_shop_and_warehouse_foreign_key_invariants_are_mandatory(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        context = broken["detailed_alignment"]["contexts"][0]
        context["invariants"] = [
            item for item in context["invariants"] if item["id"] != "shop-belongs-to-merchant"
        ]
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("shop-belongs-to-merchant" in error for error in errors))

        broken = json.loads(json.dumps(manifest))
        context = broken["detailed_alignment"]["contexts"][1]
        context["invariants"] = [
            item for item in context["invariants"] if item["id"] != "location-belongs-to-warehouse"
        ]
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("location-belongs-to-warehouse" in error for error in errors))

    def test_implemented_event_requires_real_schema_evidence(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        event = broken["detailed_alignment"]["contexts"][1]["events"][-1]
        event["status"] = "partial"
        event["schema_ref"] = "missing.schema.json"
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("implementation evidence required" in error for error in errors))

    def test_event_contract_separates_envelope_from_payload(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        event = broken["detailed_alignment"]["contexts"][0]["events"][0]
        event["required_payload_fields"].append("tenant_id")
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("tenant_id belongs to the envelope" in error for error in errors))

    def test_event_type_must_follow_envelope_naming(self):
        manifest = ALIGNMENT.load(ALIGNMENT.DEFAULT_MANIFEST)
        broken = json.loads(json.dumps(manifest))
        broken["detailed_alignment"]["contexts"][0]["events"][0]["event_type"] = "identity.source-linked"
        errors = ALIGNMENT.validate_detailed_alignment(broken)
        self.assertTrue(any("invalid event_type" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
