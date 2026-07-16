-- Tenant-level admission denominator for legacy Trade benefit history.
-- Canonical migration remains blocked until exact order/item mappings, benefit
-- versions, and named funding rows are supplied by governed evidence.
CREATE OR REPLACE VIEW yshopping_dws.dws_legacy_trade_benefit_migration_assessment AS
WITH component_rollup AS (
    SELECT
        tenant_id,
        legacy_order_id,
        COUNT(*) AS component_count,
        SUM(component_amount_minor) AS component_amount_minor,
        SUM(CASE WHEN identity_resolution_status NOT IN ('RESOLVED') THEN 1 ELSE 0 END)
            AS unresolved_identity_count,
        SUM(CASE WHEN funding_resolution_status <> 'RESOLVED' THEN 1 ELSE 0 END)
            AS unresolved_funding_count,
        SUM(CASE WHEN canonical_import_allowed THEN 1 ELSE 0 END) AS import_allowed_component_count
    FROM yshopping_dim.dim_legacy_trade_benefit_component_assessment
    GROUP BY tenant_id, legacy_order_id
)
SELECT
    orders.tenant_id,
    COUNT(*) AS source_order_row_count,
    SUM(CASE WHEN orders.is_deleted = FALSE THEN 1 ELSE 0 END) AS non_deleted_order_count,
    SUM(CASE WHEN orders.assessment_status = 'DELETED_EXCLUDED' THEN 1 ELSE 0 END) AS deleted_excluded_count,
    SUM(CASE WHEN orders.assessment_status = 'NO_BENEFIT' THEN 1 ELSE 0 END) AS no_benefit_order_count,
    SUM(CASE WHEN orders.assessment_status = 'BENEFIT_REQUIRES_IDENTITY_AND_FUNDING' THEN 1 ELSE 0 END)
        AS benefit_evidence_pending_order_count,
    SUM(CASE WHEN orders.assessment_status LIKE 'QUARANTINED_%' THEN 1 ELSE 0 END)
        AS quarantined_order_count,
    SUM(CASE WHEN orders.is_deleted = FALSE THEN orders.header_benefit_amount_minor ELSE 0 END)
        AS source_benefit_amount_minor,
    COALESCE(SUM(components.component_count), 0) AS component_count,
    COALESCE(SUM(components.component_amount_minor), 0) AS component_amount_minor,
    COALESCE(SUM(components.unresolved_identity_count), 0) AS unresolved_identity_count,
    COALESCE(SUM(components.unresolved_funding_count), 0) AS unresolved_funding_count,
    COALESCE(SUM(components.import_allowed_component_count), 0) AS import_allowed_component_count,
    FALSE AS production_migration_enabled,
    'LEGACY_TRADE_BENEFIT_MIGRATION_ASSESSMENT' AS model_semantics
FROM yshopping_dwd.dwd_legacy_trade_benefit_assessment orders
LEFT JOIN component_rollup components
  ON components.tenant_id = orders.tenant_id
 AND components.legacy_order_id = orders.legacy_order_id
GROUP BY orders.tenant_id;
