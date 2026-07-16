import importlib.machinery
import importlib.util
import hashlib
import json
import tempfile
import unittest
import uuid
from collections import Counter
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "sourceassetctl"
LOADER = importlib.machinery.SourceFileLoader("sourceassetctl", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
SOURCE_ASSETS = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(SOURCE_ASSETS)

from source_evidence import (
    canonical_sha256,
    validate_reconciliation,
    validate_trade_admission,
)


def write_valid_reconciliation(
    directory: Path, *, source_asset: str, run_id: str, row_count: int, tenant_count: int
) -> Path:
    payload = directory / "source.jsonl"
    payload.write_text('{"tenant_id":"t-1","source_key":"k-1"}\n', encoding="utf-8")
    schema = directory / "source-schema.sql"
    schema.write_text("tenant_id STRING NOT NULL, source_key STRING NOT NULL\n", encoding="utf-8")
    query = directory / "extract.sql"
    query.write_text("SELECT tenant_id, source_key FROM bounded_source\n", encoding="utf-8")
    verifier_code = directory / "reconcile.sql"
    verifier_code.write_text("SELECT COUNT(*) AS mismatch_count FROM independent_diff\n", encoding="utf-8")
    tenant_mapping = directory / "tenant-mapping.json"
    tenant_mapping.write_text('{"source_tenant":"t-1","canonical_tenant":"1","version":1}\n', encoding="utf-8")
    attestation = directory / "source-audit.json"
    attestation.write_text('{"job":"job-1","access":"read-only","result":"completed"}\n', encoding="utf-8")
    manifest = {
        "contract_id": "yshopping.source-evidence-bundle.v1",
        "bundle_id": str(uuid.uuid4()),
        "source_system": "YSHOPPING",
        "source_environment": "production",
        "provenance": {
            "snapshot_id": "snapshot-1",
            "extraction_job_id": "job-1",
            "extractor_identity": "test-governed-extractor",
            "attestation_method": "SOURCE_SYSTEM_AUDIT_EXPORT",
            "read_only_confirmed": True,
            "attestation_ref": attestation.name,
            "attestation_sha256": hashlib.sha256(attestation.read_bytes()).hexdigest(),
        },
        "source": {
            "asset": source_asset,
            "qualified_table": f"yshopping.{source_asset}",
            "schema_ref": schema.name,
            "schema_sha256": hashlib.sha256(schema.read_bytes()).hexdigest(),
            "primary_key": ["source_key"],
            "columns": [
                {"name": "tenant_id", "type": "STRING", "nullable": False, "classification": "internal", "semantic_role": "tenant"},
                {"name": "source_key", "type": "STRING", "nullable": False, "classification": "internal", "semantic_role": "business_key"},
            ],
        },
        "extraction": {
            "mode": "READ_ONLY_SNAPSHOT",
            "full_denominator": True,
            "sampled": False,
            "query_ref": query.name,
            "query_sha256": hashlib.sha256(query.read_bytes()).hexdigest(),
            "extracted_at": "2026-07-17T00:00:00Z",
            "window": {"field": "pt", "start_inclusive": "2026-07-01", "end_exclusive": "2026-07-02"},
            "watermark": {"kind": "partition", "value": "2026-07-01"},
        },
        "tenant_scope": {"strategy": "source-key-map", "source_keys": ["tenant_id"], "tenant_count": tenant_count},
        "quality": {
            "row_count": row_count,
            "distinct_business_key_count": row_count,
            "duplicate_business_key_count": 0,
            "null_business_key_count": 0,
            "deleted_row_count": 0,
        },
        "semantic_artifacts": [{
            "kind": "tenant_mapping",
            "path": tenant_mapping.name,
            "sha256": hashlib.sha256(tenant_mapping.read_bytes()).hexdigest(),
        }],
        "security": {"pii_handling": "no_pii"},
        "files": [{
            "path": payload.name,
            "format": "JSONL",
            "byte_count": payload.stat().st_size,
            "row_count": row_count,
            "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
        }],
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest, "manifest_sha256")
    manifest_path = directory / "bundle.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    business_key_digest = hashlib.sha256(b"all-source-business-keys").hexdigest()
    evidence = {
        "contract_id": "yshopping.source-reconciliation-evidence.v1",
        "reconciliation_id": str(uuid.uuid4()),
        "run_id": run_id,
        "source_asset": source_asset,
        "source_bundle_ref": manifest_path.name,
        "source_bundle_manifest_sha256": manifest["manifest_sha256"],
        "result": "verified",
        "full_denominator": True,
        "sampled": False,
        "coverage": {
            "source_row_count": row_count,
            "admitted_source_row_count": row_count,
            "quarantined_source_row_count": 0,
            "missing_source_row_count": 0,
            "duplicate_source_coverage_count": 0,
            "tenant_count": tenant_count,
            "source_business_key_sha256": business_key_digest,
            "accounted_business_key_sha256": business_key_digest,
        },
        "canonical_outputs": [{"target": "canonical.test", "row_count": row_count}],
        "semantic_checks": [{"name": "business_key_coverage", "checked_count": row_count, "mismatch_count": 0}],
        "independent_verifier": {
            "engine": "test-independent-engine",
            "code_ref": verifier_code.name,
            "code_sha256": hashlib.sha256(verifier_code.read_bytes()).hexdigest(),
            "executed_at": "2026-07-17T00:01:00Z",
            "independent_from_extractor": True,
            "independent_from_canonical_transform": True,
        },
        "authorization": {"import_enabled": False, "cutover_enabled": False},
    }
    evidence["evidence_sha256"] = canonical_sha256(evidence, "evidence_sha256")
    evidence_path = directory / "reconciliation.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    return evidence_path


class SourceAssetCtlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = SOURCE_ASSETS.extract_inventory()

    def test_checked_in_source_snapshot_validates(self):
        self.assertEqual([], SOURCE_ASSETS.validate_inventory(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_source_domain_policy(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_source_asset_routes(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_game_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_metadata_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_commerce_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_product_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_merchant_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_coupon_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_user_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_payment_source_schema_request(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_advertising_source_schema_request(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_community_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_engagement_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_compensation_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_ticket_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_supply_chain_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_llm_source_dispositions(self.inventory))
        self.assertEqual([], SOURCE_ASSETS.validate_operations_intelligence_source_dispositions(self.inventory))
        self.assertEqual(
            [],
            validate_trade_admission(
                SOURCE_ASSETS.TRADE_HISTORY_ADMISSION,
                SOURCE_ASSETS.DEFAULT_REFERENCE_ROOT / SOURCE_ASSETS.LAYER_DOCUMENTS["ODS"],
            ),
        )
        self.assertEqual(6, len(self.inventory["documents"]))

    def test_inventory_is_complete_and_deterministic_for_the_locked_snapshot(self):
        summary = self.inventory["summary"]
        self.assertEqual(1790, summary["unique_asset_count"])
        self.assertEqual(728, summary["unique_logical_asset_count"])
        self.assertEqual(728, summary["global_unique_name_count"])
        self.assertEqual(
            {
                "candidate": 718,
                "create_target": 491,
                "dependency": 303,
                "insert_target": 278,
            },
            summary["unique_by_kind"],
        )
        self.assertEqual(2364, summary["document_role_unique_count"])
        self.assertEqual(
            {
                "candidate": 1139,
                "create_target": 501,
                "dependency": 442,
                "insert_target": 282,
            },
            summary["document_role_unique_by_kind"],
        )
        self.assertEqual(752, summary["reference_occurrence_count"])
        self.assertEqual(
            {
                "code_symbol": 35,
                "cte": 124,
                "physical_table": 561,
                "python_import": 26,
                "unclassified_reference": 6,
            },
            summary["references_by_kind"],
        )
        self.assertEqual(1327, summary["topic_count"])
        self.assertEqual(1, summary["unparsed_statement_line_count"])
        asset_ids = [item["asset_id"] for item in self.inventory["assets"]]
        self.assertEqual(asset_ids, sorted(asset_ids))
        self.assertEqual(len(asset_ids), len(set(asset_ids)))
        logical_ids = [item["logical_asset_id"] for item in self.inventory["logical_assets"]]
        self.assertEqual(logical_ids, sorted(logical_ids))
        self.assertEqual(len(logical_ids), len(set(logical_ids)))

    def test_known_source_defects_remain_visible_instead_of_being_normalized_away(self):
        assets = {item["asset_id"]: item for item in self.inventory["assets"]}
        self.assertIn("ods:create_target:ods_goods_goods_white_df", assets)
        misplaced = assets["ods:create_target:ods_goods_goods_white_df"]
        self.assertEqual(["DIM", "ODS"], misplaced["document_layers"])
        self.assertIn("wrong_layer_create", misplaced["occurrences"][0]["risk_flags"])
        self.assertIn("ods:create_target:ods_scm_sorting_di", assets)
        duplicate = assets["dws:create_target:dws_com_trend_user_target_1d"]
        self.assertEqual(2, len(duplicate["occurrences"]))
        issue = self.inventory["unparsed_statement_lines"][0]
        self.assertEqual(6141, issue["line"])
        self.assertIn("{full_name}", issue["text"])
        self.assertIn("ods:candidate:ods_eliminate_user_coin_log_df", assets)
        self.assertIn("ods:candidate:ods__", assets)

    def test_code_references_are_classified_without_polluting_physical_dependencies(self):
        assets = {item["asset_id"] for item in self.inventory["assets"]}
        for false_dependency in ("pathlib", "typing", "__future__", "tt0", "base"):
            self.assertFalse(any(item.endswith(f":{false_dependency}") for item in assets))
        reference_kinds = {
            (item["qualified_name"], item["reference_kind"])
            for item in self.inventory["references"]
        }
        self.assertIn(("typing", "python_import"), reference_kinds)
        self.assertIn(("tt0", "cte"), reference_kinds)

    def test_ods_overview_is_authoritative_business_domain_evidence(self):
        domains = Counter()
        for asset in self.inventory["logical_assets"]:
            for domain in asset["source_domains"]:
                domains[domain] += 1
        self.assertEqual(
            {
                "正向订单": 11, "逆向订单": 7, "支付": 14, "库存": 3,
                "供应链": 23, "活动": 56, "优惠券": 6, "推送": 2,
                "游戏": 19, "赔付": 3, "工单": 15, "用户": 30,
                "商家": 7, "广告": 7, "社区": 33, "收藏": 2,
                "算法": 1, "中台": 3, "商品": 10, "大模型": 16,
                "情报系统": 3, "元数据": 10,
            },
            dict(domains),
        )
        game = next(
            item for item in self.inventory["logical_assets"]
            if item["normalized_name"] == "ods_eliminate_user_coin_log_df"
        )
        self.assertEqual(["游戏"], game["source_domains"])
        self.assertEqual(["游戏用户能量记录/库下金币记录"], game["source_labels"])

    def test_domain_routing_is_measured_but_never_credited_as_final_disposition(self):
        status = SOURCE_ASSETS.disposition_status(self.inventory)
        self.assertEqual(718, status["candidate_asset_count"])
        self.assertEqual(281, status["authoritative_ods_overview_asset_count"])
        self.assertEqual(712, status["domain_routed_asset_count"])
        self.assertEqual(322, status["heading_lineage_inferred_asset_count"])
        self.assertEqual(112, status["explicit_asset_route_count"])
        self.assertEqual(110, status["bounded_domain_asset_count"])
        self.assertEqual(6, status["explicit_rejection_count"])
        self.assertEqual(718, status["preliminary_handled_count"])
        self.assertEqual(159, status["detailed_disposition_specified_count"])
        self.assertEqual(0, status["runtime_nonempty_reconciled_count"])
        self.assertEqual(0, status["final_disposition_verified_count"])
        self.assertEqual(99.16, status["routing_percent"])
        self.assertEqual(100.0, status["preliminary_handled_percent"])
        self.assertEqual(22.14, status["detailed_disposition_specified_percent"])
        self.assertEqual(0.0, status["runtime_nonempty_reconciled_percent"])
        self.assertEqual(0.0, status["final_disposition_percent"])
        self.assertIn(
            "ods_trade_trade_discount_df",
            SOURCE_ASSETS.load_source_domain_policy()["explicit_rejections"],
        )
        inferred = SOURCE_ASSETS.infer_source_domains(self.inventory)
        self.assertEqual(
            ["游戏"], inferred["ods:object:ods_eliminate_user_coin_log_df"]["domains"]
        )
        self.assertEqual(
            ["ods_overview"],
            inferred["ods:object:ods_eliminate_user_coin_log_df"]["evidence_kinds"],
        )
        lines = list(SOURCE_ASSETS.disposition_lines(self.inventory))
        self.assertTrue(any("metadata=10/10 (100.00%)" in line for line in lines))
        self.assertTrue(any("metadata=0/10 (0.00%)" in line for line in lines))
        self.assertTrue(any("commerce=19/35 (54.29%)" in line for line in lines))
        self.assertTrue(any("commerce=0/35 (0.00%)" in line for line in lines))
        self.assertTrue(any("product=9/10 (90.00%)" in line for line in lines))
        self.assertTrue(any("product=0/10 (0.00%)" in line for line in lines))
        self.assertTrue(any("merchant=6/7 (85.71%)" in line for line in lines))
        self.assertTrue(any("merchant=0/7 (0.00%)" in line for line in lines))
        self.assertTrue(any("coupon=6/6 (100.00%)" in line for line in lines))
        self.assertTrue(any("coupon=0/6 (0.00%)" in line for line in lines))
        self.assertTrue(any("user=2/30 (6.67%)" in line for line in lines))
        self.assertTrue(any("user=0/30 (0.00%)" in line for line in lines))
        self.assertTrue(any("advertising=0/7 (0.00%)" in line for line in lines))
        self.assertTrue(any("community=30/33 (90.91%)" in line for line in lines))
        self.assertTrue(any("community=0/33 (0.00%)" in line for line in lines))
        self.assertTrue(any("engagement=4/4 (100.00%)" in line for line in lines))
        self.assertTrue(any("engagement=0/4 (0.00%)" in line for line in lines))
        self.assertTrue(any("compensation=1/3 (33.33%)" in line for line in lines))
        self.assertTrue(any("compensation=0/3 (0.00%)" in line for line in lines))
        self.assertTrue(any("ticket=11/15 (73.33%)" in line for line in lines))
        self.assertTrue(any("ticket=0/15 (0.00%)" in line for line in lines))
        self.assertTrue(any("supply_chain=23/23 (100.00%)" in line for line in lines))
        self.assertTrue(any("supply_chain=0/23 (0.00%)" in line for line in lines))
        self.assertTrue(any("llm=14/16 (87.50%)" in line for line in lines))
        self.assertTrue(any("llm=0/16 (0.00%)" in line for line in lines))
        self.assertTrue(any("operations_intelligence=5/7 (71.43%)" in line for line in lines))
        self.assertTrue(any("operations_intelligence=0/7 (0.00%)" in line for line in lines))
        self.assertTrue(any("operations_intelligence=0/7; routing is not completion" in line for line in lines))

    def test_game_dispositions_cover_exact_authoritative_overview_rows(self):
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "游戏")
        contract = SOURCE_ASSETS.load_game_source_dispositions()
        names = [asset["source_asset"] for asset in contract["assets"]]
        self.assertEqual(19, len(observed))
        self.assertEqual(19, len(names))
        self.assertEqual(set(observed), set(names))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(
            {line for item in observed.values() for _, line in item["anchors"]},
            set(range(133, 152)),
        )
        for asset in contract["assets"]:
            source = observed[asset["source_asset"]]
            self.assertEqual([asset["source_label"]], source["source_labels"])
            self.assertIn(
                (asset["source_anchor"]["document"], asset["source_anchor"]["line"]),
                source["anchors"],
            )

    def test_game_dispositions_are_fully_specified_but_not_runtime_verified(self):
        status = SOURCE_ASSETS.game_disposition_status(self.inventory)
        self.assertEqual(
            {
                "game_source_asset_count": 19,
                "game_detailed_disposition_specified_count": 19,
                "game_runtime_nonempty_reconciled_count": 0,
                "game_final_disposition_verified_count": 0,
                "game_detailed_disposition_percent": 100.0,
                "game_runtime_nonempty_reconciled_percent": 0.0,
                "game_final_disposition_verified_percent": 0.0,
            },
            status,
        )
        contract = SOURCE_ASSETS.load_game_source_dispositions()
        for asset in contract["assets"]:
            self.assertEqual("specified", asset["specification_status"])
            self.assertEqual("unverified", asset["verification_status"])
            runtime = asset["runtime_nonempty_reconciliation"]
            self.assertEqual("missing", runtime["status"])
            self.assertIsNone(runtime["evidence_ref"])
            self.assertEqual(0, runtime["row_count"])
            self.assertEqual(0, runtime["tenant_count"])

    def test_game_dispositions_encode_required_authority_boundaries(self):
        contract = SOURCE_ASSETS.load_game_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        coin = by_name["ods_eliminate_user_coin_log_df"]
        self.assertIn("gamification.VirtualCurrencyLedgerEntry", coin["canonical_entities"])
        self.assertIn("exactly two entries", coin["field_rules"]["quantity"])
        for name in (
            "ods_card_mall_coin_log_df",
            "ods_eliminate_mall_coin_log_df",
            "ods_factory_mall_coin_log_df",
        ):
            asset = by_name[name]
            self.assertIn("gamification.RedemptionIntent", asset["canonical_entities"])
            self.assertIn("gamification.VirtualCurrencyTransaction", asset["canonical_entities"])
            self.assertFalse(any("Collectible" in entity for entity in asset["canonical_entities"]))
            self.assertIn("mall", asset["sor_owner"])
            self.assertIn("balance", asset["field_rules"]["currency_boundary"])
            self.assertIn("GAME_VIRTUAL_CURRENCY", asset["field_rules"]["currency_boundary"])
            self.assertIn("PENDING/SUCCEEDED/REJECTED", asset["field_rules"]["status"])
            self.assertNotIn("FAILED", asset["field_rules"]["status"])
            self.assertIn("amount_microunits", asset["field_rules"]["quantity"])
            self.assertIn("GAME_COIN_*", asset["field_rules"]["quantity"])
            self.assertTrue(any("V20260716_34" in ref for ref in asset["backend_refs"]))
            self.assertTrue(any("V20260716_02" in ref for ref in asset["backend_refs"]))
        self.assertEqual(
            "split", by_name["ods_fortune_season_series_df"]["decision"]
        )
        self.assertIn(
            "gamification.CollectibleOwnership",
            by_name["ods_fortune_gk_df"]["canonical_entities"],
        )
        self.assertIn(
            "gamification.RewardClaim",
            by_name["ods_yshopping_hacking_world_user_receive_record_df"]["canonical_entities"],
        )
        for name in (
            "ods_yshopping_hacking_world_rank_currency_df",
            "ods_yshopping_hacking_world_rank_gift_df",
        ):
            asset = by_name[name]
            self.assertEqual("derive", asset["decision"])
            self.assertTrue(all(entity.startswith("analytics.") for entity in asset["canonical_entities"]))
            self.assertTrue(any("README.md#Leaderboards" in ref for ref in asset["backend_refs"]))
        self.assertEqual(
            [
                "dws_canonical_gamification_currency_leaderboard_input_current",
                "ads_canonical_gamification_currency_leaderboard_current",
            ],
            by_name["ods_yshopping_hacking_world_rank_currency_df"]["canonical_targets"],
        )
        self.assertEqual(
            [
                "dws_canonical_gamification_gift_leaderboard_1d",
                "ads_canonical_gamification_gift_leaderboard_1d",
            ],
            by_name["ods_yshopping_hacking_world_rank_gift_df"]["canonical_targets"],
        )

    def test_game_final_verification_fails_closed_without_nonempty_runtime_evidence(self):
        contract = SOURCE_ASSETS.load_game_source_dispositions()
        broken = json.loads(json.dumps(contract))
        broken["assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_game_source_dispositions(self.inventory, broken)
        self.assertTrue(any("forbidden without non-empty" in error for error in errors))

        incomplete = json.loads(json.dumps(contract))
        runtime = incomplete["assets"][0]["runtime_nonempty_reconciliation"]
        runtime["status"] = "verified"
        runtime["evidence_ref"] = "/tmp/not-enough.json"
        errors = SOURCE_ASSETS.validate_game_source_dispositions(self.inventory, incomplete)
        self.assertTrue(any("positive row/tenant counts" in error for error in errors))

        nonexistent = json.loads(json.dumps(contract))
        runtime = nonexistent["assets"][0]["runtime_nonempty_reconciliation"]
        runtime.update(
            {
                "status": "verified",
                "evidence_ref": "/tmp/cloudmold-game-evidence-does-not-exist.json",
                "run_id": "game-runtime-001",
                "row_count": 1,
                "tenant_count": 1,
            }
        )
        nonexistent["assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_game_source_dispositions(self.inventory, nonexistent)
        self.assertTrue(any("durable evidence" in error for error in errors))

        with tempfile.TemporaryDirectory() as directory:
            proven = json.loads(json.dumps(contract))
            runtime = proven["assets"][0]["runtime_nonempty_reconciliation"]
            evidence = write_valid_reconciliation(
                Path(directory),
                source_asset=proven["assets"][0]["source_asset"],
                run_id="game-runtime-verified-001",
                row_count=7,
                tenant_count=1,
            )
            runtime.update(
                {
                    "status": "verified",
                    "evidence_ref": str(evidence),
                    "run_id": "game-runtime-verified-001",
                    "row_count": 7,
                    "tenant_count": 1,
                }
            )
            proven["assets"][0]["verification_status"] = "verified"
            self.assertEqual(
                [], SOURCE_ASSETS.validate_game_source_dispositions(self.inventory, proven)
            )
            status = SOURCE_ASSETS.game_disposition_status(self.inventory, proven)
            self.assertEqual(1, status["game_runtime_nonempty_reconciled_count"])
            self.assertEqual(1, status["game_final_disposition_verified_count"])

    def test_runtime_evidence_detects_payload_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = write_valid_reconciliation(
                root,
                source_asset="ods_eliminate_user_coin_log_df",
                run_id="trade-runtime-001",
                row_count=7,
                tenant_count=1,
            )
            (root / "source.jsonl").write_text("tampered\n", encoding="utf-8")
            errors = validate_reconciliation(evidence)
            self.assertTrue(any("sha256 mismatch" in error for error in errors))

    def test_runtime_evidence_rejects_sampling_and_non_production_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_path = write_valid_reconciliation(
                root,
                source_asset="ods_eliminate_user_coin_log_df",
                run_id="trade-runtime-002",
                row_count=7,
                tenant_count=1,
            )
            manifest_path = root / "bundle.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_environment"] = "test"
            manifest["extraction"]["sampled"] = True
            manifest["extraction"]["full_denominator"] = False
            manifest["manifest_sha256"] = canonical_sha256(manifest, "manifest_sha256")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["source_bundle_manifest_sha256"] = manifest["manifest_sha256"]
            evidence["evidence_sha256"] = canonical_sha256(evidence, "evidence_sha256")
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            errors = validate_reconciliation(evidence_path)
            self.assertTrue(any("requires production" in error for error in errors))
            self.assertTrue(any("full-denominator" in error for error in errors))

    def test_runtime_evidence_rejects_denominator_and_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_path = write_valid_reconciliation(
                root,
                source_asset="ods_eliminate_user_coin_log_df",
                run_id="trade-runtime-003",
                row_count=7,
                tenant_count=1,
            )
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["coverage"]["admitted_source_row_count"] = 6
            evidence["evidence_sha256"] = canonical_sha256(evidence, "evidence_sha256")
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            errors = validate_reconciliation(
                evidence_path,
                expected_asset="ods_trade_trade_discount_di",
                expected_run_id="another-run",
                expected_row_count=8,
                expected_tenant_count=2,
            )
            self.assertTrue(any("admitted plus quarantined" in error for error in errors))
            self.assertTrue(any("source_asset does not match" in error for error in errors))
            self.assertTrue(any("run_id does not match" in error for error in errors))
            self.assertTrue(any("row count does not match" in error for error in errors))
            self.assertTrue(any("tenant count does not match" in error for error in errors))

    def test_trade_history_admission_is_bound_to_commerce_dispositions(self):
        admission = json.loads(
            SOURCE_ASSETS.TRADE_HISTORY_ADMISSION.read_text(encoding="utf-8")
        )
        commerce = SOURCE_ASSETS.load_commerce_source_dispositions()
        commerce_by_name = {
            asset["source_asset"]: asset for asset in commerce["assets"]
        }
        self.assertEqual(
            [
                "ods_trade_trade_order_di",
                "ods_trade_trade_sub_order_di",
                "ods_trade_trade_discount_di",
            ],
            [asset["source_asset"] for asset in admission["assets"]],
        )
        for asset in admission["assets"]:
            disposition = commerce_by_name[asset["source_asset"]]
            self.assertEqual(
                set(disposition["canonical_entities"]), set(asset["canonical_targets"])
            )
            self.assertEqual("specified", disposition["specification_status"])
            self.assertEqual("unverified", disposition["verification_status"])
            self.assertEqual("missing", disposition["runtime_nonempty_reconciliation"]["status"])
        discount = admission["assets"][2]
        self.assertEqual(
            set(commerce_by_name[discount["source_asset"]]["field_dispositions"]),
            {column["name"] for column in discount["columns"]},
        )

    def test_game_contract_rejects_missing_duplicate_or_mislabeled_overview_assets(self):
        contract = SOURCE_ASSETS.load_game_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["assets"].pop()
        errors = SOURCE_ASSETS.validate_game_source_dispositions(self.inventory, missing)
        self.assertTrue(any("differ from authoritative ODS overview" in error for error in errors))

        duplicate = json.loads(json.dumps(contract))
        duplicate["assets"][1] = json.loads(json.dumps(duplicate["assets"][0]))
        errors = SOURCE_ASSETS.validate_game_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))

        mislabeled = json.loads(json.dumps(contract))
        mislabeled["assets"][0]["source_label"] = "金币"
        errors = SOURCE_ASSETS.validate_game_source_dispositions(self.inventory, mislabeled)
        self.assertTrue(any("source label differs" in error for error in errors))

    def test_all_game_implementation_references_and_fragments_resolve(self):
        contract = SOURCE_ASSETS.load_game_source_dispositions()
        references = [
            reference
            for asset in contract["assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ]
        self.assertEqual(100, len(references))
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_contract_reference_with_nonexistent_fragment_is_rejected(self):
        contract = SOURCE_ASSETS.load_game_source_dispositions()
        broken = json.loads(json.dumps(contract))
        original = broken["assets"][0]["backend_refs"][0].split("#", 1)[0]
        broken["assets"][0]["backend_refs"][0] = (
            original + "#fragment_that_cannot_exist_in_cloudmold"
        )
        errors = SOURCE_ASSETS.validate_game_source_dispositions(self.inventory, broken)
        self.assertTrue(any("missing fragment" in error for error in errors))

    def test_metadata_dispositions_cover_exact_authoritative_overview_rows(self):
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "元数据")
        contract = SOURCE_ASSETS.load_metadata_source_dispositions()
        names = [asset["source_asset"] for asset in contract["assets"]]
        self.assertEqual(10, len(observed))
        self.assertEqual(10, len(names))
        self.assertEqual(set(observed), set(names))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(
            {line for item in observed.values() for _, line in item["anchors"]},
            set(range(284, 294)),
        )
        for asset in contract["assets"]:
            source = observed[asset["source_asset"]]
            self.assertEqual([asset["source_label"]], source["source_labels"])
            self.assertIn(
                (asset["source_anchor"]["document"], asset["source_anchor"]["line"]),
                source["anchors"],
            )

    def test_metadata_dispositions_are_fully_specified_but_not_runtime_verified(self):
        self.assertEqual(
            {
                "metadata_source_asset_count": 10,
                "metadata_detailed_disposition_specified_count": 10,
                "metadata_runtime_nonempty_reconciled_count": 0,
                "metadata_final_disposition_verified_count": 0,
                "metadata_detailed_disposition_percent": 100.0,
                "metadata_runtime_nonempty_reconciled_percent": 0.0,
                "metadata_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.metadata_disposition_status(self.inventory),
        )
        contract = SOURCE_ASSETS.load_metadata_source_dispositions()
        for asset in contract["assets"]:
            self.assertEqual("specified", asset["specification_status"])
            self.assertEqual("unverified", asset["verification_status"])
            runtime = asset["runtime_nonempty_reconciliation"]
            self.assertEqual("missing", runtime["status"])
            self.assertIsNone(runtime["evidence_ref"])
            self.assertEqual(0, runtime["row_count"])
            self.assertEqual(0, runtime["tenant_count"])

    def test_all_metadata_implementation_references_and_fragments_resolve(self):
        contract = SOURCE_ASSETS.load_metadata_source_dispositions()
        references = [
            reference
            for asset in contract["assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ]
        self.assertEqual(60, len(references))
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_metadata_dispositions_encode_corrected_authority_boundaries(self):
        contract = SOURCE_ASSETS.load_metadata_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        task_run = by_name["ods_meta_task_instance_di"]
        self.assertIn("metadata.TaskRunObservation", task_run["canonical_entities"])
        self.assertIn("exact minor units", task_run["field_rules"]["value_or_unit"])
        self.assertIn("raw sql_content", task_run["field_rules"]["security_boundary"])
        dependency = by_name["ods_sla_parent_child_nodes_df"]
        self.assertEqual("correct", dependency["decision"])
        self.assertIn("direct edges only", dependency["field_rules"]["value_or_unit"])
        table = by_name["ods_meta_table_df"]
        self.assertIn("analytics.DatasetPhysicalObservation", table["canonical_entities"])
        lineage = by_name["ods_meta_table_lineage_df"]
        self.assertEqual("correct", lineage["decision"])
        self.assertIn("SOURCE_TO_TARGET", lineage["field_rules"]["status"])
        dqc = by_name["ods_meta_dq_dqc_df"]
        self.assertIn("monitor_sql is never stored raw", dqc["field_rules"]["security_boundary"])
        result = by_name["ods_meta_dq_dqc_instance_df"]
        self.assertIn(
            "task_run_id plus observation_sequence",
            result["field_rules"]["business_key"],
        )
        metric = by_name["ods_metrics_metrics_info_df"]
        self.assertIn(
            "grain_code and metric_unit are distinct",
            metric["field_rules"]["value_or_unit"],
        )

    def test_metadata_final_verification_fails_closed_without_runtime_evidence(self):
        contract = SOURCE_ASSETS.load_metadata_source_dispositions()
        broken = json.loads(json.dumps(contract))
        broken["assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_metadata_source_dispositions(self.inventory, broken)
        self.assertTrue(any("forbidden without non-empty" in error for error in errors))

        incomplete = json.loads(json.dumps(contract))
        runtime = incomplete["assets"][0]["runtime_nonempty_reconciliation"]
        runtime.update({"status": "verified", "evidence_ref": "/tmp/metadata.json"})
        errors = SOURCE_ASSETS.validate_metadata_source_dispositions(self.inventory, incomplete)
        self.assertTrue(any("positive row/tenant counts" in error for error in errors))

    def test_metadata_contract_rejects_missing_duplicate_or_mislabeled_assets(self):
        contract = SOURCE_ASSETS.load_metadata_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["assets"].pop()
        errors = SOURCE_ASSETS.validate_metadata_source_dispositions(self.inventory, missing)
        self.assertTrue(any("differ from authoritative ODS overview" in error for error in errors))

        duplicate = json.loads(json.dumps(contract))
        duplicate["assets"][1] = json.loads(json.dumps(duplicate["assets"][0]))
        errors = SOURCE_ASSETS.validate_metadata_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))

        mislabeled = json.loads(json.dumps(contract))
        mislabeled["assets"][0]["source_label"] = "任务"
        errors = SOURCE_ASSETS.validate_metadata_source_dispositions(self.inventory, mislabeled)
        self.assertTrue(any("source label differs" in error for error in errors))

    def test_commerce_dispositions_cover_exact_authoritative_overview_rows(self):
        contract = SOURCE_ASSETS.load_commerce_source_dispositions()
        expected, counts = SOURCE_ASSETS._commerce_expected_assets(
            self.inventory, contract["source_scope"]["domains"]
        )
        names = [asset["source_asset"] for asset in contract["assets"]]
        self.assertEqual(
            {"正向订单": 11, "逆向订单": 7, "支付": 14, "库存": 3}, counts
        )
        self.assertEqual(35, len(expected))
        self.assertEqual(
            {"ddl_backed": 18, "overview_only": 14, "name_conflict": 2, "rejected_mislabeled": 1},
            contract["source_scope"]["expected_source_evidence_counts"],
        )
        self.assertEqual(set(expected), set(names))
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(
            set(range(9, 45)),
            {line for item in expected.values() for _, line in item["anchors"]},
        )

    def test_commerce_dispositions_count_only_field_level_evidence_and_fail_closed_on_runtime(self):
        self.assertEqual(
            {
                "commerce_source_asset_count": 35,
                "commerce_detailed_disposition_specified_count": 19,
                "commerce_runtime_nonempty_reconciled_count": 0,
                "commerce_final_disposition_verified_count": 0,
                "commerce_detailed_disposition_percent": 54.29,
                "commerce_runtime_nonempty_reconciled_percent": 0.0,
                "commerce_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.commerce_disposition_status(self.inventory),
        )
        contract = SOURCE_ASSETS.load_commerce_source_dispositions()
        broken = json.loads(json.dumps(contract))
        broken["assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_commerce_source_dispositions(self.inventory, broken)
        self.assertTrue(any("forbidden without non-empty" in error for error in errors))

    def test_commerce_source_evidence_keeps_overview_only_and_name_conflicts_provisional(self):
        contract = SOURCE_ASSETS.load_commerce_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        statuses = [asset["source_evidence"]["status"] for asset in contract["assets"]]
        self.assertEqual(18, statuses.count("ddl_backed"))
        self.assertEqual(14, statuses.count("overview_only"))
        self.assertEqual(2, statuses.count("name_conflict"))
        self.assertEqual(1, statuses.count("rejected_mislabeled"))
        self.assertEqual(
            "ods_commodity_commodity_trade_spu_df",
            by_name["ods_trade_trade_trade_spu_df"]["source_evidence"]["detail_anchors"][0]["source_asset"],
        )
        self.assertEqual(
            "ods_commodity_commodity_sku_df",
            by_name["ods_trade_trade_trade_sku_df"]["source_evidence"]["detail_anchors"][0]["source_asset"],
        )
        broken = json.loads(json.dumps(contract))
        by_broken_name = {asset["source_asset"]: asset for asset in broken["assets"]}
        by_broken_name["ods_pay_pay_log_di"]["specification_status"] = "specified"
        errors = SOURCE_ASSETS.validate_commerce_source_dispositions(self.inventory, broken)
        self.assertTrue(any("specification_status must be 'provisional'" in error for error in errors))

        broken = json.loads(json.dumps(contract))
        by_broken_name = {asset["source_asset"]: asset for asset in broken["assets"]}
        by_broken_name["ods_trade_trade_order_di"]["source_evidence"]["detail_anchors"][0]["heading_line"] = 305
        errors = SOURCE_ASSETS.validate_commerce_source_dispositions(self.inventory, broken)
        self.assertTrue(any("source detail evidence differs" in error for error in errors))

    def test_commerce_dispositions_lock_required_authority_corrections(self):
        contract = SOURCE_ASSETS.load_commerce_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        discount = by_name["ods_trade_trade_discount_di"]
        self.assertIn("order.OrderBenefitApplication", discount["canonical_entities"])
        self.assertIn("order.OrderBenefitAllocation", discount["canonical_entities"])
        self.assertIn("order.OrderBenefitFunding", discount["canonical_entities"])
        self.assertEqual("partial", discount["model_status"])
        self.assertTrue(
            discount["runtime_nonempty_reconciliation"]["gate_ref"].endswith(
                "27-canonical-order-benefit-contract.sql"
            )
        )
        self.assertEqual("missing", discount["runtime_nonempty_reconciliation"]["status"])
        self.assertEqual("unverified", discount["verification_status"])
        self.assertEqual(
            {
                "id", "discount_no", "order_no", "sub_order_no", "buyer_id", "discount_type",
                "discount_code", "use_status", "amount", "feature", "create_time", "modify_time",
                "subsidy_info", "pt",
            },
            set(discount["field_dispositions"]),
        )
        self.assertIn("quarantine", discount["field_dispositions"]["amount"]["rule"])
        self.assertIn("positional guessing", discount["field_dispositions"]["subsidy_info"]["rule"])
        self.assertEqual("reject_raw", discount["field_dispositions"]["feature"]["decision"])
        reversal = by_name["ods_refund_refund_discount_df"]
        self.assertIn("original allocation", " ".join(reversal["corrections"]))
        bad_alias = by_name["ods_logistic_logistic_track_structure_di"]
        self.assertEqual("reject", bad_alias["decision"])
        self.assertEqual("rejected", bad_alias["model_status"])
        card = by_name["ods_fin_bind_card_df"]
        self.assertIn("PAN", card["semantic_rules"]["security"])
        for name in ("ods_inventory_sale_df", "ods_inventory_warehouse_df"):
            grain = by_name[name]["semantic_rules"]["grain"]
            for dimension in ("Warehouse", "Location", "Lot", "UOM"):
                self.assertIn(dimension, grain)

    def test_all_commerce_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_commerce_source_dispositions()
        references = [
            reference
            for asset in contract["assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ]
        self.assertEqual(114, len(references))
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_commerce_contract_rejects_missing_duplicate_or_mislabeled_assets(self):
        contract = SOURCE_ASSETS.load_commerce_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["assets"].pop()
        errors = SOURCE_ASSETS.validate_commerce_source_dispositions(self.inventory, missing)
        self.assertTrue(any("differ from authoritative ODS overview" in error for error in errors))

        duplicate = json.loads(json.dumps(contract))
        duplicate["assets"][1] = json.loads(json.dumps(duplicate["assets"][0]))
        errors = SOURCE_ASSETS.validate_commerce_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))

        mislabeled = json.loads(json.dumps(contract))
        mislabeled["assets"][0]["source_labels"] = ["订单"]
        errors = SOURCE_ASSETS.validate_commerce_source_dispositions(self.inventory, mislabeled)
        self.assertTrue(any("source labels differ" in error for error in errors))

    def test_product_dispositions_cover_the_exact_ods_overview_slice(self):
        contract = SOURCE_ASSETS.load_product_source_dispositions()
        expected = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "商品")
        self.assertEqual(10, len(expected))
        self.assertEqual(set(expected), {asset["source_asset"] for asset in contract["assets"]})
        self.assertEqual(
            {"ddl_backed": 9, "name_conflict": 1},
            dict(Counter(asset["source_evidence"]["status"] for asset in contract["assets"])),
        )
        for asset in contract["assets"]:
            observed = expected[asset["source_asset"]]
            self.assertEqual(observed["source_labels"], [asset["source_label"]])
            self.assertIn(
                (asset["source_anchor"]["document"], asset["source_anchor"]["line"]),
                observed["anchors"],
            )

    def test_product_dispositions_keep_authority_and_source_defects_explicit(self):
        contract = SOURCE_ASSETS.load_product_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        application = by_name["ods_goods_goods_new_apply_df"]
        self.assertEqual("split", application["decision"])
        self.assertIn("Catalog owns SPU master", application["semantic_rules"]["authority"])
        self.assertIn("Listing owns sellability", application["semantic_rules"]["authority"])
        result = by_name["ods_goods_goods_operate_result_df"]
        self.assertIn("latest", result["semantic_rules"]["history"])
        salary = by_name["ods_goods_goods_operate_user_salary_settlement_df"]
        self.assertEqual("name_conflict", salary["source_evidence"]["status"])
        self.assertEqual("ods_goods_goods_operate_reject_df", salary["source_evidence"]["detail_anchor"]["source_asset"])
        self.assertEqual("provisional", salary["specification_status"])
        self.assertIn("HR/payroll", salary["semantic_rules"]["authority"])
        import_job = by_name["ods_goods_goods_operate_import_df"]
        self.assertIn("restricted", import_job["semantic_rules"]["security"])
        quality = by_name["ods_goods_goods_quilty_check_df"]
        self.assertTrue(any("misspelled" in correction for correction in quality["corrections"]))

    def test_product_status_is_specified_but_not_runtime_verified(self):
        status = SOURCE_ASSETS.product_disposition_status(self.inventory)
        self.assertEqual(
            {
                "product_source_asset_count": 10,
                "product_detailed_disposition_specified_count": 9,
                "product_runtime_nonempty_reconciled_count": 0,
                "product_final_disposition_verified_count": 0,
                "product_detailed_disposition_percent": 90.0,
                "product_runtime_nonempty_reconciled_percent": 0.0,
                "product_final_disposition_verified_percent": 0.0,
            },
            status,
        )
        contract = SOURCE_ASSETS.load_product_source_dispositions()
        for asset in contract["assets"]:
            self.assertEqual("unverified", asset["verification_status"])
            self.assertEqual("missing", asset["runtime_nonempty_reconciliation"]["status"])

    def test_product_contract_rejects_missing_duplicate_mislabeled_and_false_verification(self):
        contract = SOURCE_ASSETS.load_product_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["assets"].pop()
        errors = SOURCE_ASSETS.validate_product_source_dispositions(self.inventory, missing)
        self.assertTrue(any("differ from authoritative ODS overview" in error for error in errors))

        duplicate = json.loads(json.dumps(contract))
        duplicate["assets"][1] = json.loads(json.dumps(duplicate["assets"][0]))
        errors = SOURCE_ASSETS.validate_product_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))

        mislabeled = json.loads(json.dumps(contract))
        mislabeled["assets"][0]["source_label"] = "商品"
        errors = SOURCE_ASSETS.validate_product_source_dispositions(self.inventory, mislabeled)
        self.assertTrue(any("source label differs" in error for error in errors))

        false_verification = json.loads(json.dumps(contract))
        false_verification["assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_product_source_dispositions(
            self.inventory, false_verification
        )
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))

    def test_all_product_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_product_source_dispositions()
        references = [
            reference
            for asset in contract["assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ]
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_merchant_dispositions_cover_the_exact_duplicated_overview_slice(self):
        contract = SOURCE_ASSETS.load_merchant_source_dispositions()
        expected = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "商家")
        self.assertEqual(7, len(expected))
        self.assertEqual(set(expected), {asset["source_asset"] for asset in contract["assets"]})
        self.assertEqual(
            {"ddl_backed": 6, "name_conflict": 1},
            dict(Counter(asset["source_evidence"]["status"] for asset in contract["assets"])),
        )
        for asset in contract["assets"]:
            observed = expected[asset["source_asset"]]
            self.assertEqual(observed["source_labels"], [asset["source_label"]])
            self.assertEqual(
                observed["anchors"],
                sorted(
                    (anchor["document"], anchor["line"])
                    for anchor in asset["source_anchors"]
                ),
            )

    def test_merchant_dispositions_split_regulated_money_and_ai_authorities(self):
        contract = SOURCE_ASSETS.load_merchant_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        onboarding = by_name["ods_merchant_sys_entry_apply_df"]
        self.assertIn("no Shop may be invented", onboarding["semantic_rules"]["authority"])
        info = by_name["ods_merchant_sys_info_df"]
        self.assertIn("tokenized/restricted", info["semantic_rules"]["security"])
        self.assertIn("independent authorities", " ".join(info["corrections"]))
        withdrawal = by_name["ods_merchant_sys_withdraw_df"]
        self.assertIn("currency is absent", withdrawal["semantic_rules"]["money_or_quantity"])
        self.assertIn("raw card_id", " ".join(withdrawal["corrections"]))
        exit_asset = by_name["ods_merchant_sys_exit_df"]
        self.assertEqual("name_conflict", exit_asset["source_evidence"]["status"])
        self.assertEqual("ods_merchant_sys_withdraw_df", exit_asset["source_evidence"]["detail_anchor"]["source_asset"])
        self.assertEqual("provisional", exit_asset["specification_status"])
        deposit = by_name["ods_merchant_sys_deposit_recharge_df"]
        self.assertIn("amount is STRING", deposit["semantic_rules"]["money_or_quantity"])
        assistant = by_name["ods_merchant_ai_merchant_ai_answer_df"]
        self.assertIn("not a financial fact", assistant["semantic_rules"]["money_or_quantity"])

    def test_merchant_status_is_specified_but_not_runtime_verified(self):
        self.assertEqual(
            {
                "merchant_source_asset_count": 7,
                "merchant_detailed_disposition_specified_count": 6,
                "merchant_runtime_nonempty_reconciled_count": 0,
                "merchant_final_disposition_verified_count": 0,
                "merchant_detailed_disposition_percent": 85.71,
                "merchant_runtime_nonempty_reconciled_percent": 0.0,
                "merchant_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.merchant_disposition_status(self.inventory),
        )
        contract = SOURCE_ASSETS.load_merchant_source_dispositions()
        for asset in contract["assets"]:
            self.assertEqual("unverified", asset["verification_status"])
            self.assertEqual("missing", asset["runtime_nonempty_reconciliation"]["status"])

    def test_merchant_contract_rejects_missing_duplicate_mislabeled_and_false_verification(self):
        contract = SOURCE_ASSETS.load_merchant_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["assets"].pop()
        errors = SOURCE_ASSETS.validate_merchant_source_dispositions(self.inventory, missing)
        self.assertTrue(any("differ from authoritative ODS overview" in error for error in errors))

        duplicate = json.loads(json.dumps(contract))
        duplicate["assets"][1] = json.loads(json.dumps(duplicate["assets"][0]))
        errors = SOURCE_ASSETS.validate_merchant_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))

        mislabeled = json.loads(json.dumps(contract))
        mislabeled["assets"][0]["source_label"] = "商户"
        errors = SOURCE_ASSETS.validate_merchant_source_dispositions(self.inventory, mislabeled)
        self.assertTrue(any("source label differs" in error for error in errors))

        false_verification = json.loads(json.dumps(contract))
        false_verification["assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_merchant_source_dispositions(
            self.inventory, false_verification
        )
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))

    def test_all_merchant_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_merchant_source_dispositions()
        references = [
            reference
            for asset in contract["assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ]
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_coupon_dispositions_cover_every_authoritative_ods_asset(self):
        contract = SOURCE_ASSETS.load_coupon_source_dispositions()
        expected = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "优惠券")
        self.assertEqual(6, len(expected))
        self.assertEqual(set(expected), {asset["source_asset"] for asset in contract["assets"]})
        self.assertEqual(
            {"ddl_backed": 6},
            dict(Counter(asset["source_evidence"]["status"] for asset in contract["assets"])),
        )
        for asset in contract["assets"]:
            observed = expected[asset["source_asset"]]
            self.assertEqual(observed["source_labels"], [asset["source_label"]])
            self.assertIn(
                (asset["source_anchor"]["document"], asset["source_anchor"]["line"]),
                observed["anchors"],
            )

    def test_coupon_dispositions_bind_entitlement_allocation_and_funding(self):
        contract = SOURCE_ASSETS.load_coupon_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        issued = by_name["ods_coupon_coupon_send_di"]
        self.assertIn("versioned schema", " ".join(issued["corrections"]))
        self.assertIn("found_type_code", " ".join(issued["corrections"]))
        template = by_name["ods_coupon_coupon_template_df"]
        self.assertIn("trailing comma", " ".join(template["corrections"]))
        acquisition = by_name["ods_coupon_coupon_snap_di"]
        self.assertIn("does not itself prove", acquisition["semantic_rules"]["authority"])
        refund = by_name["ods_coupon_coupon_refund_di"]
        self.assertIn("exact original Order benefit allocation", " ".join(refund["corrections"]))
        allowance = by_name["ods_coupon_coupon_allowance_di"]
        self.assertIn("do not assume", " ".join(allowance["corrections"]))
        self.assertIn("STRING lacks currency/unit", allowance["semantic_rules"]["money_or_quantity"])

    def test_coupon_status_is_fully_specified_but_not_runtime_verified(self):
        self.assertEqual(
            {
                "coupon_source_asset_count": 6,
                "coupon_detailed_disposition_specified_count": 6,
                "coupon_runtime_nonempty_reconciled_count": 0,
                "coupon_final_disposition_verified_count": 0,
                "coupon_detailed_disposition_percent": 100.0,
                "coupon_runtime_nonempty_reconciled_percent": 0.0,
                "coupon_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.coupon_disposition_status(self.inventory),
        )
        contract = SOURCE_ASSETS.load_coupon_source_dispositions()
        for asset in contract["assets"]:
            self.assertEqual("specified", asset["specification_status"])
            self.assertEqual("unverified", asset["verification_status"])
            self.assertEqual("missing", asset["runtime_nonempty_reconciliation"]["status"])

    def test_coupon_contract_rejects_missing_duplicate_mislabeled_and_false_verification(self):
        contract = SOURCE_ASSETS.load_coupon_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["assets"].pop()
        errors = SOURCE_ASSETS.validate_coupon_source_dispositions(self.inventory, missing)
        self.assertTrue(any("differ from authoritative ODS overview" in error for error in errors))

        duplicate = json.loads(json.dumps(contract))
        duplicate["assets"][1] = json.loads(json.dumps(duplicate["assets"][0]))
        errors = SOURCE_ASSETS.validate_coupon_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))

        mislabeled = json.loads(json.dumps(contract))
        mislabeled["assets"][0]["source_label"] = "券"
        errors = SOURCE_ASSETS.validate_coupon_source_dispositions(self.inventory, mislabeled)
        self.assertTrue(any("source label differs" in error for error in errors))

        false_verification = json.loads(json.dumps(contract))
        false_verification["assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_coupon_source_dispositions(
            self.inventory, false_verification
        )
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))

    def test_all_coupon_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_coupon_source_dispositions()
        references = [
            reference
            for asset in contract["assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ]
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_user_dispositions_cover_every_authoritative_ods_asset(self):
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "用户")
        contract = SOURCE_ASSETS.load_user_source_dispositions()
        detailed = [asset["source_asset"] for asset in contract["ddl_backed_assets"]]
        provisional = [
            asset["source_asset"]
            for group in contract["overview_only_groups"]
            for asset in group["assets"]
        ]
        self.assertEqual(30, len(observed))
        self.assertEqual(2, len(detailed))
        self.assertEqual(28, len(provisional))
        self.assertEqual(set(observed), set(detailed + provisional))
        self.assertEqual([], SOURCE_ASSETS.validate_user_source_dispositions(self.inventory))

    def test_user_dispositions_bind_identity_privacy_and_authentication_boundaries(self):
        contract = SOURCE_ASSETS.load_user_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["ddl_backed_assets"]}
        profile = by_name["ods_user_user_detail_df"]
        login = by_name["ods_user_user_login_di"]
        profile_text = " ".join(profile["corrections"] + list(profile["semantic_rules"].values()))
        login_text = " ".join(login["corrections"] + list(login["semantic_rules"].values()))
        self.assertIn("is_complete", profile_text)
        self.assertIn("idcard", profile_text)
        self.assertIn("immutable authentication observation", login_text)
        self.assertIn("tokenize mobile, IP, device and geolocation", login_text)
        group_rules = {
            asset["source_asset"]: asset["table_rule"]
            for group in contract["overview_only_groups"]
            for asset in group["assets"]
        }
        self.assertIn("Reject password migration", group_rules["ods_userpassword_df"])
        self.assertIn("Order stores an immutable accepted delivery snapshot", group_rules["ods_tb_user_address_df"])
        self.assertIn("biometric material remains outside", group_rules["ods_yshopping_user_ext_tb_ua_authentication_log_df"])

    def test_user_status_is_ddl_limited_and_not_runtime_verified(self):
        self.assertEqual(
            {
                "user_source_asset_count": 30,
                "user_detailed_disposition_specified_count": 2,
                "user_runtime_nonempty_reconciled_count": 0,
                "user_final_disposition_verified_count": 0,
                "user_detailed_disposition_percent": 6.67,
                "user_runtime_nonempty_reconciled_percent": 0.0,
                "user_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.user_disposition_status(self.inventory),
        )

    def test_user_contract_rejects_missing_duplicate_mislabeled_and_false_verification(self):
        contract = SOURCE_ASSETS.load_user_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["overview_only_groups"][0]["assets"].pop()
        errors = SOURCE_ASSETS.validate_user_source_dispositions(self.inventory, missing)
        self.assertTrue(any("differ from authoritative ODS overview" in error for error in errors))

        duplicate = json.loads(json.dumps(contract))
        duplicate["overview_only_groups"][1]["assets"][0] = json.loads(
            json.dumps(duplicate["overview_only_groups"][0]["assets"][0])
        )
        errors = SOURCE_ASSETS.validate_user_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))

        mislabeled = json.loads(json.dumps(contract))
        mislabeled["ddl_backed_assets"][0]["source_label"] = "用户"
        errors = SOURCE_ASSETS.validate_user_source_dispositions(self.inventory, mislabeled)
        self.assertTrue(any("source label differs" in error for error in errors))

        false_verification = json.loads(json.dumps(contract))
        false_verification["ddl_backed_assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_user_source_dispositions(
            self.inventory, false_verification
        )
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))

    def test_all_user_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_user_source_dispositions()
        references = [
            reference
            for asset in contract["ddl_backed_assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ]
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_payment_schema_request_covers_exact_overview_only_payment_assets(self):
        contract = SOURCE_ASSETS.load_payment_source_schema_request()
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "支付")
        governed = set(contract["source_scope"]["already_governed_elsewhere"])
        requested = {asset["source_asset"] for asset in contract["assets"]}
        self.assertEqual(14, len(observed))
        self.assertEqual(12, len(requested))
        self.assertEqual(set(observed) - governed, requested)
        self.assertEqual([], SOURCE_ASSETS.validate_payment_source_schema_request(self.inventory))

    def test_payment_schema_request_requires_ledger_security_and_transport_boundaries(self):
        contract = SOURCE_ASSETS.load_payment_source_schema_request()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        self.assertIn("pan_cvv", " ".join(by_name["ods_fin_bind_card_df"]["required_semantics"]))
        self.assertIn("validated_against_instruction", " ".join(by_name["ods_transfer_queue_df"]["required_semantics"]))
        for name in ("ods_userscashaccountdetail_df", "ods_acc_personal_detail_df", "ods_bom_wallet_flow_log_df"):
            self.assertIn("counter", " ".join(by_name[name]["required_semantics"]))
        self.assertFalse(contract["admission_policy"]["overview_name_is_schema_evidence"])
        self.assertFalse(contract["admission_policy"]["sampled_rows_are_final_evidence"])

    def test_payment_schema_request_rejects_missing_duplicate_and_weakened_security(self):
        contract = SOURCE_ASSETS.load_payment_source_schema_request()
        missing = json.loads(json.dumps(contract))
        missing["assets"].pop()
        errors = SOURCE_ASSETS.validate_payment_source_schema_request(self.inventory, missing)
        self.assertTrue(any("differ from missing-schema" in error for error in errors))
        duplicate = json.loads(json.dumps(contract))
        duplicate["assets"][1] = json.loads(json.dumps(duplicate["assets"][0]))
        errors = SOURCE_ASSETS.validate_payment_source_schema_request(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))
        weakened = json.loads(json.dumps(contract))
        weakened["admission_policy"]["raw_pan_password_otp_or_bank_credentials_are_accepted"] = True
        errors = SOURCE_ASSETS.validate_payment_source_schema_request(self.inventory, weakened)
        self.assertTrue(any("raw_pan_password" in error for error in errors))

    def test_advertising_schema_request_covers_exact_overview_only_assets(self):
        contract = SOURCE_ASSETS.load_advertising_source_schema_request()
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "广告")
        requested = {asset["source_asset"] for asset in contract["assets"]}
        self.assertEqual(7, len(observed))
        self.assertEqual(set(observed), requested)
        self.assertEqual([], SOURCE_ASSETS.validate_advertising_source_schema_request(self.inventory))
        for name in requested:
            logical = next(
                asset for asset in self.inventory["logical_assets"]
                if asset["normalized_name"] == name
            )
            self.assertEqual(1, len(logical["occurrences"]))
            self.assertIn("数据表总览", logical["occurrences"][0]["heading_path"])

    def test_advertising_schema_request_preserves_grain_privacy_and_authority_boundaries(self):
        contract = SOURCE_ASSETS.load_advertising_source_schema_request()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        self.assertIn(
            "bilibill_spelling",
            " ".join(by_name["ods_bilibill_df"]["required_semantics"]),
        )
        self.assertIn(
            "prohibition_on_inferring_conversion_order_or_payment",
            " ".join(by_name["ods_toutiaoevent_df"]["required_semantics"]),
        )
        self.assertIn(
            "exclusion_of_conversion_order_payment_and_settlement_inference",
            " ".join(by_name["ods_xinlangclick_df"]["required_semantics"]),
        )
        kafka = " ".join(by_name["ods_kafka_market_launch_label_di"]["required_semantics"])
        for token in ("topic_partition_offset", "schema_registry", "replay_duplicate", "does_not_authorize"):
            self.assertIn(token, kafka)
        for gate in (
            "platform_name_implies_event_grain",
            "click_or_impression_proves_conversion",
            "attribution_proves_order_or_payment",
            "raw_device_cookie_ip_or_platform_identifier_is_broadly_exposed",
        ):
            self.assertFalse(contract["admission_policy"][gate])

    def test_advertising_disposition_status_is_explicitly_zero_until_schema_arrives(self):
        status = SOURCE_ASSETS.advertising_disposition_status(self.inventory)
        self.assertEqual(7, status["advertising_source_asset_count"])
        self.assertEqual(0, status["advertising_detailed_disposition_specified_count"])
        self.assertEqual(0, status["advertising_runtime_nonempty_reconciled_count"])
        self.assertEqual(0, status["advertising_final_disposition_verified_count"])
        self.assertEqual(0.0, status["advertising_detailed_disposition_percent"])

    def test_advertising_schema_request_rejects_missing_duplicate_weakened_and_evidence_drift(self):
        contract = SOURCE_ASSETS.load_advertising_source_schema_request()
        missing = json.loads(json.dumps(contract))
        missing["assets"].pop()
        errors = SOURCE_ASSETS.validate_advertising_source_schema_request(self.inventory, missing)
        self.assertTrue(any("differ from locked overview assets" in error for error in errors))

        duplicate = json.loads(json.dumps(contract))
        duplicate["assets"][1] = json.loads(json.dumps(duplicate["assets"][0]))
        errors = SOURCE_ASSETS.validate_advertising_source_schema_request(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))

        weakened = json.loads(json.dumps(contract))
        weakened["admission_policy"]["attribution_proves_order_or_payment"] = True
        errors = SOURCE_ASSETS.validate_advertising_source_schema_request(self.inventory, weakened)
        self.assertTrue(any("attribution_proves_order_or_payment" in error for error in errors))

        drifted_inventory = json.loads(json.dumps(self.inventory))
        logical = next(
            asset for asset in drifted_inventory["logical_assets"]
            if asset["normalized_name"] == "ods_xinlangclick_df"
        )
        logical["occurrences"].append(
            {
                "role": "create_target",
                "document": "ODS语兴好物（y shopping）电商数据表.md",
                "line": 9000,
                "heading_path": ["广告", "ods_xinlangclick_df"],
            }
        )
        errors = SOURCE_ASSETS.validate_advertising_source_schema_request(
            drifted_inventory, contract
        )
        self.assertTrue(any("field-level evidence may now exist" in error for error in errors))

    def test_all_advertising_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_advertising_source_schema_request()
        references = [
            reference
            for values in contract["implementation_refs"].values()
            for reference in values
        ]
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_community_dispositions_cover_exact_30_ddl_and_3_name_conflicts(self):
        contract = SOURCE_ASSETS.load_community_source_dispositions()
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "社区")
        ddl_names = {asset["source_asset"] for asset in contract["ddl_backed_assets"]}
        conflict_names = {asset["source_asset"] for asset in contract["name_conflict_assets"]}
        self.assertEqual(33, len(observed))
        self.assertEqual(30, len(ddl_names))
        self.assertEqual(3, len(conflict_names))
        self.assertEqual(set(observed), ddl_names | conflict_names)
        self.assertEqual(
            {
                "ods_community_community_comment_di",
                "ods_community_community_follows_di",
                "ods_community_ecology_selected_audit_result_df",
            },
            conflict_names,
        )
        self.assertEqual([], SOURCE_ASSETS.validate_community_source_dispositions(self.inventory))

    def test_community_profiles_preserve_history_privacy_money_and_effect_authority(self):
        profiles = SOURCE_ASSETS.load_community_source_dispositions()["semantic_profiles"]
        self.assertIn("cannot reconstruct history", profiles["social_interaction"]["history"])
        self.assertIn("only the owning service", profiles["moderation"]["authority"])
        self.assertIn("policy versions", profiles["moderation"]["authority"])
        self.assertIn("consent for model training", profiles["messaging_and_search"]["authority"])
        economy = " ".join(str(value) for value in profiles["live_economy"].values())
        for token in ("ISO currency", "integer minor unit", "Payment", "Ledger", "never proves settlement"):
            self.assertIn(token, economy)
        self.assertIn("cannot impersonate a real user", profiles["ai_red_team"]["authority"])
        self.assertIn("attack production", profiles["ai_red_team"]["authority"])

    def test_community_status_credits_definition_only_not_runtime_or_final(self):
        status = SOURCE_ASSETS.community_disposition_status(self.inventory)
        self.assertEqual(33, status["community_source_asset_count"])
        self.assertEqual(30, status["community_detailed_disposition_specified_count"])
        self.assertEqual(90.91, status["community_detailed_disposition_percent"])
        self.assertEqual(0, status["community_runtime_nonempty_reconciled_count"])
        self.assertEqual(0, status["community_final_disposition_verified_count"])

    def test_community_dispositions_reject_missing_duplicate_weakened_and_conflict_drift(self):
        contract = SOURCE_ASSETS.load_community_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["ddl_backed_assets"].pop()
        errors = SOURCE_ASSETS.validate_community_source_dispositions(self.inventory, missing)
        self.assertTrue(any("differ from authoritative overview" in error for error in errors))

        duplicate = json.loads(json.dumps(contract))
        duplicate["ddl_backed_assets"][1] = json.loads(json.dumps(duplicate["ddl_backed_assets"][0]))
        errors = SOURCE_ASSETS.validate_community_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))

        weakened = json.loads(json.dumps(contract))
        weakened["semantic_profiles"]["moderation"]["authority"] = "model output is final"
        errors = SOURCE_ASSETS.validate_community_source_dispositions(self.inventory, weakened)
        self.assertTrue(any("separate reviewed decision" in error for error in errors))

        drifted_inventory = json.loads(json.dumps(self.inventory))
        logical = next(
            asset for asset in drifted_inventory["logical_assets"]
            if asset["normalized_name"] == "ods_community_community_comment_di"
        )
        logical["occurrences"].append(
            {
                "role": "create_target",
                "document": "ODS语兴好物（y shopping）电商数据表.md",
                "line": 9999,
                "qualified_name": "ods_community_community_comment_di",
            }
        )
        errors = SOURCE_ASSETS.validate_community_source_dispositions(
            drifted_inventory, contract
        )
        self.assertTrue(any("requires reclassification" in error for error in errors))

    def test_all_community_profile_references_resolve(self):
        contract = SOURCE_ASSETS.load_community_source_dispositions()
        references = [
            reference
            for profile in contract["semantic_profiles"].values()
            for key in ("backend_refs", "lakehouse_refs")
            for reference in profile[key]
        ]
        references.append(contract["runtime_nonempty_reconciliation"]["gate_ref"])
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_engagement_dispositions_cover_push_and_collect_assets(self):
        contract = SOURCE_ASSETS.load_engagement_source_dispositions()
        observed = set(SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "推送"))
        observed.update(SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "收藏"))
        names = {asset["source_asset"] for asset in contract["assets"]}
        self.assertEqual(4, len(observed))
        self.assertEqual(observed, names)
        self.assertEqual([], SOURCE_ASSETS.validate_engagement_source_dispositions(self.inventory))

    def test_engagement_dispositions_preserve_delivery_preference_and_price_authority(self):
        contract = SOURCE_ASSETS.load_engagement_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["assets"]}
        sms = " ".join(by_name["ods_push_push_message_log_di"]["corrections"])
        favorite = " ".join(by_name["ods_collect_collect_spu_di"]["corrections"])
        reminder = " ".join(by_name["ods_collect_collect_remind_di"]["corrections"])
        self.assertIn("versioned JSON schema", sms)
        self.assertIn("currency and unit", favorite)
        self.assertIn("trigger-direction dictionary", reminder)
        self.assertIn("separate from trigger evaluation", by_name["ods_collect_collect_remind_di"]["semantic_rules"]["history"])

    def test_engagement_status_is_specified_but_not_runtime_verified(self):
        self.assertEqual(
            {
                "engagement_source_asset_count": 4,
                "engagement_detailed_disposition_specified_count": 4,
                "engagement_runtime_nonempty_reconciled_count": 0,
                "engagement_final_disposition_verified_count": 0,
                "engagement_detailed_disposition_percent": 100.0,
                "engagement_runtime_nonempty_reconciled_percent": 0.0,
                "engagement_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.engagement_disposition_status(self.inventory),
        )

    def test_engagement_contract_rejects_missing_duplicate_and_false_verification(self):
        contract = SOURCE_ASSETS.load_engagement_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["assets"].pop()
        errors = SOURCE_ASSETS.validate_engagement_source_dispositions(self.inventory, missing)
        self.assertTrue(any("differ from authoritative" in error for error in errors))
        duplicate = json.loads(json.dumps(contract))
        duplicate["assets"][1] = json.loads(json.dumps(duplicate["assets"][0]))
        errors = SOURCE_ASSETS.validate_engagement_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))
        false_verification = json.loads(json.dumps(contract))
        false_verification["assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_engagement_source_dispositions(self.inventory, false_verification)
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))

    def test_all_engagement_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_engagement_source_dispositions()
        references = [
            reference
            for asset in contract["assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ]
        self.assertEqual(
            [],
            [(reference, SOURCE_ASSETS._contract_reference_error(reference)) for reference in references if SOURCE_ASSETS._contract_reference_error(reference)],
        )

    def test_compensation_dispositions_cover_overview_and_unadvertised_reason_table(self):
        contract = SOURCE_ASSETS.load_compensation_source_dispositions()
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "赔付")
        governed = {asset["source_asset"] for asset in contract["ddl_backed_assets"]}
        governed.update(asset["source_asset"] for asset in contract["overview_only_assets"])
        self.assertEqual(3, len(observed))
        self.assertEqual(set(observed), governed)
        self.assertEqual("ods_repay_repay_reason_df", contract["unadvertised_detailed_assets"][0]["source_asset"])
        self.assertFalse(contract["unadvertised_detailed_assets"][0]["denominator_credit"])
        self.assertEqual([], SOURCE_ASSETS.validate_compensation_source_dispositions(self.inventory))

    def test_compensation_bill_splits_case_entitlement_execution_and_refund_authority(self):
        contract = SOURCE_ASSETS.load_compensation_source_dispositions()
        bill = contract["ddl_backed_assets"][0]
        corrections = " ".join(bill["corrections"])
        self.assertIn("do not equate compensation with AfterSale or Payment refund", corrections)
        self.assertIn("typed entitlements", corrections)
        self.assertIn("named funder", corrections)
        self.assertIn("Customer Service owns compensation case", bill["semantic_rules"]["authority"])
        self.assertIn("no cross-unit sum", bill["semantic_rules"]["money_or_quantity"])

    def test_compensation_status_is_ddl_limited_and_not_runtime_verified(self):
        self.assertEqual(
            {
                "compensation_source_asset_count": 3,
                "compensation_detailed_disposition_specified_count": 1,
                "compensation_runtime_nonempty_reconciled_count": 0,
                "compensation_final_disposition_verified_count": 0,
                "compensation_detailed_disposition_percent": 33.33,
                "compensation_runtime_nonempty_reconciled_percent": 0.0,
                "compensation_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.compensation_disposition_status(self.inventory),
        )

    def test_compensation_contract_rejects_missing_duplicate_or_false_verification(self):
        contract = SOURCE_ASSETS.load_compensation_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["overview_only_assets"].pop()
        errors = SOURCE_ASSETS.validate_compensation_source_dispositions(self.inventory, missing)
        self.assertTrue(any("exactly two overview-only" in error for error in errors))
        duplicate = json.loads(json.dumps(contract))
        duplicate["overview_only_assets"][1] = json.loads(json.dumps(duplicate["overview_only_assets"][0]))
        errors = SOURCE_ASSETS.validate_compensation_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))
        false_verification = json.loads(json.dumps(contract))
        false_verification["ddl_backed_assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_compensation_source_dispositions(self.inventory, false_verification)
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))

    def test_all_compensation_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_compensation_source_dispositions()
        references = [
            reference
            for asset in contract["ddl_backed_assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ]
        self.assertEqual(
            [],
            [(reference, SOURCE_ASSETS._contract_reference_error(reference)) for reference in references if SOURCE_ASSETS._contract_reference_error(reference)],
        )

    def test_ticket_dispositions_cover_all_assets_and_preserve_four_name_conflicts(self):
        contract = SOURCE_ASSETS.load_ticket_source_dispositions()
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "工单")
        detailed = {asset["source_asset"] for asset in contract["ddl_backed_assets"]}
        conflicts = {asset["source_asset"] for asset in contract["name_conflict_assets"]}
        self.assertEqual(15, len(observed))
        self.assertEqual(11, len(detailed))
        self.assertEqual(4, len(conflicts))
        self.assertEqual(set(observed), detailed | conflicts)
        self.assertEqual([], SOURCE_ASSETS.validate_ticket_source_dispositions(self.inventory))

    def test_ticket_dispositions_reject_credentials_and_ai_decision_fabrication(self):
        contract = SOURCE_ASSETS.load_ticket_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["ddl_backed_assets"]}
        self.assertIn("reject password field entirely", by_name["ods_ticket_ticket_operator_df"]["corrections"])
        self.assertIn("do not promote model result to business decision", by_name["ods_yshopping_model_predict_log_ri"]["corrections"])
        self.assertIn("do not infer account block/refund/remediation effect", " ".join(by_name["ods_ticket_ticket_risk_handle_df"]["corrections"]))
        self.assertIn("remain restricted", contract["semantic_profiles"]["ai_evidence"]["security"])

    def test_ticket_status_is_name_conflict_limited_and_not_runtime_verified(self):
        self.assertEqual(
            {
                "ticket_source_asset_count": 15,
                "ticket_detailed_disposition_specified_count": 11,
                "ticket_runtime_nonempty_reconciled_count": 0,
                "ticket_final_disposition_verified_count": 0,
                "ticket_detailed_disposition_percent": 73.33,
                "ticket_runtime_nonempty_reconciled_percent": 0.0,
                "ticket_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.ticket_disposition_status(self.inventory),
        )

    def test_ticket_contract_rejects_missing_duplicate_and_false_verification(self):
        contract = SOURCE_ASSETS.load_ticket_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["name_conflict_assets"].pop()
        errors = SOURCE_ASSETS.validate_ticket_source_dispositions(self.inventory, missing)
        self.assertTrue(any("exactly four name-conflict" in error for error in errors))
        duplicate = json.loads(json.dumps(contract))
        duplicate["ddl_backed_assets"][1] = json.loads(json.dumps(duplicate["ddl_backed_assets"][0]))
        errors = SOURCE_ASSETS.validate_ticket_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))
        false_verification = json.loads(json.dumps(contract))
        false_verification["ddl_backed_assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_ticket_source_dispositions(self.inventory, false_verification)
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))

    def test_all_ticket_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_ticket_source_dispositions()
        references = [reference for asset in contract["ddl_backed_assets"] for key in ("backend_refs", "lakehouse_refs") for reference in asset[key]]
        self.assertEqual([], [(reference, SOURCE_ASSETS._contract_reference_error(reference)) for reference in references if SOURCE_ASSETS._contract_reference_error(reference)])

    def test_supply_chain_dispositions_cover_all_twenty_three_same_name_ddls(self):
        contract = SOURCE_ASSETS.load_supply_chain_source_dispositions()
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "供应链")
        detailed = {asset["source_asset"] for asset in contract["ddl_backed_assets"]}
        self.assertEqual(23, len(observed))
        self.assertEqual(set(observed), detailed)
        self.assertEqual({"ddl_backed": 23, "name_conflict": 0}, contract["source_scope"]["expected_source_evidence_counts"])
        self.assertEqual([], SOURCE_ASSETS.validate_supply_chain_source_dispositions(self.inventory))

    def test_supply_chain_boundaries_reject_stock_and_ai_authority_fabrication(self):
        contract = SOURCE_ASSETS.load_supply_chain_source_dispositions()
        by_name = {asset["source_asset"]: asset for asset in contract["ddl_backed_assets"]}
        self.assertIn("do not equate P-code unique_id with canonical Lot or SKU", by_name["ods_scm_inbound_di"]["corrections"])
        self.assertIn("source prose says repeated sorting is overwritten so history is incomplete", by_name["ods_scm_sorting_di"]["corrections"])
        self.assertIn("repair trailing comma in DDL before execution", by_name["ods_scm_user_info_df"]["corrections"])
        self.assertIn("do not promote suggest_action_code or ai_result_code to business decision", by_name["ods_scm_quality_ai_analyze_result_di"]["corrections"])
        self.assertIn("Inventory alone accepts the stock movement", contract["semantic_profiles"]["receipt_line"]["authority"])
        self.assertIn("Inventory owns accepted movement ledger", contract["semantic_profiles"]["warehouse_operation"]["authority"])

    def test_supply_chain_status_is_definition_complete_but_not_runtime_verified(self):
        self.assertEqual(
            {
                "supply_chain_source_asset_count": 23,
                "supply_chain_detailed_disposition_specified_count": 23,
                "supply_chain_runtime_nonempty_reconciled_count": 0,
                "supply_chain_final_disposition_verified_count": 0,
                "supply_chain_detailed_disposition_percent": 100.0,
                "supply_chain_runtime_nonempty_reconciled_percent": 0.0,
                "supply_chain_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.supply_chain_disposition_status(self.inventory),
        )

    def test_supply_chain_contract_rejects_missing_duplicate_and_false_verification(self):
        contract = SOURCE_ASSETS.load_supply_chain_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["ddl_backed_assets"].pop()
        errors = SOURCE_ASSETS.validate_supply_chain_source_dispositions(self.inventory, missing)
        self.assertTrue(any("exactly twenty-three" in error for error in errors))
        duplicate = json.loads(json.dumps(contract))
        duplicate["ddl_backed_assets"][1] = json.loads(json.dumps(duplicate["ddl_backed_assets"][0]))
        errors = SOURCE_ASSETS.validate_supply_chain_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))
        false_verification = json.loads(json.dumps(contract))
        false_verification["ddl_backed_assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_supply_chain_source_dispositions(self.inventory, false_verification)
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))
        fabricated_authority = json.loads(json.dumps(contract))
        fabricated_authority["semantic_profiles"]["warehouse_operation"]["authority"] = "WMS owns all stock balances"
        errors = SOURCE_ASSETS.validate_supply_chain_source_dispositions(self.inventory, fabricated_authority)
        self.assertTrue(any("must not become Inventory authority" in error for error in errors))

    def test_all_supply_chain_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_supply_chain_source_dispositions()
        references = [reference for asset in contract["ddl_backed_assets"] for key in ("backend_refs", "lakehouse_refs") for reference in asset[key]]
        self.assertEqual([], [(reference, SOURCE_ASSETS._contract_reference_error(reference)) for reference in references if SOURCE_ASSETS._contract_reference_error(reference)])

    def test_llm_dispositions_lock_fourteen_ddls_and_two_conflicts_without_alias_inference(self):
        contract = SOURCE_ASSETS.load_llm_source_dispositions()
        observed = SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, "大模型")
        detailed = {asset["source_asset"] for asset in contract["ddl_backed_assets"]}
        conflicts = {asset["source_asset"] for asset in contract["name_conflict_assets"]}
        ytoken_detailed = {
            asset["source_asset"]
            for group in contract["ddl_backed_groups"]
            for asset in group["assets"]
        }
        self.assertEqual(16, len(observed))
        self.assertEqual(set(observed), detailed | conflicts | ytoken_detailed)
        self.assertEqual((14, 2), (len(detailed) + len(ytoken_detailed), len(conflicts)))
        self.assertEqual(
            {"ddl_backed": 14, "name_conflict": 2, "overview_only": 0},
            contract["source_scope"]["expected_source_evidence_counts"],
        )
        self.assertEqual([], SOURCE_ASSETS.validate_llm_source_dispositions(self.inventory))

    def test_llm_boundaries_reject_secret_attempt_payment_and_ai_authority_fabrication(self):
        contract = SOURCE_ASSETS.load_llm_source_dispositions()
        detailed = {asset["source_asset"]: asset for asset in contract["ddl_backed_assets"]}
        ytoken = {
            asset["source_asset"]: asset
            for group in contract["ddl_backed_groups"]
            for asset in group["assets"]
        }
        self.assertIn(
            "source samples reuse id across multiple index values",
            " ".join(detailed["ods_ai_workflow_node_executions_di"]["corrections"]),
        )
        self.assertIn(
            "secret values remain in a vault",
            detailed["ods_ai_workflow_workflow_df"]["semantic_rules"]["security"],
        )
        self.assertIn(
            "a top-up row alone is not payment success",
            ytoken["ods_paimon_ytoken_top_up_ri"]["table_rule"],
        )
        self.assertIn(
            "reject password ingestion",
            " ".join(ytoken["ods_paimon_ytoken_user_ri"]["corrections"]),
        )
        self.assertIn(
            "api_key is secret material",
            ytoken["ods_paimon_ytoken_token_ri"]["table_rule"],
        )
        findings = contract["unadvertised_detailed_findings"]
        self.assertEqual(["reject", "derive"], [finding["decision"] for finding in findings])
        self.assertTrue(all(not finding["denominator_credit"] for finding in findings))
        self.assertIn("password_salt", findings[0]["finding"])
        self.assertIn("restricted search-behavior", findings[1]["finding"])

    def test_llm_status_credits_fourteen_same_name_ddls_and_no_runtime_evidence(self):
        self.assertEqual(
            {
                "llm_source_asset_count": 16,
                "llm_detailed_disposition_specified_count": 14,
                "llm_runtime_nonempty_reconciled_count": 0,
                "llm_final_disposition_verified_count": 0,
                "llm_detailed_disposition_percent": 87.5,
                "llm_runtime_nonempty_reconciled_percent": 0.0,
                "llm_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.llm_disposition_status(self.inventory),
        )

    def test_llm_contract_rejects_missing_duplicate_false_verification_and_security_drift(self):
        contract = SOURCE_ASSETS.load_llm_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["ddl_backed_assets"].pop()
        errors = SOURCE_ASSETS.validate_llm_source_dispositions(self.inventory, missing)
        self.assertTrue(any("exactly four" in error for error in errors))
        duplicate = json.loads(json.dumps(contract))
        duplicate["ddl_backed_assets"][1] = json.loads(json.dumps(duplicate["ddl_backed_assets"][0]))
        errors = SOURCE_ASSETS.validate_llm_source_dispositions(self.inventory, duplicate)
        self.assertTrue(any("duplicate source_asset" in error for error in errors))
        false_verification = json.loads(json.dumps(contract))
        false_verification["ddl_backed_assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_llm_source_dispositions(self.inventory, false_verification)
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))
        ytoken_evidence_drift = json.loads(json.dumps(contract))
        ytoken_evidence_drift["ddl_backed_groups"][0]["assets"][0]["detail_anchor"]["heading_line"] = 1
        errors = SOURCE_ASSETS.validate_llm_source_dispositions(self.inventory, ytoken_evidence_drift)
        self.assertTrue(any("detailed evidence differs" in error for error in errors))
        security_drift = json.loads(json.dumps(contract))
        security_drift["unadvertised_detailed_findings"][0]["decision"] = "reuse"
        errors = SOURCE_ASSETS.validate_llm_source_dispositions(self.inventory, security_drift)
        self.assertTrue(any("account or Skill-search finding differs" in error for error in errors))

    def test_all_llm_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_llm_source_dispositions()
        references = [
            reference
            for asset in contract["ddl_backed_assets"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in asset[key]
        ] + [
            reference
            for group in contract["ddl_backed_groups"]
            for key in ("backend_refs", "lakehouse_refs")
            for reference in group[key]
        ]
        self.assertEqual(
            [],
            [
                (reference, SOURCE_ASSETS._contract_reference_error(reference))
                for reference in references
                if SOURCE_ASSETS._contract_reference_error(reference)
            ],
        )

    def test_operations_intelligence_dispositions_lock_five_ddls_one_conflict_and_one_overview(self):
        contract = SOURCE_ASSETS.load_operations_intelligence_source_dispositions()
        observed = {}
        for domain in ("算法", "中台", "情报系统"):
            observed.update(SOURCE_ASSETS.authoritative_ods_domain_assets(self.inventory, domain))
        detailed = {asset["source_asset"] for asset in contract["ddl_backed_assets"]}
        conflicts = {asset["source_asset"] for asset in contract["name_conflict_assets"]}
        overview = {asset["source_asset"] for asset in contract["overview_only_assets"]}
        self.assertEqual(7, len(observed))
        self.assertEqual(set(observed), detailed | conflicts | overview)
        self.assertEqual((5, 1, 1), (len(detailed), len(conflicts), len(overview)))
        self.assertEqual([], SOURCE_ASSETS.validate_operations_intelligence_source_dispositions(self.inventory))

    def test_operations_intelligence_boundaries_keep_models_and_clusters_advisory(self):
        contract = SOURCE_ASSETS.load_operations_intelligence_source_dispositions()
        detailed = {asset["source_asset"]: asset for asset in contract["ddl_backed_assets"]}
        algorithm = contract["overview_only_assets"][0]
        self.assertIn("never directly blocks users", detailed["ods_intelligence_model_result_df"]["semantic_rules"]["authority"])
        self.assertIn("cannot prove cluster membership", algorithm["table_rule"])
        self.assertIn("missing comma", " ".join(detailed["ods_discover_ng_monitor_rule_data_ri"]["corrections"]))
        self.assertIn("seven-day source retention", " ".join(detailed["ods_yeyes_alarm_record_df"]["corrections"]))

    def test_operations_intelligence_status_is_definition_only(self):
        self.assertEqual(
            {
                "operations_intelligence_source_asset_count": 7,
                "operations_intelligence_detailed_disposition_specified_count": 5,
                "operations_intelligence_runtime_nonempty_reconciled_count": 0,
                "operations_intelligence_final_disposition_verified_count": 0,
                "operations_intelligence_detailed_disposition_percent": 71.43,
                "operations_intelligence_runtime_nonempty_reconciled_percent": 0.0,
                "operations_intelligence_final_disposition_verified_percent": 0.0,
            },
            SOURCE_ASSETS.operations_intelligence_disposition_status(self.inventory),
        )

    def test_operations_intelligence_contract_rejects_evidence_and_authority_drift(self):
        contract = SOURCE_ASSETS.load_operations_intelligence_source_dispositions()
        missing = json.loads(json.dumps(contract))
        missing["ddl_backed_assets"].pop()
        errors = SOURCE_ASSETS.validate_operations_intelligence_source_dispositions(self.inventory, missing)
        self.assertTrue(any("exactly five" in error for error in errors))
        evidence_drift = json.loads(json.dumps(contract))
        evidence_drift["ddl_backed_assets"][0]["source_evidence"]["detail_anchor"]["heading_line"] = 1
        errors = SOURCE_ASSETS.validate_operations_intelligence_source_dispositions(self.inventory, evidence_drift)
        self.assertTrue(any("detailed evidence differs" in error for error in errors))
        false_verification = json.loads(json.dumps(contract))
        false_verification["ddl_backed_assets"][0]["verification_status"] = "verified"
        errors = SOURCE_ASSETS.validate_operations_intelligence_source_dispositions(self.inventory, false_verification)
        self.assertTrue(any("forbidden without governed reconciliation" in error for error in errors))
        authority_drift = json.loads(json.dumps(contract))
        authority_drift["ddl_backed_assets"][3]["semantic_rules"]["authority"] = "model blocks users"
        errors = SOURCE_ASSETS.validate_operations_intelligence_source_dispositions(self.inventory, authority_drift)
        self.assertTrue(any("direct business authority" in error for error in errors))

    def test_all_operations_intelligence_implementation_references_resolve(self):
        contract = SOURCE_ASSETS.load_operations_intelligence_source_dispositions()
        references = [reference for asset in contract["ddl_backed_assets"] for key in ("backend_refs", "lakehouse_refs") for reference in asset[key]]
        self.assertEqual([], [(reference, SOURCE_ASSETS._contract_reference_error(reference)) for reference in references if SOURCE_ASSETS._contract_reference_error(reference)])

    def test_qualified_names_and_markdown_bold_are_parsed_without_losing_source_location(self):
        assets = {item["asset_id"]: item for item in self.inventory["assets"]}
        login = assets["ods:create_target:ods_user_user_login_di"]
        self.assertEqual(1917, login["occurrences"][0]["line"])
        self.assertEqual("yshopping.ods_user_user_login_di", login["occurrences"][0]["qualified_name"])
        order = assets["dws:create_target:dws_trade_order_buyer_target_1d"]
        self.assertEqual("yshopping.dws_trade_order_buyer_target_1d", order["occurrences"][0]["qualified_name"])

    def test_source_drift_is_rejected_against_a_manifest_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {"source_documents": []}
            for layer, filename in SOURCE_ASSETS.LAYER_DOCUMENTS.items():
                path = root / filename
                path.write_text("# source\nCREATE TABLE sample_table (id BIGINT);\n", encoding="utf-8")
                manifest["source_documents"].append(
                    {
                        "filename": filename,
                        "sha256": SOURCE_ASSETS.sha256(path),
                        "line_count": 2,
                    }
                )
            inventory = SOURCE_ASSETS.extract_inventory(root)
            self.assertEqual([], SOURCE_ASSETS.validate_inventory(inventory, manifest))
            broken = json.loads(json.dumps(manifest))
            broken["source_documents"][0]["sha256"] = "0" * 64
            errors = SOURCE_ASSETS.validate_inventory(inventory, broken)
            self.assertTrue(any("source drift" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
