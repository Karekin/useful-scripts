CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_risk_commerce_metrics AS
WITH paid_orders AS (
    SELECT orders.tenant_id, orders.order_id, orders.payment_id, payments.recorded_at
    FROM yshopping_dim.dim_canonical_order_current orders
    JOIN yshopping_dim.dim_canonical_payment_current payments
      ON payments.tenant_id = orders.tenant_id
     AND payments.payment_id = orders.payment_id
    WHERE payments.current_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
      AND payments.captured_amount_minor > 0
), denominators AS (
    SELECT tenant_id, COUNT(DISTINCT order_id) AS paid_order_count, MAX(recorded_at) AS data_freshness_at
    FROM paid_orders
    GROUP BY tenant_id
), risk_rollup AS (
    SELECT
        tenant_id,
        COUNT(DISTINCT CASE WHEN flagged_review_count > 0 THEN order_id END) AS flagged_order_count,
        COUNT(DISTINCT CASE WHEN chargeback_dispute_count > 0 THEN order_id END) AS chargeback_order_count,
        COUNT(DISTINCT CASE WHEN adjudicated_risk_case_count > 0
                              OR chargeback_dispute_count > 0
                              OR has_customer_service_defect > 0
                            THEN order_id END) AS defect_order_count,
        SUM(net_loss_amount_minor) AS net_loss_amount_minor,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_dws.dws_canonical_risk_order_current
    GROUP BY tenant_id
), metric_rows AS (
    SELECT d.tenant_id, 'risk.flagged_order_rate' AS metric_id,
           CAST(r.flagged_order_count * 100.0 / NULLIF(d.paid_order_count, 0) AS DECIMAL(38,6)) AS metric_value,
           CAST(r.flagged_order_count AS DECIMAL(38,6)) AS numerator,
           CAST(d.paid_order_count AS DECIMAL(38,6)) AS denominator,
           'percent' AS unit, d.paid_order_count AS source_row_count,
           'Distinct paid orders linked to a governed risk review case' AS evidence_note,
           GREATEST(d.data_freshness_at, r.data_freshness_at) AS data_freshness_at
    FROM denominators d JOIN risk_rollup r ON r.tenant_id = d.tenant_id
    UNION ALL
    SELECT d.tenant_id, 'risk.chargeback_rate',
           CAST(r.chargeback_order_count * 100.0 / NULLIF(d.paid_order_count, 0) AS DECIMAL(38,6)),
           CAST(r.chargeback_order_count AS DECIMAL(38,6)),
           CAST(d.paid_order_count AS DECIMAL(38,6)),
           'percent', d.paid_order_count,
           'Distinct paid orders with an OPEN/WON/LOST chargeback dispute lifecycle',
           GREATEST(d.data_freshness_at, r.data_freshness_at)
    FROM denominators d JOIN risk_rollup r ON r.tenant_id = d.tenant_id
    UNION ALL
    SELECT r.tenant_id, 'risk.loss_amount_yuan',
           CAST(r.net_loss_amount_minor / 100.0 AS DECIMAL(38,6)),
           CAST(r.net_loss_amount_minor AS DECIMAL(38,6)),
           CAST(100 AS DECIMAL(38,6)),
           'yuan', d.paid_order_count,
           'Signed risk loss ledger: confirmed risk, chargeback and service compensation less reversals',
           GREATEST(d.data_freshness_at, r.data_freshness_at)
    FROM risk_rollup r JOIN denominators d ON d.tenant_id = r.tenant_id
    UNION ALL
    SELECT d.tenant_id, 'service.order_defect_rate',
           CAST(r.defect_order_count * 100.0 / NULLIF(d.paid_order_count, 0) AS DECIMAL(38,6)),
           CAST(r.defect_order_count AS DECIMAL(38,6)),
           CAST(d.paid_order_count AS DECIMAL(38,6)),
           'percent', d.paid_order_count,
           'Distinct paid orders with customer-service defect references, adjudicated risk review or payment dispute',
           GREATEST(d.data_freshness_at, r.data_freshness_at)
    FROM denominators d JOIN risk_rollup r ON r.tenant_id = d.tenant_id
)
SELECT tenant_id, metric_id, metric_value, numerator, denominator, unit,
       'LOCAL_TEST_CANONICAL_CURRENT' AS evidence_scope, source_row_count, evidence_note, data_freshness_at
FROM metric_rows
WHERE metric_value IS NOT NULL;
