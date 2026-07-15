CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_inventory_lot_lifecycle_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS lot_id,
    aggregate_version AS lot_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.migration_run_id') AS migration_run_id,
    get_json_string(payload, '$.lot_id') AS payload_lot_id,
    get_json_string(payload, '$.owner_type') AS owner_type,
    get_json_string(payload, '$.owner_id') AS owner_id,
    get_json_string(payload, '$.canonical_sku_id') AS canonical_sku_id,
    get_json_string(payload, '$.lot_code') AS lot_code,
    COALESCE(
      CAST(get_json_string(payload, '$.manufactured_on') AS DATE),
      CAST(STR_TO_DATE(CONCAT(
        get_json_string(payload, '$.manufactured_on[0]'), '-',
        get_json_string(payload, '$.manufactured_on[1]'), '-',
        get_json_string(payload, '$.manufactured_on[2]')), '%Y-%m-%d') AS DATE)
    ) AS manufactured_on,
    COALESCE(
      CAST(get_json_string(payload, '$.expires_on') AS DATE),
      CAST(STR_TO_DATE(CONCAT(
        get_json_string(payload, '$.expires_on[0]'), '-',
        get_json_string(payload, '$.expires_on[1]'), '-',
        get_json_string(payload, '$.expires_on[2]')), '%Y-%m-%d') AS DATE)
    ) AS expires_on,
    COALESCE(
      CAST(REPLACE(SUBSTR(get_json_string(payload, '$.received_at'), 1, 19), 'T', ' ') AS DATETIME),
      CAST(FROM_UNIXTIME(CAST(CAST(get_json_string(payload, '$.received_at') AS BIGINT) / 1000 AS BIGINT)) AS DATETIME)
    ) AS received_at,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.change_type') AS change_type,
    get_json_string(payload, '$.reason_code') AS reason_code,
    get_json_string(payload, '$.evidence_ref') AS evidence_ref,
    get_json_string(payload, '$.recall_reference') AS recall_reference
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'inventory.lot.lifecycle.changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-inventory'
  AND aggregate_type = 'inventory_lot';
