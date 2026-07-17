CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_legacy_trade_target_readiness AS
SELECT
    target.tenant_id,
    target.target_readiness_run_id,
    target.source_migration_run_id,
    target.source_order_count,
    target.active_order_count,
    target.excluded_order_count,
    target.buyer_resolved_order_count,
    target.buyer_missing_order_count,
    target.buyer_ambiguous_order_count,
    target.order_mapping_qualified_count,
    target.lifecycle_mapping_qualified_count,
    target.exact_money_order_count,
    target.source_item_count,
    target.active_item_count,
    target.excluded_item_count,
    target.historical_product_identity_qualified_item_count,
    target.historical_product_identity_unqualified_item_count,
    target.spu_mapping_qualified_item_count,
    target.sku_mapping_qualified_item_count,
    target.order_item_mapping_qualified_count,
    target.exact_money_item_count,
    target.fully_mapped_item_count,
    target.mapping_admitted_order_count,
    target.mapping_blocked_order_count,
    target.mapping_admitted_item_count,
    target.canonical_import_allowed_order_count,
    target.canonical_import_allowed_item_count,
    target.target_mapping_evidence_hash,
    CASE
      WHEN source.migration_run_id IS NULL THEN 'BLOCKED_SOURCE_ASSESSMENT_MISSING'
      WHEN target.source_order_count <> source.source_order_row_count
        OR target.active_order_count <> source.non_deleted_order_count
        OR target.excluded_order_count <> source.deleted_excluded_count
        OR target.source_item_count <> source.source_item_count
        OR target.active_item_count <> source.active_item_count
        OR target.excluded_item_count <> source.excluded_item_count
        THEN 'BLOCKED_SOURCE_DENOMINATOR_MISMATCH'
      WHEN target.canonical_import_allowed_order_count <> 0
        OR target.canonical_import_allowed_item_count <> 0 OR target.production_migration_enabled
        THEN 'BLOCKED_ILLEGAL_IMPORT_AUTHORITY'
      WHEN NOT source.product_snapshot_evidence_complete
        OR source.product_snapshot_captured_item_count <> source.source_item_count
        OR source.product_snapshot_incomplete_item_count <> 0
        OR source.product_snapshot_evidence_hash IS NULL
        THEN 'BLOCKED_PRODUCT_SNAPSHOT_EVIDENCE_INCOMPLETE'
      WHEN target.historical_product_identity_qualified_item_count <> target.active_item_count
        OR target.historical_product_identity_unqualified_item_count <> 0
        THEN 'BLOCKED_HISTORICAL_PRODUCT_IDENTITY_NOT_QUALIFIED'
      WHEN target.mapping_admitted_order_count = target.active_order_count
        AND target.mapping_admitted_item_count = target.active_item_count
        THEN 'TARGET_MAPPING_READY_BUT_BENEFIT_GOVERNANCE_BLOCKED'
      ELSE 'BLOCKED_REQUIRES_EXPLICIT_TARGET_MAPPINGS'
    END AS readiness_status,
    target.mapping_admitted_order_count = target.active_order_count
      AND target.mapping_admitted_item_count = target.active_item_count
      AND target.historical_product_identity_qualified_item_count = target.active_item_count
      AS exact_target_mapping_available,
    FALSE AS canonical_import_available,
    FALSE AS production_migration_enabled,
    'LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE' AS governed_scope,
    'CANONICAL_LEGACY_TRADE_TARGET_MAPPING_ADMISSION' AS model_semantics
FROM yshopping_dws.dws_canonical_legacy_trade_target_readiness target
LEFT JOIN yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment source
  ON source.tenant_id = target.tenant_id
 AND source.migration_run_id = target.source_migration_run_id;
