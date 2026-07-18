CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_inventory_cost_layer_current AS
WITH balance_coverage AS (
    SELECT
        tenant_id,
        balance_id,
        COUNT(CASE WHEN delta_on_hand_quantity <> 0 THEN 1 END) AS on_hand_movement_count,
        COUNT(CASE WHEN delta_on_hand_quantity <> 0 AND schema_version = 5
                    AND unit_cost_amount_minor IS NOT NULL
                    AND movement_cost_amount_minor IS NOT NULL THEN 1 END) AS costed_on_hand_movement_count,
        COUNT(DISTINCT CASE WHEN schema_version = 5 THEN currency_code END) AS currency_count,
        MAX(CASE WHEN schema_version = 5 THEN currency_code END) AS currency_code
    FROM yshopping_dwd.dwd_canonical_inventory_movement
    GROUP BY tenant_id, balance_id
),
inbound AS (
    SELECT
        movement.*,
        COALESCE(SUM(delta_on_hand_quantity) OVER (
            PARTITION BY tenant_id, balance_id
            ORDER BY occurred_at DESC, aggregate_version DESC, event_id DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ), 0) AS newer_inbound_quantity
    FROM yshopping_dwd.dwd_canonical_inventory_movement movement
    WHERE schema_version = 5
      AND delta_on_hand_quantity > 0
      AND movement_type IN ('PURCHASE_RECEIPT', 'SALE_RETURN')
),
layers AS (
    SELECT
        inbound.*,
        balance.on_hand_quantity,
        GREATEST(
            LEAST(inbound.delta_on_hand_quantity,
                  balance.on_hand_quantity - inbound.newer_inbound_quantity),
            CAST(0 AS DECIMAL(24,6))
        ) AS remaining_quantity
    FROM inbound
    JOIN yshopping_dws.dws_canonical_inventory_balance_current balance
      ON balance.tenant_id = inbound.tenant_id
     AND balance.balance_id = inbound.balance_id
)
SELECT
    layers.tenant_id,
    layers.balance_id,
    layers.event_id AS source_event_id,
    layers.aggregate_version,
    layers.canonical_sku_id,
    layers.warehouse_id,
    layers.location_id,
    layers.lot_id,
    layers.owner_id,
    layers.base_uom_code,
    layers.occurred_at AS received_at,
    layers.delta_on_hand_quantity AS received_quantity,
    layers.remaining_quantity,
    layers.unit_cost_amount_minor,
    CAST(layers.remaining_quantity * layers.unit_cost_amount_minor AS DECIMAL(38,6)) AS remaining_cost_amount_minor,
    layers.currency_code,
    layers.cost_source_system,
    layers.cost_source_ref,
    layers.cost_policy_version,
    coverage.on_hand_movement_count,
    coverage.costed_on_hand_movement_count,
    coverage.currency_count,
    coverage.on_hand_movement_count = coverage.costed_on_hand_movement_count
        AND coverage.currency_count = 1 AS is_cost_complete
FROM layers
JOIN balance_coverage coverage
  ON coverage.tenant_id = layers.tenant_id
 AND coverage.balance_id = layers.balance_id
WHERE layers.remaining_quantity > 0;
