import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "sourceassetctl"
LOADER = importlib.machinery.SourceFileLoader("sourceassetctl", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
SOURCE_ASSETS = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(SOURCE_ASSETS)


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
        self.assertEqual(713, status["domain_routed_asset_count"])
        self.assertEqual(322, status["heading_lineage_inferred_asset_count"])
        self.assertEqual(112, status["explicit_asset_route_count"])
        self.assertEqual(110, status["bounded_domain_asset_count"])
        self.assertEqual(5, status["explicit_rejection_count"])
        self.assertEqual(718, status["preliminary_handled_count"])
        self.assertEqual(48, status["detailed_disposition_specified_count"])
        self.assertEqual(0, status["runtime_nonempty_reconciled_count"])
        self.assertEqual(0, status["final_disposition_verified_count"])
        self.assertEqual(99.3, status["routing_percent"])
        self.assertEqual(100.0, status["preliminary_handled_percent"])
        self.assertEqual(6.69, status["detailed_disposition_specified_percent"])
        self.assertEqual(0.0, status["runtime_nonempty_reconciled_percent"])
        self.assertEqual(0.0, status["final_disposition_percent"])
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
        self.assertTrue(any("commerce=0/35; routing is not completion" in line for line in lines))

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
            evidence = Path(directory) / "reconciliation.json"
            evidence.write_text('{"row_count": 7, "tenant_count": 1}', encoding="utf-8")
            proven = json.loads(json.dumps(contract))
            runtime = proven["assets"][0]["runtime_nonempty_reconciliation"]
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
