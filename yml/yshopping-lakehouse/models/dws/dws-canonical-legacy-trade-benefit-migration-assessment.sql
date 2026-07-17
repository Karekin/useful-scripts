CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment AS
WITH component_rollup AS (
    SELECT
        tenant_id,
        migration_run_id,
        COUNT(*) AS component_count,
        SUM(component_amount_minor) AS component_amount_minor,
        SUM(CASE WHEN identity_resolution_status <> 'RESOLVED' THEN 1 ELSE 0 END) AS unresolved_identity_count,
        SUM(CASE WHEN funding_resolution_status <> 'RESOLVED' THEN 1 ELSE 0 END) AS unresolved_funding_count,
        SUM(CASE WHEN canonical_import_allowed THEN 1 ELSE 0 END) AS import_allowed_component_count
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_component_assessment
    GROUP BY tenant_id, migration_run_id
), item_rollup AS (
    SELECT
        tenant_id,
        migration_run_id,
        COUNT(*) AS source_item_count,
        SUM(CASE WHEN is_deleted = FALSE AND order_assessment_status <> 'DELETED_EXCLUDED'
            THEN 1 ELSE 0 END) AS active_item_count,
        SUM(CASE WHEN is_deleted = TRUE OR order_assessment_status = 'DELETED_EXCLUDED'
            THEN 1 ELSE 0 END) AS excluded_item_count,
        SUM(CASE WHEN is_deleted = FALSE AND order_assessment_status <> 'DELETED_EXCLUDED'
            THEN generic_discount_amount_minor + coupon_amount_minor + point_amount_minor + vip_amount_minor
            ELSE 0 END) AS item_benefit_amount_minor,
        SUM(CASE WHEN canonical_import_allowed THEN 1 ELSE 0 END) AS import_allowed_item_count
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_item_assessment
    GROUP BY tenant_id, migration_run_id
)
SELECT
    event.tenant_id,
    event.migration_run_id,
    MAX(event.source_scope) AS source_scope,
    COUNT(*) AS source_order_row_count,
    SUM(CASE WHEN event.is_deleted = FALSE THEN 1 ELSE 0 END) AS non_deleted_order_count,
    SUM(CASE WHEN event.assessment_status = 'DELETED_EXCLUDED' THEN 1 ELSE 0 END) AS deleted_excluded_count,
    SUM(CASE WHEN event.assessment_status = 'NO_BENEFIT' THEN 1 ELSE 0 END) AS no_benefit_order_count,
    SUM(CASE WHEN event.assessment_status = 'BENEFIT_REQUIRES_IDENTITY_AND_FUNDING' THEN 1 ELSE 0 END)
        AS benefit_evidence_pending_order_count,
    SUM(CASE WHEN event.assessment_status LIKE 'QUARANTINED_%' THEN 1 ELSE 0 END) AS quarantined_order_count,
    SUM(CASE WHEN event.is_deleted = FALSE THEN event.header_benefit_amount_minor ELSE 0 END)
        AS source_benefit_amount_minor,
    COALESCE(MAX(component.component_count), 0) AS component_count,
    COALESCE(MAX(component.component_amount_minor), 0) AS component_amount_minor,
    COALESCE(MAX(component.unresolved_identity_count), 0) AS unresolved_identity_count,
    COALESCE(MAX(component.unresolved_funding_count), 0) AS unresolved_funding_count,
    COALESCE(MAX(component.import_allowed_component_count), 0) AS import_allowed_component_count,
    COALESCE(MAX(item.source_item_count), 0) AS source_item_count,
    COALESCE(MAX(item.active_item_count), 0) AS active_item_count,
    COALESCE(MAX(item.excluded_item_count), 0) AS excluded_item_count,
    COALESCE(MAX(item.item_benefit_amount_minor), 0) AS item_benefit_amount_minor,
    COALESCE(MAX(item.import_allowed_item_count), 0) AS import_allowed_item_count,
    MIN(CASE WHEN event.schema_version = 2 AND event.item_evidence_complete THEN 1 ELSE 0 END) = 1
        AS item_evidence_complete,
    MAX(event.run_source_item_count) AS declared_source_item_count,
    MAX(event.run_active_item_count) AS declared_active_item_count,
    MAX(event.run_excluded_item_count) AS declared_excluded_item_count,
    MAX(event.run_item_evidence_hash) AS item_evidence_hash,
    MAX(event.run_item_evidence_benefit_amount_minor) AS declared_item_benefit_amount_minor,
    MAX(event.assessed_at) AS assessed_at,
    FALSE AS production_migration_enabled,
    'CANONICAL_LEGACY_TRADE_BENEFIT_MIGRATION_ASSESSMENT' AS model_semantics
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_assessment_event event
LEFT JOIN component_rollup component
  ON component.tenant_id = event.tenant_id
 AND component.migration_run_id = event.migration_run_id
LEFT JOIN item_rollup item
  ON item.tenant_id = event.tenant_id
 AND item.migration_run_id = event.migration_run_id
GROUP BY event.tenant_id, event.migration_run_id;
