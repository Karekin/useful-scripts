CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_identity_source_link_event AS
SELECT
    event_id, tenant_id, aggregate_id AS principal_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.principal_type') AS principal_type,
    get_json_string(payload, '$.principal_status') AS principal_status,
    get_json_string(payload, '$.source_identity_id') AS source_identity_id,
    get_json_string(payload, '$.source_system') AS identity_source_system,
    get_json_string(payload, '$.source_type') AS source_type,
    get_json_string(payload, '$.source_id') AS source_id,
    get_json_string(payload, '$.source_status') AS source_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'identity.source.linked'
  AND schema_version = 1
  AND source_system = 'cloudmold-identity';
