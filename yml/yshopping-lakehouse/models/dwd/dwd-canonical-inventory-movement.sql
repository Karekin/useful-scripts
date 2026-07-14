CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_inventory_movement AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    aggregate_id AS balance_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.canonical_sku_id') AS canonical_sku_id,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.owner_id') AS owner_id,
    get_json_string(payload, '$.quality_status') AS quality_status,
    CAST(get_json_string(payload, '$.delta_quantity') AS DECIMAL(24,6)) AS delta_on_hand_quantity,
    CAST(get_json_string(payload, '$.after_on_hand_quantity') AS DECIMAL(24,6)) AS after_on_hand_quantity,
    CAST(get_json_string(payload, '$.after_reserved_quantity') AS DECIMAL(24,6)) AS after_reserved_quantity,
    CAST(get_json_string(payload, '$.after_available_quantity') AS DECIMAL(24,6)) AS after_available_quantity,
    get_json_string(payload, '$.uom_code') AS uom_code,
    get_json_string(payload, '$.movement_type') AS movement_type,
    get_json_string(payload, '$.business_type') AS business_type,
    get_json_string(payload, '$.business_id') AS business_id,
    get_json_string(payload, '$.business_item_id') AS business_item_id,
    get_json_string(payload, '$.business_no') AS business_no,
    get_json_string(payload, '$.reservation_id') AS reservation_id,
    get_json_string(payload, '$.cancellation_saga_id') AS cancellation_saga_id,
    CAST(get_json_string(payload, '$.step_ordinal') AS INT) AS step_ordinal
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'inventory.stock.changed'
  AND schema_version IN (1, 2)
  AND source_system = 'cloudmold-inventory';
