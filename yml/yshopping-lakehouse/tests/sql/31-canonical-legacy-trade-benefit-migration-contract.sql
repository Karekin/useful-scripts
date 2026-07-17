SELECT 'canonical_legacy_trade_candidate_identity_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event
WHERE candidate_id <> payload_candidate_id OR source_scope <> 'LOCAL_YUDAO_TRADE_CURRENT'
   OR canonical_import_allowed OR candidate_version <> 1;

SELECT 'canonical_legacy_trade_denominator_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment
WHERE source_order_row_count <> non_deleted_order_count + deleted_excluded_count
   OR non_deleted_order_count <> no_benefit_order_count
        + benefit_evidence_pending_order_count + quarantined_order_count;

SELECT 'canonical_legacy_trade_component_amount_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment
WHERE source_benefit_amount_minor <> component_amount_minor
   OR component_count <> unresolved_identity_count OR component_count <> unresolved_funding_count
   OR import_allowed_component_count <> 0 OR production_migration_enabled;

SELECT 'canonical_legacy_trade_backend_offline_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_benefit_migration_readiness
WHERE reconciliation_status <> 'MATCHED_LOCAL_SNAPSHOT_BLOCKED_REQUIRES_GOVERNED_EVIDENCE'
   OR missing_offline_candidate_count <> 0 OR missing_backend_candidate_count <> 0
   OR candidate_fact_mismatch_count <> 0 OR missing_offline_component_count <> 0
   OR missing_backend_component_count <> 0 OR component_fact_mismatch_count <> 0;

SELECT 'canonical_legacy_trade_false_import_readiness' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_benefit_migration_readiness
WHERE exact_order_item_mapping_available OR versioned_benefit_identity_available
   OR named_funding_breakdown_available OR governed_scope <> 'LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE';

SELECT 'canonical_legacy_trade_item_denominator_incomplete' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment
WHERE item_evidence_complete
  AND (source_item_count <> active_item_count + excluded_item_count
    OR (declared_source_item_count IS NOT NULL AND source_item_count <> declared_source_item_count)
    OR (declared_active_item_count IS NOT NULL AND active_item_count <> declared_active_item_count)
    OR (declared_excluded_item_count IS NOT NULL AND excluded_item_count <> declared_excluded_item_count)
    OR (declared_item_benefit_amount_minor IS NOT NULL
        AND item_benefit_amount_minor <> declared_item_benefit_amount_minor)
    OR (item_evidence_hash IS NOT NULL AND LENGTH(item_evidence_hash) <> 64)
    OR source_item_count <= 0 OR import_allowed_item_count <> 0);

SELECT 'canonical_legacy_trade_item_identity_or_import_open' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment
WHERE canonical_import_allowed
   OR legacy_order_item_id IS NULL OR legacy_item_snapshot_hash IS NULL
   OR source_product_identity_status NOT IN ('SOURCE_IDS_PRESENT','MISSING_SOURCE_IDS');
