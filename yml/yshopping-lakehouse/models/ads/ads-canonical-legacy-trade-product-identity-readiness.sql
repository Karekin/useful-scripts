CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_legacy_trade_product_identity_readiness AS
SELECT
    tenant_id,
    identity_run_id,
    source_migration_run_id,
    source_item_count,
    active_item_count,
    excluded_item_count,
    source_pair_unambiguous_count,
    source_parent_conflict_item_count,
    source_ids_missing_item_count,
    current_relation_observed_count,
    current_relation_missing_or_mismatch_count,
    historical_identity_qualified_count,
    historical_identity_missing_count,
    historical_identity_ambiguous_count,
    identity_admitted_item_count,
    target_mapping_allowed_item_count,
    governance_evidence_hash,
    CASE
      WHEN source_item_count <> active_item_count + excluded_item_count
        OR source_item_count <> reported_source_item_count
        OR active_item_count <> reported_active_item_count
        THEN 'BLOCKED_SOURCE_DENOMINATOR_MISMATCH'
      WHEN source_pair_unambiguous_count <> reported_source_pair_unambiguous_count
        OR source_parent_conflict_item_count <> reported_source_parent_conflict_item_count
        OR current_relation_observed_count <> reported_current_relation_observed_count
        OR historical_identity_qualified_count <> reported_historical_identity_qualified_count
        OR identity_admitted_item_count <> reported_identity_admitted_item_count
        THEN 'BLOCKED_REPORTED_ROLLUP_MISMATCH'
      WHEN identity_admitted_item_count <> target_mapping_allowed_item_count
        OR identity_admitted_item_count <> historical_identity_qualified_count
        OR (target_mapping_enabled AND identity_admitted_item_count <> active_item_count)
        THEN 'BLOCKED_ILLEGAL_IDENTITY_ADMISSION'
      WHEN identity_admitted_item_count = active_item_count AND active_item_count > 0
        THEN 'READY_FOR_TARGET_MAPPING_ASSESSMENT'
      ELSE 'BLOCKED_REQUIRES_HISTORICAL_PRODUCT_IDENTITY'
    END AS readiness_status,
    identity_admitted_item_count = active_item_count AND active_item_count > 0
        AS exact_historical_product_identity_available,
    target_mapping_enabled,
    FALSE AS canonical_import_available,
    FALSE AS production_migration_enabled,
    'CURRENT_CATALOG_RELATION_IS_OBSERVATION_ONLY' AS current_relation_semantics,
    'LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE' AS governed_scope,
    'CANONICAL_LEGACY_TRADE_PRODUCT_IDENTITY_ADMISSION' AS model_semantics
FROM yshopping_dws.dws_canonical_legacy_trade_product_identity;
