-- Fail-closed readiness for the local legacy Trade benefit snapshot.
-- This explicitly does not claim coverage of Y-Shopping's 1.97B-row discount source.
CREATE OR REPLACE VIEW yshopping_ads.ads_legacy_trade_benefit_migration_readiness AS
SELECT
    tenant_id,
    source_order_row_count,
    non_deleted_order_count,
    deleted_excluded_count,
    no_benefit_order_count,
    benefit_evidence_pending_order_count,
    quarantined_order_count,
    source_benefit_amount_minor,
    component_count,
    component_amount_minor,
    unresolved_identity_count,
    unresolved_funding_count,
    import_allowed_component_count,
    production_migration_enabled,
    FALSE AS exact_order_item_mapping_available,
    FALSE AS versioned_benefit_identity_available,
    FALSE AS named_funding_breakdown_available,
    CASE
      WHEN benefit_evidence_pending_order_count = 0 AND quarantined_order_count = 0
        THEN 'NOT_REQUIRED'
      WHEN unresolved_identity_count > 0 OR unresolved_funding_count > 0
        OR quarantined_order_count > 0
        THEN 'BLOCKED_REQUIRES_GOVERNED_EVIDENCE'
      ELSE 'ASSESSMENT_ONLY'
    END AS readiness_status,
    'LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE' AS source_scope,
    'LEGACY_TRADE_BENEFIT_MIGRATION_READINESS' AS model_semantics
FROM yshopping_dws.dws_legacy_trade_benefit_migration_assessment;
