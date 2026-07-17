CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_legacy_trade_target_readiness AS
WITH item_rollup AS (
    SELECT
        tenant_id,
        target_readiness_run_id,
        COUNT(*) AS source_item_count,
        SUM(CASE WHEN mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END) AS active_item_count,
        SUM(CASE WHEN mapping_readiness_status = 'EXCLUDED' THEN 1 ELSE 0 END) AS excluded_item_count,
        SUM(CASE WHEN historical_product_identity_status = 'QUALIFIED'
                      AND mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END)
            AS historical_product_identity_qualified_item_count,
        SUM(CASE WHEN historical_product_identity_status <> 'QUALIFIED'
                      AND mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END)
            AS historical_product_identity_unqualified_item_count,
        SUM(CASE WHEN spu_mapping_status = 'QUALIFIED' AND mapping_readiness_status <> 'EXCLUDED'
            THEN 1 ELSE 0 END) AS spu_mapping_qualified_item_count,
        SUM(CASE WHEN sku_mapping_status = 'QUALIFIED' AND mapping_readiness_status <> 'EXCLUDED'
            THEN 1 ELSE 0 END) AS sku_mapping_qualified_item_count,
        SUM(CASE WHEN order_item_mapping_status = 'QUALIFIED' AND mapping_readiness_status <> 'EXCLUDED'
            THEN 1 ELSE 0 END) AS order_item_mapping_qualified_count,
        SUM(CASE WHEN money_reconciliation_status = 'EXACT' AND mapping_readiness_status <> 'EXCLUDED'
            THEN 1 ELSE 0 END) AS exact_money_item_count,
        SUM(CASE WHEN mapping_readiness_status = 'READY' THEN 1 ELSE 0 END) AS fully_mapped_item_count,
        SUM(CASE WHEN mapping_admission_allowed THEN 1 ELSE 0 END) AS mapping_admitted_item_count,
        SUM(CASE WHEN canonical_import_allowed THEN 1 ELSE 0 END) AS canonical_import_allowed_item_count
    FROM yshopping_dim.dim_canonical_legacy_trade_target_readiness_item
    GROUP BY tenant_id, target_readiness_run_id
)
SELECT
    event.tenant_id,
    event.target_readiness_run_id,
    MAX(event.source_migration_run_id) AS source_migration_run_id,
    COUNT(*) AS source_order_count,
    SUM(CASE WHEN event.mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END) AS active_order_count,
    SUM(CASE WHEN event.mapping_readiness_status = 'EXCLUDED' THEN 1 ELSE 0 END) AS excluded_order_count,
    SUM(CASE WHEN event.buyer_identity_status = 'RESOLVED'
                  AND event.mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END)
        AS buyer_resolved_order_count,
    SUM(CASE WHEN event.buyer_identity_status = 'MISSING'
                  AND event.mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END)
        AS buyer_missing_order_count,
    SUM(CASE WHEN event.buyer_identity_status = 'AMBIGUOUS'
                  AND event.mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END)
        AS buyer_ambiguous_order_count,
    SUM(CASE WHEN event.order_mapping_status = 'QUALIFIED'
                  AND event.mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END)
        AS order_mapping_qualified_count,
    SUM(CASE WHEN event.lifecycle_mapping_status = 'QUALIFIED'
                  AND event.mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END)
        AS lifecycle_mapping_qualified_count,
    SUM(CASE WHEN event.money_reconciliation_status = 'EXACT'
                  AND event.mapping_readiness_status <> 'EXCLUDED' THEN 1 ELSE 0 END)
        AS exact_money_order_count,
    COALESCE(MAX(item.source_item_count), 0) AS source_item_count,
    COALESCE(MAX(item.active_item_count), 0) AS active_item_count,
    COALESCE(MAX(item.excluded_item_count), 0) AS excluded_item_count,
    COALESCE(MAX(item.historical_product_identity_qualified_item_count), 0)
        AS historical_product_identity_qualified_item_count,
    COALESCE(MAX(item.historical_product_identity_unqualified_item_count), 0)
        AS historical_product_identity_unqualified_item_count,
    COALESCE(MAX(item.spu_mapping_qualified_item_count), 0) AS spu_mapping_qualified_item_count,
    COALESCE(MAX(item.sku_mapping_qualified_item_count), 0) AS sku_mapping_qualified_item_count,
    COALESCE(MAX(item.order_item_mapping_qualified_count), 0) AS order_item_mapping_qualified_count,
    COALESCE(MAX(item.exact_money_item_count), 0) AS exact_money_item_count,
    COALESCE(MAX(item.fully_mapped_item_count), 0) AS fully_mapped_item_count,
    SUM(CASE WHEN event.mapping_admission_allowed THEN 1 ELSE 0 END) AS mapping_admitted_order_count,
    SUM(CASE WHEN event.mapping_readiness_status = 'BLOCKED' THEN 1 ELSE 0 END) AS mapping_blocked_order_count,
    COALESCE(MAX(item.mapping_admitted_item_count), 0) AS mapping_admitted_item_count,
    SUM(CASE WHEN event.canonical_import_allowed THEN 1 ELSE 0 END) AS canonical_import_allowed_order_count,
    COALESCE(MAX(item.canonical_import_allowed_item_count), 0) AS canonical_import_allowed_item_count,
    MAX(event.run_target_mapping_evidence_hash) AS target_mapping_evidence_hash,
    MAX(event.assessed_at) AS assessed_at,
    FALSE AS production_migration_enabled,
    'CANONICAL_LEGACY_TRADE_TARGET_READINESS' AS model_semantics
FROM yshopping_dwd.dwd_canonical_legacy_trade_target_readiness_event event
LEFT JOIN item_rollup item
  ON item.tenant_id = event.tenant_id
 AND item.target_readiness_run_id = event.target_readiness_run_id
GROUP BY event.tenant_id, event.target_readiness_run_id;
