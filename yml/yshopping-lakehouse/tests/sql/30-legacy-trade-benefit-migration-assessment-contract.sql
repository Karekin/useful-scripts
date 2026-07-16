SELECT 'legacy_trade_source_to_assessment_count_mismatch' AS check_name,
       ABS((SELECT COUNT(*) FROM yshopping_ods.trade_order)
         - (SELECT COUNT(*) FROM yshopping_dwd.dwd_legacy_trade_benefit_assessment)) AS violations;

SELECT 'legacy_trade_order_key_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT legacy_order_key
    FROM yshopping_dwd.dwd_legacy_trade_benefit_assessment
    GROUP BY legacy_order_key
    HAVING COUNT(*) <> 1
) duplicate_keys;

SELECT 'legacy_trade_non_deleted_denominator_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_legacy_trade_benefit_migration_assessment
WHERE non_deleted_order_count
      <> no_benefit_order_count + benefit_evidence_pending_order_count + quarantined_order_count;

SELECT 'legacy_trade_component_amount_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_trade_benefit_migration_readiness
WHERE source_benefit_amount_minor <> component_amount_minor;

SELECT 'legacy_trade_invalid_component_marked_importable' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_legacy_trade_benefit_component_assessment
WHERE canonical_import_allowed <> FALSE
   OR identity_resolution_status = 'RESOLVED'
   OR funding_resolution_status = 'RESOLVED';

SELECT 'legacy_trade_false_migration_readiness' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_legacy_trade_benefit_migration_readiness
WHERE production_migration_enabled <> FALSE
   OR exact_order_item_mapping_available <> FALSE
   OR versioned_benefit_identity_available <> FALSE
   OR named_funding_breakdown_available <> FALSE
   OR (benefit_evidence_pending_order_count > 0 AND readiness_status <> 'BLOCKED_REQUIRES_GOVERNED_EVIDENCE')
   OR source_scope <> 'LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE';
