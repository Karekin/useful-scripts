CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_merchant_source_mapping_event AS
SELECT
    event_id, tenant_id, aggregate_id AS mapping_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.migration_run_id') AS migration_run_id,
    get_json_string(payload, '$.source_system') AS mapping_source_system,
    get_json_string(payload, '$.source_type') AS source_type,
    get_json_string(payload, '$.source_id') AS source_id,
    get_json_string(payload, '$.target_type') AS target_type,
    get_json_string(payload, '$.target_id') AS target_id,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.valid_from'), 1, 19), 'T', ' ') AS DATETIME) AS valid_from,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.valid_to'), 1, 19), 'T', ' ') AS DATETIME) AS valid_to,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.verification_ref') AS verification_ref
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'merchant.source_mapping.changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-merchant'
  AND aggregate_type = 'MERCHANT_SOURCE_MAPPING';
