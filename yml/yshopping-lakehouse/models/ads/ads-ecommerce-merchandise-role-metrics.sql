-- Lightweight governed KPI surface for Product & Supply Chain.
-- Cost and aging publish only when every on-hand movement of a valued balance
-- carries complete FIFO cost evidence. Procurement OTIF uses only active,
-- versioned purchase promises and approved receipt facts.
CREATE OR REPLACE VIEW yshopping_ads.ads_ecommerce_merchandise_role_metrics AS
WITH inventory_ready AS (
    SELECT
        tenant_id,
        SUM(inventory_value_amount_minor) AS inventory_value_amount_minor,
        SUM(aged_stock_value_amount_minor) AS aged_stock_value_amount_minor,
        SUM(cost_of_goods_sold_amount_minor) AS cost_of_goods_sold_amount_minor,
        SUM(valued_balance_count) AS valued_balance_count,
        SUM(costed_shipment_count) AS costed_shipment_count,
        MAX(calculated_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_inventory_cost_aging_metrics
    WHERE readiness_status = 'READY_COSTED_FIFO_V1'
    GROUP BY tenant_id
), procurement_ready AS (
    SELECT
        tenant_id,
        SUM(on_time_in_full_purchase_order_count) AS on_time_in_full_purchase_order_count,
        SUM(due_purchase_order_count) AS due_purchase_order_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_procurement_otif_metrics
    GROUP BY tenant_id
), metric_rows AS (
    SELECT
        tenant_id,
        'inventory.turnover_days' AS metric_id,
        CAST(inventory_value_amount_minor * 90.0 / NULLIF(cost_of_goods_sold_amount_minor, 0)
             AS DECIMAL(38,6)) AS metric_value,
        CAST(inventory_value_amount_minor AS DECIMAL(38,6)) AS numerator,
        CAST(cost_of_goods_sold_amount_minor AS DECIMAL(38,6)) AS denominator,
        'days' AS unit,
        valued_balance_count AS source_row_count,
        'FIFO-valued inventory divided by trailing 90-day cost of goods sold, multiplied by 90' AS evidence_note,
        data_freshness_at
    FROM inventory_ready
    UNION ALL
    SELECT
        tenant_id,
        'inventory.aged_stock_value_yuan',
        CAST(aged_stock_value_amount_minor / 100.0 AS DECIMAL(38,6)),
        CAST(aged_stock_value_amount_minor / 100.0 AS DECIMAL(38,6)),
        CAST(NULL AS DECIMAL(38,6)),
        'yuan',
        valued_balance_count,
        'FIFO remaining inventory cost received more than 90 days ago',
        data_freshness_at
    FROM inventory_ready
    UNION ALL
    SELECT
        tenant_id,
        'procurement.otif_rate',
        CAST(on_time_in_full_purchase_order_count * 100.0 / NULLIF(due_purchase_order_count, 0)
             AS DECIMAL(38,6)),
        CAST(on_time_in_full_purchase_order_count AS DECIMAL(38,6)),
        CAST(due_purchase_order_count AS DECIMAL(38,6)),
        'percent',
        due_purchase_order_count,
        'Purchase orders received on time and in full against an active versioned promise',
        data_freshness_at
    FROM procurement_ready
), complete_tenants AS (
    SELECT tenant_id
    FROM metric_rows
    WHERE metric_value IS NOT NULL
    GROUP BY tenant_id
    HAVING COUNT(*) = 3 AND COUNT(DISTINCT metric_id) = 3
)
SELECT
    metric.tenant_id,
    metric.metric_id,
    metric.metric_value,
    metric.numerator,
    metric.denominator,
    metric.unit,
    'LOCAL_TEST_CANONICAL_CURRENT' AS evidence_scope,
    metric.source_row_count,
    metric.evidence_note,
    metric.data_freshness_at
FROM metric_rows metric
JOIN complete_tenants complete ON complete.tenant_id = metric.tenant_id
WHERE metric.metric_value IS NOT NULL;
