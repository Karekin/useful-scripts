SELECT 'canonical_legacy_trade_product_identity_event_shape' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_legacy_trade_product_identity_event
WHERE identity_item_id<>payload_identity_item_id OR identity_version<>1 OR schema_version<>1
   OR policy_version<>'legacy-trade-product-identity-v1'
   OR source_item_evidence_hash NOT REGEXP '^[0-9a-f]{64}$'
   OR evidence_hash NOT REGEXP '^[0-9a-f]{64}$'
   OR governance_evidence_hash NOT REGEXP '^[0-9a-f]{64}$';

SELECT 'canonical_legacy_trade_product_identity_denominator_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_product_identity
WHERE source_item_count<>active_item_count+excluded_item_count
   OR active_item_count<>source_pair_unambiguous_count+source_parent_conflict_item_count
                        +source_ids_missing_item_count
   OR active_item_count<>historical_identity_qualified_count+historical_identity_missing_count
                        +historical_identity_ambiguous_count;

SELECT 'canonical_legacy_trade_product_identity_reported_rollup_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_legacy_trade_product_identity
WHERE source_item_count<>reported_source_item_count
   OR active_item_count<>reported_active_item_count
   OR source_pair_unambiguous_count<>reported_source_pair_unambiguous_count
   OR source_parent_conflict_item_count<>reported_source_parent_conflict_item_count
   OR current_relation_observed_count<>reported_current_relation_observed_count
   OR historical_identity_qualified_count<>reported_historical_identity_qualified_count
   OR identity_admitted_item_count<>reported_identity_admitted_item_count;

SELECT 'canonical_legacy_trade_product_identity_qualification_shape' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_product_identity_item
WHERE (historical_identity_status='QUALIFIED' AND (
          qualification_id IS NULL OR NOT identity_admission_allowed OR NOT target_mapping_allowed
          OR blocker_codes<>'[]'))
   OR (historical_identity_status IN ('MISSING','AMBIGUOUS','EXCLUDED') AND (
          qualification_id IS NOT NULL OR identity_admission_allowed OR target_mapping_allowed));

SELECT 'canonical_legacy_trade_product_identity_current_observation_shape' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_legacy_trade_product_identity_item
WHERE (current_reference_status='CURRENT_RELATION_OBSERVED_NOT_HISTORICAL_VERSION'
       AND current_product_snapshot_hash NOT REGEXP '^[0-9a-f]{64}$')
   OR (current_reference_status<>'CURRENT_RELATION_OBSERVED_NOT_HISTORICAL_VERSION'
       AND current_product_snapshot_hash IS NOT NULL);

SELECT 'canonical_legacy_trade_product_identity_illegal_admission' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_product_identity_readiness
WHERE identity_admitted_item_count<>target_mapping_allowed_item_count
   OR identity_admitted_item_count<>historical_identity_qualified_count
   OR (target_mapping_enabled AND identity_admitted_item_count<>active_item_count)
   OR canonical_import_available OR production_migration_enabled;

SELECT 'canonical_legacy_trade_product_identity_false_readiness' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_legacy_trade_product_identity_readiness
WHERE readiness_status='READY_FOR_TARGET_MAPPING_ASSESSMENT'
  AND (NOT exact_historical_product_identity_available OR NOT target_mapping_enabled
       OR identity_admitted_item_count<>active_item_count);
