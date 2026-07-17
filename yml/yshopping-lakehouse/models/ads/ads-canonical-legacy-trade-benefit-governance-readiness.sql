CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_legacy_trade_benefit_governance_readiness AS
WITH target_mapping AS (
    SELECT
        tenant_id,
        source_migration_run_id,
        MAX(CASE WHEN exact_target_mapping_available THEN 1 ELSE 0 END) = 1 AS exact_target_mapping_available
    FROM yshopping_ads.ads_canonical_legacy_trade_target_readiness
    GROUP BY tenant_id, source_migration_run_id
)
SELECT
    governance.tenant_id,
    governance.governance_run_id,
    governance.source_migration_run_id,
    governance.candidate_event_count,
    governance.declared_source_component_count,
    governance.component_count,
    governance.source_reference_present_count,
    governance.current_reference_observed_count,
    governance.historical_identity_qualified_count,
    governance.identity_blocked_count,
    governance.funding_qualified_count,
    governance.funding_blocked_count,
    governance.governance_admitted_component_count,
    governance.declared_source_quarantine_count,
    governance.quarantine_count,
    governance.quarantine_decided_count,
    governance.quarantine_open_count,
    governance.canonical_import_allowed_component_count,
    governance.canonical_import_allowed_quarantine_count,
    governance.governance_evidence_hash,
    governance.backend_run_status,
    COALESCE(target.exact_target_mapping_available, FALSE) AS exact_target_mapping_available,
    source.migration_run_id IS NOT NULL AS immutable_source_assessment_available,
    governance.component_count = governance.declared_source_component_count
      AND governance.quarantine_count = governance.declared_source_quarantine_count
      AND source.component_count = governance.declared_source_component_count
      AND source.quarantined_order_count = governance.declared_source_quarantine_count
      AS exact_governance_denominator_available,
    governance.historical_identity_qualified_count = governance.declared_source_component_count
      AND governance.funding_qualified_count = governance.declared_source_component_count
      AND governance.governance_admitted_component_count = governance.declared_source_component_count
      AND governance.quarantine_decided_count = governance.declared_source_quarantine_count
      AND governance.quarantine_open_count = 0 AS benefit_governance_ready,
    CASE
      WHEN source.migration_run_id IS NULL THEN 'BLOCKED_SOURCE_ASSESSMENT_MISSING'
      WHEN governance.component_count <> governance.declared_source_component_count
        OR governance.quarantine_count <> governance.declared_source_quarantine_count
        OR source.component_count <> governance.declared_source_component_count
        OR source.quarantined_order_count <> governance.declared_source_quarantine_count
        THEN 'BLOCKED_GOVERNANCE_DENOMINATOR_MISMATCH'
      WHEN governance.canonical_import_allowed_component_count <> 0
        OR governance.canonical_import_allowed_quarantine_count <> 0
        OR governance.production_migration_enabled
        THEN 'BLOCKED_ILLEGAL_IMPORT_AUTHORITY'
      WHEN governance.historical_identity_qualified_count <> governance.declared_source_component_count
        OR governance.funding_qualified_count <> governance.declared_source_component_count
        OR governance.governance_admitted_component_count <> governance.declared_source_component_count
        OR governance.quarantine_decided_count <> governance.declared_source_quarantine_count
        OR governance.quarantine_open_count <> 0
        THEN 'BLOCKED_REQUIRES_HISTORICAL_BENEFIT_FUNDING_AND_QUARANTINE_DECISIONS'
      WHEN NOT COALESCE(target.exact_target_mapping_available, FALSE)
        THEN 'BLOCKED_REQUIRES_EXPLICIT_TARGET_MAPPINGS'
      ELSE 'READY_FOR_SEPARATE_COMBINED_ADMISSION_DECISION'
    END AS readiness_status,
    FALSE AS canonical_import_available,
    FALSE AS production_migration_enabled,
    'LOCAL_YUDAO_TRADE_NOT_YSHOPPING_SOURCE' AS governed_scope,
    'CANONICAL_LEGACY_TRADE_BENEFIT_GOVERNANCE_ADMISSION' AS model_semantics
FROM yshopping_dws.dws_canonical_legacy_trade_benefit_governance governance
LEFT JOIN yshopping_dws.dws_canonical_legacy_trade_benefit_migration_assessment source
  ON source.tenant_id = governance.tenant_id
 AND source.migration_run_id = governance.source_migration_run_id
LEFT JOIN target_mapping target
  ON target.tenant_id = governance.tenant_id
 AND target.source_migration_run_id = governance.source_migration_run_id;
