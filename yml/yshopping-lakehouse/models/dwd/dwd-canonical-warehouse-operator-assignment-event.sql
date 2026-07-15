CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_warehouse_operator_assignment_event AS
SELECT
    event_id, tenant_id, aggregate_id AS assignment_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.zone_id') AS zone_id,
    get_json_string(payload, '$.location_id') AS location_id,
    get_json_string(payload, '$.principal_id') AS principal_id,
    get_json_string(payload, '$.role_code') AS role_code,
    get_json_string(payload, '$.current_status') AS current_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'warehouse.operator_assignment.changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-warehouse';
