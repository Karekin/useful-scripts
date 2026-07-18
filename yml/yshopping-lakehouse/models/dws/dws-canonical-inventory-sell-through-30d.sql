CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_inventory_sell_through_30d AS
WITH tenant_window AS (
    SELECT
        tenant_id,
        MAX(occurred_at) AS window_end_at
    FROM yshopping_dwd.dwd_canonical_inventory_movement
    WHERE occurred_at <= CURRENT_TIMESTAMP()
    GROUP BY tenant_id
), bounded_movements AS (
    SELECT
        movement.tenant_id,
        COALESCE(movement.owner_type, 'UNSPECIFIED') AS owner_type,
        COALESCE(movement.owner_id, '<UNSCOPED>') AS owner_id,
        movement.canonical_sku_id,
        movement.warehouse_id,
        movement.base_uom_code,
        movement.event_id,
        movement.movement_type,
        movement.occurred_at,
        movement.recorded_at,
        movement.delta_on_hand_quantity,
        movement.after_available_quantity
    FROM yshopping_dwd.dwd_canonical_inventory_movement movement
    JOIN tenant_window window
      ON window.tenant_id = movement.tenant_id
    WHERE movement.occurred_at <= window.window_end_at
), opening_balance AS (
    SELECT
        ranked.tenant_id,
        ranked.owner_type,
        ranked.owner_id,
        ranked.canonical_sku_id,
        ranked.warehouse_id,
        ranked.base_uom_code,
        ranked.after_available_quantity AS opening_available_quantity
    FROM (
        SELECT
            movement.*,
            ROW_NUMBER() OVER (
                PARTITION BY movement.tenant_id, movement.owner_type, movement.owner_id,
                             movement.canonical_sku_id, movement.warehouse_id, movement.base_uom_code
                ORDER BY movement.occurred_at DESC, movement.recorded_at DESC, movement.event_id DESC
            ) AS version_rank
        FROM bounded_movements movement
        JOIN tenant_window window
          ON window.tenant_id = movement.tenant_id
        WHERE movement.occurred_at < DATE_SUB(window.window_end_at, INTERVAL 30 DAY)
    ) ranked
    WHERE version_rank = 1
), window_movements AS (
    SELECT
        movement.tenant_id,
        movement.owner_type,
        movement.owner_id,
        movement.canonical_sku_id,
        movement.warehouse_id,
        movement.base_uom_code,
        movement.movement_type,
        movement.delta_on_hand_quantity,
        movement.recorded_at
    FROM bounded_movements movement
    JOIN tenant_window window
      ON window.tenant_id = movement.tenant_id
    WHERE movement.occurred_at >= DATE_SUB(window.window_end_at, INTERVAL 30 DAY)
), movement_rollup AS (
    SELECT
        tenant_id,
        owner_type,
        owner_id,
        canonical_sku_id,
        warehouse_id,
        base_uom_code,
        SUM(CASE WHEN movement_type = 'PURCHASE_RECEIPT'
                 THEN delta_on_hand_quantity ELSE 0 END) AS receipt_quantity_30d,
        SUM(CASE WHEN movement_type = 'SALE_SHIPMENT'
                 THEN ABS(delta_on_hand_quantity) ELSE 0 END) AS shipped_quantity_30d,
        SUM(CASE WHEN movement_type = 'SALE_RETURN'
                 THEN delta_on_hand_quantity ELSE 0 END) AS returned_quantity_30d,
        MAX(recorded_at) AS data_freshness_at
    FROM window_movements
    GROUP BY tenant_id, owner_type, owner_id, canonical_sku_id, warehouse_id, base_uom_code
), sell_through_entities AS (
    SELECT
        tenant_id,
        owner_type,
        owner_id,
        canonical_sku_id,
        warehouse_id,
        base_uom_code
    FROM opening_balance
    UNION DISTINCT
    SELECT
        tenant_id,
        owner_type,
        owner_id,
        canonical_sku_id,
        warehouse_id,
        base_uom_code
    FROM movement_rollup
)
SELECT
    entity.tenant_id,
    entity.owner_type,
    entity.owner_id,
    entity.canonical_sku_id,
    entity.warehouse_id,
    entity.base_uom_code,
    DATE_SUB(window.window_end_at, INTERVAL 30 DAY) AS window_start_at,
    window.window_end_at,
    COALESCE(opening.opening_available_quantity, 0) AS opening_available_quantity,
    COALESCE(movement.receipt_quantity_30d, 0) AS receipt_quantity_30d,
    COALESCE(movement.shipped_quantity_30d, 0) AS shipped_quantity_30d,
    COALESCE(movement.returned_quantity_30d, 0) AS returned_quantity_30d,
    CAST(COALESCE(movement.shipped_quantity_30d, 0) - COALESCE(movement.returned_quantity_30d, 0)
         AS DECIMAL(38,6)) AS net_sold_quantity_30d,
    CAST(COALESCE(opening.opening_available_quantity, 0) + COALESCE(movement.receipt_quantity_30d, 0)
         AS DECIMAL(38,6)) AS denominator_quantity_30d,
    CAST(
        (COALESCE(movement.shipped_quantity_30d, 0) - COALESCE(movement.returned_quantity_30d, 0))
        * 100.0
        / NULLIF(COALESCE(opening.opening_available_quantity, 0) + COALESCE(movement.receipt_quantity_30d, 0), 0)
        AS DECIMAL(38,6)
    ) AS sell_through_rate_30d,
    COALESCE(movement.data_freshness_at, window.window_end_at) AS data_freshness_at
FROM sell_through_entities entity
JOIN tenant_window window
  ON window.tenant_id = entity.tenant_id
LEFT JOIN opening_balance opening
  ON opening.tenant_id = entity.tenant_id
 AND opening.owner_type = entity.owner_type
 AND opening.owner_id = entity.owner_id
 AND opening.canonical_sku_id = entity.canonical_sku_id
 AND opening.warehouse_id = entity.warehouse_id
 AND opening.base_uom_code = entity.base_uom_code
LEFT JOIN movement_rollup movement
  ON movement.tenant_id = entity.tenant_id
 AND movement.owner_type = entity.owner_type
 AND movement.owner_id = entity.owner_id
 AND movement.canonical_sku_id = entity.canonical_sku_id
 AND movement.warehouse_id = entity.warehouse_id
 AND movement.base_uom_code = entity.base_uom_code
WHERE COALESCE(opening.opening_available_quantity, 0) + COALESCE(movement.receipt_quantity_30d, 0) > 0
  AND COALESCE(movement.shipped_quantity_30d, 0) >= COALESCE(movement.returned_quantity_30d, 0);
