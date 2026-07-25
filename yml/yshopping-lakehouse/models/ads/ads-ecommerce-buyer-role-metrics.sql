-- Lightweight governed KPI surface for the Buyer Journey dashboard.
-- First-order duration uses only versioned principal stitching plus strict
-- Session-to-Payment attribution. Delivery promise performance uses the
-- promise snapshot frozen by Fulfillment at CREATE time and never substitutes
-- the actual delivery timestamp for a missing promise.
CREATE OR REPLACE VIEW yshopping_ads.ads_ecommerce_buyer_role_metrics AS
WITH buyer_first_paid AS (
    SELECT
        tenant_id,
        current_principal_id AS principal_id,
        MIN(started_at) AS first_visit_at,
        MIN(first_paid_at) AS first_paid_at
    FROM yshopping_dws.dws_canonical_commerce_session_funnel
    WHERE current_principal_id IS NOT NULL
      AND paid_session_flag = 1
    GROUP BY tenant_id, current_principal_id
), buyer_first_paid_ranked AS (
    SELECT
        tenant_id,
        principal_id,
        TIMESTAMPDIFF(SECOND, first_visit_at, first_paid_at) / 3600.0 AS first_order_hours,
        first_paid_at,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id
            ORDER BY TIMESTAMPDIFF(SECOND, first_visit_at, first_paid_at), principal_id
        ) AS order_rank,
        COUNT(*) OVER (PARTITION BY tenant_id) AS buyer_count
    FROM buyer_first_paid
    WHERE first_visit_at IS NOT NULL
      AND first_paid_at IS NOT NULL
      AND first_paid_at >= first_visit_at
), buyer_first_paid_p50 AS (
    SELECT
        tenant_id,
        CAST(AVG(first_order_hours) AS DECIMAL(38,6)) AS first_order_hours_p50,
        MAX(buyer_count) AS buyer_count,
        MAX(first_paid_at) AS data_freshness_at
    FROM buyer_first_paid_ranked
    WHERE order_rank IN (
        FLOOR((buyer_count + 1) / 2),
        FLOOR((buyer_count + 2) / 2)
    )
    GROUP BY tenant_id
), delivery_promise_rollup AS (
    SELECT
        tenant_id,
        SUM(on_time_delivery_count) AS on_time_delivery_count,
        SUM(delivered_promise_count) AS delivered_promise_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM yshopping_ads.ads_canonical_fulfillment_promise_metrics
    GROUP BY tenant_id
), metric_rows AS (
    SELECT
        tenant_id,
        'buyer.time_to_first_order_hours' AS metric_id,
        first_order_hours_p50 AS metric_value,
        first_order_hours_p50 AS numerator,
        CAST(NULL AS DECIMAL(38,6)) AS denominator,
        'hours' AS unit,
        buyer_count AS source_row_count,
        'Median hours from first linked governed visit to first strictly attributed paid order' AS evidence_note,
        data_freshness_at
    FROM buyer_first_paid_p50
    UNION ALL
    SELECT
        tenant_id,
        'buyer.delivery_promise_hit_rate',
        CAST(on_time_delivery_count * 100.0 / NULLIF(delivered_promise_count, 0) AS DECIMAL(38,6)),
        CAST(on_time_delivery_count AS DECIMAL(38,6)),
        CAST(delivered_promise_count AS DECIMAL(38,6)),
        'percent',
        delivered_promise_count,
        'Delivered before or at the versioned delivery promise frozen by Fulfillment CREATE',
        data_freshness_at
    FROM delivery_promise_rollup
    UNION ALL
    SELECT
        tenant_id,
        'fulfillment.on_time_delivery_rate',
        CAST(on_time_delivery_count * 100.0 / NULLIF(delivered_promise_count, 0) AS DECIMAL(38,6)),
        CAST(on_time_delivery_count AS DECIMAL(38,6)),
        CAST(delivered_promise_count AS DECIMAL(38,6)),
        'percent',
        delivered_promise_count,
        'Delivered before or at the versioned delivery promise frozen by Fulfillment CREATE',
        data_freshness_at
    FROM delivery_promise_rollup
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
