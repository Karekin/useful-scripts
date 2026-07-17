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

SELECT 'canonical_legacy_trade_item_component_reconciliation_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_component_reconciliation
WHERE component_type NOT IN ('GENERIC_DISCOUNT','COUPON','POINT','VIP')
   OR reconciliation_id NOT REGEXP '^[0-9a-f]{64}$'
   OR reconciliation_hash NOT REGEXP '^[0-9a-f]{64}$'
   OR source_item_component_row_count < 0 OR item_component_row_count < 0
   OR excluded_item_component_row_count < 0
   OR source_item_component_row_count
        <> item_component_row_count + excluded_item_component_row_count
   OR source_item_component_amount_minor
        <> item_component_amount_minor + excluded_item_component_amount_minor
   OR header_component_count NOT IN (0,1)
   OR reconciliation_status NOT IN ('MATCHED','MISSING_ITEM_COMPONENT','MISSING_HEADER_COMPONENT',
                                     'AMOUNT_MISMATCH','EXCLUDED_SOURCE_ORDER_DELETED',
                                     'EXCLUDED_SOURCE_ITEM_DELETED')
   OR canonical_import_allowed;

SELECT 'canonical_legacy_trade_unquarantined_item_component_difference' AS check_name,
       COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_component_reconciliation
WHERE reconciliation_status NOT IN ('MATCHED','EXCLUDED_SOURCE_ORDER_DELETED',
                                     'EXCLUDED_SOURCE_ITEM_DELETED')
  AND order_assessment_status NOT LIKE 'QUARANTINED_%';

SELECT 'canonical_legacy_trade_item_component_rollup_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment
WHERE item_evidence_complete
  AND (item_component_reconciliation_count
        <> matched_component_type_count + excluded_component_type_count + mismatched_component_type_count
   OR active_item_component_row_count > source_item_component_row_count
   OR item_header_component_gap_minor <> item_benefit_amount_minor - component_amount_minor
   OR import_allowed_item_component_count <> 0);

SELECT 'canonical_legacy_trade_v4_buyer_lineage_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event
WHERE schema_version = 3
  AND (policy_version <> 'legacy-trade-benefit-v4' OR source_created_at IS NULL OR legacy_buyer_id <= 0
    OR legacy_order_status IS NULL OR buyer_identity_status NOT IN ('RESOLVED','MISSING','AMBIGUOUS')
    OR (buyer_identity_status = 'RESOLVED'
      AND (buyer_source_identity_id IS NULL OR buyer_principal_id IS NULL OR buyer_identity_version <= 0))
    OR (buyer_identity_status <> 'RESOLVED'
      AND (buyer_source_identity_id IS NOT NULL OR buyer_principal_id IS NOT NULL
        OR buyer_identity_version IS NOT NULL)));

SELECT 'canonical_legacy_trade_v4_item_buyer_lineage_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment item
JOIN yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event event
  ON event.tenant_id=item.tenant_id AND event.migration_run_id=item.migration_run_id
 AND event.candidate_id=item.candidate_id
WHERE event.schema_version=3 AND item.legacy_buyer_id<>event.legacy_buyer_id;

SELECT 'canonical_legacy_trade_v4_buyer_rollup_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment
WHERE buyer_lineage_complete
  AND buyer_lineage_order_count
      <>resolved_buyer_identity_order_count+missing_buyer_identity_order_count
        +ambiguous_buyer_identity_order_count;

SELECT 'canonical_legacy_trade_v5_product_snapshot_run_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event
WHERE schema_version = 4
  AND (policy_version <> 'legacy-trade-benefit-v5'
    OR NOT run_product_snapshot_evidence_complete
    OR run_product_snapshot_captured_item_count <> run_source_item_count
    OR run_product_snapshot_incomplete_item_count <> 0
    OR run_product_snapshot_evidence_hash NOT REGEXP '^[0-9a-f]{64}$');

SELECT 'canonical_legacy_trade_v5_product_snapshot_item_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment item
JOIN yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event event
  ON event.tenant_id=item.tenant_id AND event.migration_run_id=item.migration_run_id
 AND event.candidate_id=item.candidate_id
WHERE event.schema_version = 4
  AND (item.source_created_at IS NULL OR item.legacy_spu_id <= 0 OR item.legacy_sku_id <= 0
    OR item.legacy_spu_name IS NULL OR TRIM(item.legacy_spu_name) = ''
    OR item.unit_price_minor < 0 OR item.product_snapshot_status <> 'CAPTURED'
    OR item.product_snapshot_semantics <> 'ORDER_ITEM_ACCEPTED_PRODUCT_SNAPSHOT_V1'
    OR item.historical_product_snapshot_hash NOT REGEXP '^[0-9a-f]{64}$');

SELECT 'canonical_legacy_trade_v5_product_snapshot_rollup_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment
WHERE product_snapshot_evidence_complete
  AND (product_snapshot_captured_item_count <> source_item_count
    OR product_snapshot_incomplete_item_count <> 0
    OR product_snapshot_captured_item_count <> declared_product_snapshot_captured_item_count
    OR product_snapshot_incomplete_item_count <> declared_product_snapshot_incomplete_item_count
    OR product_snapshot_evidence_hash NOT REGEXP '^[0-9a-f]{64}$');
