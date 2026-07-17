CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_legacy_trade_target_readiness_event AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    aggregate_id AS order_readiness_id,
    aggregate_version AS readiness_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.target_readiness_run_id') AS target_readiness_run_id,
    get_json_string(payload, '$.source_migration_run_id') AS source_migration_run_id,
    get_json_string(payload, '$.order_readiness_id') AS payload_order_readiness_id,
    get_json_string(payload, '$.candidate_id') AS candidate_id,
    CAST(get_json_string(payload, '$.legacy_order_id') AS BIGINT) AS legacy_order_id,
    get_json_string(payload, '$.buyer_identity_status') AS buyer_identity_status,
    get_json_string(payload, '$.buyer_principal_id') AS buyer_principal_id,
    get_json_string(payload, '$.order_mapping_plan_id') AS order_mapping_plan_id,
    get_json_string(payload, '$.planned_order_id') AS planned_order_id,
    get_json_string(payload, '$.order_mapping_status') AS order_mapping_status,
    get_json_string(payload, '$.canonical_order_status') AS canonical_order_status,
    get_json_string(payload, '$.lifecycle_mapping_status') AS lifecycle_mapping_status,
    get_json_string(payload, '$.money_reconciliation_status') AS money_reconciliation_status,
    CAST(get_json_string(payload, '$.active_item_count') AS BIGINT) AS active_item_count,
    CAST(get_json_string(payload, '$.fully_mapped_item_count') AS BIGINT) AS fully_mapped_item_count,
    get_json_string(payload, '$.mapping_readiness_status') AS mapping_readiness_status,
    json_query(payload, '$.blocker_codes') AS blocker_codes,
    CAST(get_json_string(payload, '$.mapping_admission_allowed') AS BOOLEAN) AS mapping_admission_allowed,
    CAST(get_json_string(payload, '$.canonical_import_allowed') AS BOOLEAN) AS canonical_import_allowed,
    get_json_string(payload, '$.evidence_hash') AS evidence_hash,
    json_query(payload, '$.items') AS items,
    get_json_string(payload, '$.run_target_mapping_evidence_hash') AS run_target_mapping_evidence_hash,
    get_json_string(payload, '$.policy_version') AS policy_version,
    get_json_string(payload, '$.verification_ref') AS verification_ref,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.assessed_at'), 1, 19), 'T', ' ') AS DATETIME) AS assessed_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'order.migration.legacy_trade_target_readiness_assessed'
  AND schema_version IN (1, 2)
  AND source_system = 'cloudmold-order'
  AND aggregate_type = 'legacy_trade_target_readiness';
