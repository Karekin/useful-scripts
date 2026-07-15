CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_merchant_operator_assignment_event AS
SELECT
    event_id, tenant_id, aggregate_id AS assignment_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.merchant_id') AS merchant_id,
    get_json_string(payload, '$.shop_id') AS shop_id,
    get_json_string(payload, '$.principal_id') AS principal_id,
    get_json_string(payload, '$.role_code') AS role_code,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    CAST(REPLACE(SUBSTR(get_json_string(payload, '$.valid_from'), 1, 19), 'T', ' ') AS DATETIME) AS valid_from
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'merchant.operator_assignment.changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-merchant';
