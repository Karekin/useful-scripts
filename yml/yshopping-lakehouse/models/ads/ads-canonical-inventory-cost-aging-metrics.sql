CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_inventory_cost_aging_metrics AS
WITH valuation AS (
    SELECT
        tenant_id,
        currency_code,
        SUM(remaining_cost_amount_minor) AS inventory_value_amount_minor,
        SUM(CASE WHEN received_at < DATE_SUB(NOW(), INTERVAL 90 DAY)
                 THEN remaining_cost_amount_minor ELSE 0 END) AS aged_stock_value_amount_minor,
        COUNT(DISTINCT balance_id) AS valued_balance_count,
        COUNT(DISTINCT CASE WHEN is_cost_complete THEN balance_id END) AS cost_complete_balance_count,
        MIN(CASE WHEN is_cost_complete THEN 1 ELSE 0 END) AS all_valued_balances_cost_complete
    FROM yshopping_dws.dws_canonical_inventory_cost_layer_current
    GROUP BY tenant_id, currency_code
),
cogs_90d AS (
    SELECT
        tenant_id,
        currency_code,
        SUM(movement_cost_amount_minor) AS cost_of_goods_sold_amount_minor,
        COUNT(*) AS costed_shipment_count
    FROM yshopping_dwd.dwd_canonical_inventory_movement
    WHERE schema_version = 5
      AND movement_type = 'SALE_SHIPMENT'
      AND occurred_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)
    GROUP BY tenant_id, currency_code
)
SELECT
    valuation.tenant_id,
    valuation.currency_code,
    valuation.inventory_value_amount_minor,
    valuation.aged_stock_value_amount_minor,
    cogs_90d.cost_of_goods_sold_amount_minor,
    CASE WHEN cogs_90d.cost_of_goods_sold_amount_minor > 0
         THEN CAST(valuation.inventory_value_amount_minor * 90.0
                   / cogs_90d.cost_of_goods_sold_amount_minor AS DECIMAL(18,4))
    END AS inventory_turnover_days,
    valuation.valued_balance_count,
    valuation.cost_complete_balance_count,
    COALESCE(cogs_90d.costed_shipment_count, 0) AS costed_shipment_count,
    CASE
        WHEN valuation.all_valued_balances_cost_complete <> 1 THEN 'BLOCKED_INCOMPLETE_COST_COVERAGE'
        WHEN COALESCE(cogs_90d.cost_of_goods_sold_amount_minor, 0) = 0 THEN 'BLOCKED_NO_TRAILING_90D_COGS'
        ELSE 'READY_COSTED_FIFO_V1'
    END AS readiness_status,
    NOW() AS calculated_at
FROM valuation
LEFT JOIN cogs_90d
  ON cogs_90d.tenant_id = valuation.tenant_id
 AND cogs_90d.currency_code = valuation.currency_code;
