CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_inventory_movement AS
WITH inventory_event AS (
    SELECT *
    FROM yshopping_dwd.dwd_domain_event
    WHERE event_type = 'inventory.stock.changed'
      AND schema_version IN (1, 2, 3, 4, 5)
      AND source_system = 'cloudmold-inventory'
), reservation_identity AS (
    SELECT tenant_id, reservation_id, business_type, business_id, business_item_id
    FROM (
        SELECT
            tenant_id,
            get_json_string(payload, '$.reservation_id') AS reservation_id,
            CASE get_json_string(payload, '$.business_type')
                WHEN 'ORDER' THEN 'TRADE_ORDER'
                ELSE get_json_string(payload, '$.business_type')
            END AS business_type,
            get_json_string(payload, '$.business_id') AS business_id,
            get_json_string(payload, '$.business_item_id') AS business_item_id,
            ROW_NUMBER() OVER (
                PARTITION BY tenant_id, get_json_string(payload, '$.reservation_id')
                ORDER BY occurred_at, recorded_at, event_id
            ) AS row_num
        FROM inventory_event
        WHERE get_json_string(payload, '$.movement_type') = 'RESERVATION'
          AND get_json_string(payload, '$.reservation_id') IS NOT NULL
          AND get_json_string(payload, '$.business_type') IN ('ORDER', 'TRADE_ORDER')
    ) ranked
    WHERE row_num = 1
)
SELECT
    event.event_id,
    event.schema_version,
    event.tenant_id,
    event.aggregate_id AS balance_id,
    event.aggregate_version,
    event.occurred_at,
    event.recorded_at,
    event.correlation_id,
    event.causation_id,
    event.idempotency_key,
    get_json_string(payload, '$.canonical_sku_id') AS canonical_sku_id,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.location_id') AS location_id,
    CASE WHEN schema_version IN (3, 4, 5) THEN get_json_string(payload, '$.lot_id') END AS lot_id,
    CASE WHEN schema_version IN (3, 4, 5) THEN get_json_string(payload, '$.lot_code') END AS lot_code,
    CASE WHEN schema_version IN (1, 2) THEN get_json_string(payload, '$.lot_no') END AS legacy_lot_no,
    get_json_string(payload, '$.owner_type') AS owner_type,
    get_json_string(payload, '$.owner_id') AS owner_id,
    get_json_string(payload, '$.stock_status') AS stock_status,
    get_json_string(payload, '$.quality_status') AS quality_status,
    COALESCE(
        CAST(get_json_string(payload, '$.delta_on_hand_quantity') AS DECIMAL(24,6)),
        CAST(get_json_string(payload, '$.delta_quantity') AS DECIMAL(24,6))
    ) AS delta_on_hand_quantity,
    CAST(get_json_string(payload, '$.delta_reserved_quantity') AS DECIMAL(24,6)) AS delta_reserved_quantity,
    CAST(get_json_string(payload, '$.delta_in_transit_quantity') AS DECIMAL(24,6)) AS delta_in_transit_quantity,
    CAST(get_json_string(payload, '$.after_on_hand_quantity') AS DECIMAL(24,6)) AS after_on_hand_quantity,
    CAST(get_json_string(payload, '$.after_reserved_quantity') AS DECIMAL(24,6)) AS after_reserved_quantity,
    CAST(get_json_string(payload, '$.after_in_transit_quantity') AS DECIMAL(24,6)) AS after_in_transit_quantity,
    CAST(get_json_string(payload, '$.after_available_quantity') AS DECIMAL(24,6)) AS after_available_quantity,
    COALESCE(get_json_string(payload, '$.base_uom_code'), get_json_string(payload, '$.uom_code')) AS base_uom_code,
    get_json_string(payload, '$.uom_code') AS uom_code,
    get_json_string(payload, '$.movement_type') AS movement_type,
    CAST(get_json_string(payload, '$.ledger_transaction_id') AS BIGINT) AS ledger_transaction_id,
    get_json_string(payload, '$.movement_group_id') AS movement_group_id,
    get_json_string(payload, '$.entry_role') AS entry_role,
    get_json_string(payload, '$.counterparty_balance_id') AS counterparty_balance_id,
    CASE
        WHEN get_json_string(payload, '$.movement_type') = 'SALE_SHIPMENT'
         AND get_json_string(payload, '$.business_type') = 'ORDER_SHIPMENT'
        THEN reservation.business_type
        WHEN get_json_string(payload, '$.business_type') = 'ORDER' THEN 'TRADE_ORDER'
        ELSE get_json_string(payload, '$.business_type')
    END AS business_type,
    CASE
        WHEN get_json_string(payload, '$.movement_type') = 'SALE_SHIPMENT'
         AND get_json_string(payload, '$.business_type') = 'ORDER_SHIPMENT'
        THEN reservation.business_id
        ELSE get_json_string(payload, '$.business_id')
    END AS business_id,
    CASE
        WHEN get_json_string(payload, '$.movement_type') = 'SALE_SHIPMENT'
         AND get_json_string(payload, '$.business_type') = 'ORDER_SHIPMENT'
        THEN reservation.business_item_id
        ELSE get_json_string(payload, '$.business_item_id')
    END AS business_item_id,
    get_json_string(payload, '$.business_no') AS business_no,
    get_json_string(payload, '$.reservation_id') AS reservation_id,
    get_json_string(payload, '$.allocation_id') AS allocation_id,
    CAST(get_json_string(payload, '$.unit_cost_amount_minor') AS BIGINT) AS unit_cost_amount_minor,
    CAST(get_json_string(payload, '$.movement_cost_amount_minor') AS BIGINT) AS movement_cost_amount_minor,
    get_json_string(payload, '$.currency_code') AS currency_code,
    get_json_string(payload, '$.cost_source_system') AS cost_source_system,
    get_json_string(payload, '$.cost_source_ref') AS cost_source_ref,
    get_json_string(payload, '$.cost_policy_version') AS cost_policy_version,
    get_json_string(payload, '$.cancellation_saga_id') AS cancellation_saga_id,
    CAST(get_json_string(payload, '$.step_ordinal') AS INT) AS step_ordinal
FROM inventory_event event
LEFT JOIN reservation_identity reservation
  ON reservation.tenant_id = event.tenant_id
 AND reservation.reservation_id = get_json_string(event.payload, '$.reservation_id');
