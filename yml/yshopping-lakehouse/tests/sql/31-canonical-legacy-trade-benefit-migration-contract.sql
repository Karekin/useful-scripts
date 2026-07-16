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
