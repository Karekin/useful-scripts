CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_procurement_otif_metrics AS
WITH due_lines AS (
    SELECT
        tenant_id,
        purchase_order_id,
        purchase_order_no,
        supplier_id,
        DATE_FORMAT(effective_deadline_at, '%Y-%m-%d') AS metric_date,
        on_time_in_full,
        data_freshness_at
    FROM yshopping_dws.dws_canonical_procurement_otif_current
    WHERE promise_status = 'ACTIVE'
      AND comparable_otif = TRUE
), order_rollup AS (
    SELECT
        tenant_id,
        metric_date,
        supplier_id,
        purchase_order_id,
        MAX(purchase_order_no) AS purchase_order_no,
        COUNT(*) AS due_promise_line_count,
        COUNT(IF(on_time_in_full = TRUE, 1, NULL)) AS on_time_in_full_promise_line_count,
        CASE
            WHEN COUNT(*) = COUNT(IF(on_time_in_full = TRUE, 1, NULL))
            THEN TRUE ELSE FALSE
        END AS order_on_time_in_full,
        MAX(data_freshness_at) AS data_freshness_at
    FROM due_lines
    GROUP BY tenant_id, metric_date, supplier_id, purchase_order_id
)
SELECT
    tenant_id,
    metric_date,
    supplier_id,
    COUNT(*) AS due_purchase_order_count,
    COUNT(IF(order_on_time_in_full = TRUE, 1, NULL)) AS on_time_in_full_purchase_order_count,
    SUM(due_promise_line_count) AS due_promise_line_count,
    SUM(on_time_in_full_promise_line_count) AS on_time_in_full_promise_line_count,
    CAST(
        COUNT(IF(order_on_time_in_full = TRUE, 1, NULL)) * 100.0
        / NULLIF(COUNT(*), 0)
        AS DECIMAL(18,6)
    ) AS procurement_otif_rate,
    CAST(
        SUM(on_time_in_full_promise_line_count) * 100.0
        / NULLIF(SUM(due_promise_line_count), 0)
        AS DECIMAL(18,6)
    ) AS procurement_otif_line_rate,
    MAX(data_freshness_at) AS data_freshness_at
FROM order_rollup
GROUP BY tenant_id, metric_date, supplier_id;
