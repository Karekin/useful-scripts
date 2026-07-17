CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_legacy_trade_product_identity AS
SELECT
    tenant_id,
    identity_run_id,
    MAX(source_migration_run_id) AS source_migration_run_id,
    COUNT(*) AS source_item_count,
    SUM(CASE WHEN source_pair_status <> 'EXCLUDED' THEN 1 ELSE 0 END) AS active_item_count,
    SUM(CASE WHEN source_pair_status = 'EXCLUDED' THEN 1 ELSE 0 END) AS excluded_item_count,
    SUM(CASE WHEN source_pair_status = 'SOURCE_PAIR_UNAMBIGUOUS_NOT_HISTORICAL_VERSION'
                  THEN 1 ELSE 0 END) AS source_pair_unambiguous_count,
    SUM(CASE WHEN source_pair_status = 'SOURCE_SKU_PARENT_CONFLICT'
                  THEN 1 ELSE 0 END) AS source_parent_conflict_item_count,
    SUM(CASE WHEN source_pair_status = 'SOURCE_IDS_MISSING'
                  THEN 1 ELSE 0 END) AS source_ids_missing_item_count,
    SUM(CASE WHEN current_reference_status = 'CURRENT_RELATION_OBSERVED_NOT_HISTORICAL_VERSION'
                  THEN 1 ELSE 0 END) AS current_relation_observed_count,
    SUM(CASE WHEN current_reference_status = 'CURRENT_RELATION_MISSING_OR_MISMATCH'
                  THEN 1 ELSE 0 END) AS current_relation_missing_or_mismatch_count,
    SUM(CASE WHEN historical_identity_status = 'QUALIFIED' THEN 1 ELSE 0 END)
        AS historical_identity_qualified_count,
    SUM(CASE WHEN historical_identity_status = 'MISSING' THEN 1 ELSE 0 END)
        AS historical_identity_missing_count,
    SUM(CASE WHEN historical_identity_status = 'AMBIGUOUS' THEN 1 ELSE 0 END)
        AS historical_identity_ambiguous_count,
    SUM(CASE WHEN identity_admission_allowed THEN 1 ELSE 0 END) AS identity_admitted_item_count,
    SUM(CASE WHEN target_mapping_allowed THEN 1 ELSE 0 END) AS target_mapping_allowed_item_count,
    MAX(run_source_item_count) AS reported_source_item_count,
    MAX(run_active_item_count) AS reported_active_item_count,
    MAX(run_source_pair_unambiguous_count) AS reported_source_pair_unambiguous_count,
    MAX(run_source_parent_conflict_item_count) AS reported_source_parent_conflict_item_count,
    MAX(run_current_relation_observed_count) AS reported_current_relation_observed_count,
    MAX(run_historical_identity_qualified_count) AS reported_historical_identity_qualified_count,
    MAX(run_identity_admitted_item_count) AS reported_identity_admitted_item_count,
    MAX(target_mapping_enabled) AS target_mapping_enabled,
    MAX(run_status) AS run_status,
    MAX(governance_evidence_hash) AS governance_evidence_hash,
    MAX(assessed_at) AS assessed_at,
    'CANONICAL_LEGACY_TRADE_PRODUCT_IDENTITY_GOVERNANCE' AS model_semantics
FROM yshopping_dwd.dwd_canonical_legacy_trade_product_identity_event
GROUP BY tenant_id, identity_run_id;
