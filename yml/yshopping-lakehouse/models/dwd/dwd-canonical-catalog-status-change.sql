CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_catalog_status_change AS
SELECT
    event_id,
    tenant_id,
    get_json_string(payload, '$.entity_type') AS entity_type,
    get_json_string(payload, '$.entity_id') AS entity_id,
    get_json_string(payload, '$.business_code') AS business_code,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.action') AS lifecycle_action,
    get_json_string(payload, '$.reason') AS reason,
    CAST(get_json_string(payload, '$.version') AS BIGINT) AS aggregate_version,
    correlation_id,
    occurred_at,
    recorded_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'catalog.entity.status_changed' AND schema_version = 1;
