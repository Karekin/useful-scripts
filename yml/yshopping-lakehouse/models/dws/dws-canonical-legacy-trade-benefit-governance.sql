CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_legacy_trade_benefit_governance AS
WITH component_rollup AS (
    SELECT
        tenant_id,
        governance_run_id,
        COUNT(*) AS component_count,
        SUM(CASE WHEN source_reference IS NOT NULL THEN 1 ELSE 0 END) AS source_reference_present_count,
        SUM(CASE WHEN current_reference_status = 'CURRENT_REFERENCE_OBSERVED_NOT_HISTORICAL_VERSION'
            THEN 1 ELSE 0 END) AS current_reference_observed_count,
        SUM(CASE WHEN historical_identity_status = 'QUALIFIED' THEN 1 ELSE 0 END)
            AS historical_identity_qualified_count,
        SUM(CASE WHEN historical_identity_status <> 'QUALIFIED' THEN 1 ELSE 0 END)
            AS identity_blocked_count,
        SUM(CASE WHEN funding_resolution_status = 'QUALIFIED' THEN 1 ELSE 0 END)
            AS funding_qualified_count,
        SUM(CASE WHEN funding_resolution_status <> 'QUALIFIED' THEN 1 ELSE 0 END)
            AS funding_blocked_count,
        SUM(CASE WHEN governance_admission_allowed THEN 1 ELSE 0 END) AS governance_admitted_component_count,
        SUM(CASE WHEN canonical_import_allowed THEN 1 ELSE 0 END) AS canonical_import_allowed_component_count
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_governance_component
    GROUP BY tenant_id, governance_run_id
), quarantine_rollup AS (
    SELECT
        tenant_id,
        governance_run_id,
        COUNT(*) AS quarantine_count,
        SUM(CASE WHEN decision_status = 'DECIDED' THEN 1 ELSE 0 END) AS quarantine_decided_count,
        SUM(CASE WHEN decision_status = 'OPEN' THEN 1 ELSE 0 END) AS quarantine_open_count,
        SUM(CASE WHEN canonical_import_allowed THEN 1 ELSE 0 END) AS canonical_import_allowed_quarantine_count
    FROM yshopping_dim.dim_canonical_legacy_trade_benefit_governance_quarantine
    GROUP BY tenant_id, governance_run_id
)
SELECT
    event.tenant_id,
    event.governance_run_id,
    MAX(event.source_migration_run_id) AS source_migration_run_id,
    COUNT(*) AS candidate_event_count,
    MAX(event.run_source_component_count) AS declared_source_component_count,
    MAX(event.run_source_reference_present_count) AS declared_source_reference_present_count,
    MAX(event.run_current_reference_observed_count) AS declared_current_reference_observed_count,
    MAX(event.run_historical_identity_qualified_count) AS declared_historical_identity_qualified_count,
    MAX(event.run_identity_blocked_count) AS declared_identity_blocked_count,
    MAX(event.run_funding_qualified_count) AS declared_funding_qualified_count,
    MAX(event.run_funding_blocked_count) AS declared_funding_blocked_count,
    MAX(event.run_source_quarantine_count) AS declared_source_quarantine_count,
    MAX(event.run_quarantine_decided_count) AS declared_quarantine_decided_count,
    MAX(event.run_quarantine_open_count) AS declared_quarantine_open_count,
    MAX(event.run_governance_admitted_component_count) AS declared_governance_admitted_component_count,
    COALESCE(MAX(component.component_count), 0) AS component_count,
    COALESCE(MAX(component.source_reference_present_count), 0) AS source_reference_present_count,
    COALESCE(MAX(component.current_reference_observed_count), 0) AS current_reference_observed_count,
    COALESCE(MAX(component.historical_identity_qualified_count), 0) AS historical_identity_qualified_count,
    COALESCE(MAX(component.identity_blocked_count), 0) AS identity_blocked_count,
    COALESCE(MAX(component.funding_qualified_count), 0) AS funding_qualified_count,
    COALESCE(MAX(component.funding_blocked_count), 0) AS funding_blocked_count,
    COALESCE(MAX(component.governance_admitted_component_count), 0) AS governance_admitted_component_count,
    COALESCE(MAX(component.canonical_import_allowed_component_count), 0)
        AS canonical_import_allowed_component_count,
    COALESCE(MAX(quarantine.quarantine_count), 0) AS quarantine_count,
    COALESCE(MAX(quarantine.quarantine_decided_count), 0) AS quarantine_decided_count,
    COALESCE(MAX(quarantine.quarantine_open_count), 0) AS quarantine_open_count,
    COALESCE(MAX(quarantine.canonical_import_allowed_quarantine_count), 0)
        AS canonical_import_allowed_quarantine_count,
    MAX(event.governance_evidence_hash) AS governance_evidence_hash,
    MAX(event.run_status) AS backend_run_status,
    MAX(event.policy_version) AS policy_version,
    MAX(event.verification_ref) AS verification_ref,
    MAX(event.assessed_at) AS assessed_at,
    MAX(CASE WHEN event.production_migration_enabled THEN 1 ELSE 0 END) = 1 AS production_migration_enabled,
    'CANONICAL_LEGACY_TRADE_BENEFIT_GOVERNANCE' AS model_semantics
FROM yshopping_dwd.dwd_canonical_legacy_trade_benefit_governance_event event
LEFT JOIN component_rollup component
  ON component.tenant_id = event.tenant_id
 AND component.governance_run_id = event.governance_run_id
LEFT JOIN quarantine_rollup quarantine
  ON quarantine.tenant_id = event.tenant_id
 AND quarantine.governance_run_id = event.governance_run_id
GROUP BY event.tenant_id, event.governance_run_id;
