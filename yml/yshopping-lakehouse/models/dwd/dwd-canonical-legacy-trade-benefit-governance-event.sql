CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_legacy_trade_benefit_governance_event AS
SELECT
    event_id,
    tenant_id,
    schema_version,
    aggregate_id AS governance_evaluation_id,
    get_json_string(payload, '$.candidate_id') AS candidate_id,
    aggregate_version AS governance_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.governance_run_id') AS governance_run_id,
    get_json_string(payload, '$.source_migration_run_id') AS source_migration_run_id,
    get_json_string(payload, '$.candidate_id') AS payload_candidate_id,
    CAST(get_json_string(payload, '$.legacy_order_id') AS BIGINT) AS legacy_order_id,
    get_json_string(payload, '$.governance_evidence_hash') AS governance_evidence_hash,
    CAST(get_json_string(payload, '$.run_source_component_count') AS BIGINT) AS run_source_component_count,
    CAST(get_json_string(payload, '$.run_source_reference_present_count') AS BIGINT)
        AS run_source_reference_present_count,
    CAST(get_json_string(payload, '$.run_current_reference_observed_count') AS BIGINT)
        AS run_current_reference_observed_count,
    CAST(get_json_string(payload, '$.run_historical_identity_qualified_count') AS BIGINT)
        AS run_historical_identity_qualified_count,
    CAST(get_json_string(payload, '$.run_identity_blocked_count') AS BIGINT) AS run_identity_blocked_count,
    CAST(get_json_string(payload, '$.run_funding_qualified_count') AS BIGINT) AS run_funding_qualified_count,
    CAST(get_json_string(payload, '$.run_funding_blocked_count') AS BIGINT) AS run_funding_blocked_count,
    CAST(get_json_string(payload, '$.run_source_quarantine_count') AS BIGINT) AS run_source_quarantine_count,
    CAST(get_json_string(payload, '$.run_quarantine_decided_count') AS BIGINT) AS run_quarantine_decided_count,
    CAST(get_json_string(payload, '$.run_quarantine_open_count') AS BIGINT) AS run_quarantine_open_count,
    CAST(get_json_string(payload, '$.run_governance_admitted_component_count') AS BIGINT)
        AS run_governance_admitted_component_count,
    CAST(get_json_string(payload, '$.production_migration_enabled') AS BOOLEAN) AS production_migration_enabled,
    get_json_string(payload, '$.run_status') AS run_status,
    json_query(payload, '$.components') AS components,
    json_query(payload, '$.quarantine') AS quarantine,
    get_json_string(payload, '$.policy_version') AS policy_version,
    get_json_string(payload, '$.verification_ref') AS verification_ref,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.assessed_at'), 1, 19), 'T', ' ') AS DATETIME) AS assessed_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'order.migration.legacy_trade_benefit_governance_assessed'
  AND schema_version IN (1, 2)
  AND source_system = 'cloudmold-order'
  AND aggregate_type = 'legacy_trade_benefit_governance_readiness';
