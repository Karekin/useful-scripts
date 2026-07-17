SELECT 'canonical_legacy_trade_target_order_identity_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_legacy_trade_target_readiness_event
WHERE order_readiness_id <> payload_order_readiness_id OR readiness_version <> 1
   OR (schema_version=1 AND policy_version <> 'legacy-trade-target-readiness-v1')
   OR (schema_version=2 AND policy_version <> 'legacy-trade-target-readiness-v2')
   OR evidence_hash NOT REGEXP '^[0-9a-f]{64}$' OR canonical_import_allowed;

SELECT 'canonical_legacy_trade_target_order_denominator_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_target_readiness
WHERE source_order_count <> active_order_count + excluded_order_count
   OR active_order_count <> mapping_admitted_order_count + mapping_blocked_order_count
   OR buyer_resolved_order_count + buyer_missing_order_count + buyer_ambiguous_order_count
        <> active_order_count;

SELECT 'canonical_legacy_trade_target_item_denominator_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_target_readiness
WHERE source_item_count <> active_item_count + excluded_item_count
   OR active_item_count <> historical_product_identity_qualified_item_count
                          + historical_product_identity_unqualified_item_count
   OR fully_mapped_item_count <> mapping_admitted_item_count
   OR fully_mapped_item_count > active_item_count;

SELECT 'canonical_legacy_trade_target_item_shape_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_target_readiness_item
WHERE evidence_hash NOT REGEXP '^[0-9a-f]{64}$' OR canonical_import_allowed
   OR mapping_readiness_status NOT IN ('READY','BLOCKED','EXCLUDED')
   OR (mapping_readiness_status='READY' AND (
       NOT mapping_admission_allowed OR historical_product_identity_status<>'QUALIFIED'
       OR product_identity_qualification_id IS NULL OR spu_mapping_status<>'QUALIFIED'
       OR sku_mapping_status<>'QUALIFIED' OR order_item_mapping_status<>'QUALIFIED'
       OR money_reconciliation_status<>'EXACT'))
   OR (historical_product_identity_status='QUALIFIED'
       AND product_identity_qualification_id IS NULL)
   OR (historical_product_identity_status<>'QUALIFIED'
       AND product_identity_qualification_id IS NOT NULL)
   OR (mapping_readiness_status<>'READY' AND mapping_admission_allowed);

SELECT 'canonical_legacy_trade_target_false_import_readiness' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_target_readiness
WHERE canonical_import_available OR production_migration_enabled
   OR canonical_import_allowed_order_count<>0 OR canonical_import_allowed_item_count<>0
   OR governed_scope<>'LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE';

SELECT 'canonical_legacy_trade_target_historical_identity_fence_missing' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_target_readiness
WHERE (historical_product_identity_qualified_item_count<>active_item_count
       OR historical_product_identity_unqualified_item_count<>0)
  AND readiness_status<>'BLOCKED_HISTORICAL_PRODUCT_IDENTITY_NOT_QUALIFIED';

SELECT 'canonical_legacy_trade_target_source_denominator_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_target_readiness
WHERE readiness_status='BLOCKED_SOURCE_DENOMINATOR_MISMATCH';
