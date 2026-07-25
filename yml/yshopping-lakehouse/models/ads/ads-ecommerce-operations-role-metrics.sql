-- Lightweight governed KPI surface for the Platform Operations dashboard.
-- The snapshot is intentionally anchored to the latest loaded paid business day.
-- Anonymous sessions are isolated by session_id; linked sessions are stitched by
-- canonical principal_id, and payment completion requires the explicit session
-- attribution event rather than an inferred Order join.
CREATE OR REPLACE VIEW yshopping_ads.ads_ecommerce_operations_role_metrics AS
WITH behavior_subject_base AS (
    SELECT
        tenant_id,
        session_id,
        COALESCE(NULLIF(current_principal_id, ''), session_id) AS subject_key,
        cart_added_session_flag,
        paid_session_flag,
        last_activity_at
    FROM yshopping_dws.dws_canonical_commerce_session_funnel
), behavior_paid_subject AS (
    SELECT tenant_id, subject_key
    FROM behavior_subject_base
    WHERE paid_session_flag = 1
    GROUP BY tenant_id, subject_key
), behavior_rollup AS (
    SELECT
        base.tenant_id,
        COUNT(*) AS session_count,
        COUNT(DISTINCT base.subject_key) AS visitor_count,
        COUNT(DISTINCT CASE WHEN base.paid_session_flag = 1
            THEN base.subject_key END) AS paid_visitor_count,
        COUNT(DISTINCT CASE WHEN base.cart_added_session_flag = 1
            THEN base.subject_key END) AS cart_subject_count,
        COUNT(DISTINCT CASE WHEN base.cart_added_session_flag = 1
                                  AND paid.subject_key IS NULL
            THEN base.subject_key END) AS unpaid_cart_subject_count,
        MAX(base.last_activity_at) AS data_freshness_at
    FROM behavior_subject_base base
    LEFT JOIN behavior_paid_subject paid
      ON paid.tenant_id = base.tenant_id
     AND paid.subject_key = base.subject_key
    GROUP BY base.tenant_id
), paid_orders AS (
    SELECT
        orders.tenant_id,
        orders.buyer_id,
        orders.order_id,
        payment.recorded_at
    FROM yshopping_dim.dim_canonical_order_current orders
    JOIN yshopping_dim.dim_canonical_payment_current payment
      ON payment.tenant_id = orders.tenant_id
     AND payment.payment_id = orders.payment_id
    WHERE payment.current_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
      AND payment.captured_amount_minor > 0
), buyer_first_paid AS (
    SELECT
        tenant_id,
        buyer_id,
        MIN(recorded_at) AS first_paid_at
    FROM paid_orders
    GROUP BY tenant_id, buyer_id
), latest_paid_day AS (
    SELECT
        tenant_id,
        MAX(DATE(recorded_at)) AS latest_paid_date,
        COUNT(DISTINCT order_id) AS loaded_paid_order_count,
        MAX(recorded_at) AS data_freshness_at
    FROM paid_orders
    GROUP BY tenant_id
), new_paid_buyer_rollup AS (
    SELECT
        window.tenant_id,
        window.latest_paid_date,
        COUNT(DISTINCT buyer.buyer_id) AS new_paid_buyer_count,
        window.loaded_paid_order_count,
        window.data_freshness_at
    FROM latest_paid_day window
    JOIN buyer_first_paid buyer
      ON buyer.tenant_id = window.tenant_id
     AND DATE(buyer.first_paid_at) = window.latest_paid_date
    GROUP BY
        window.tenant_id,
        window.latest_paid_date,
        window.loaded_paid_order_count,
        window.data_freshness_at
), metric_rows AS (
    SELECT
        tenant_id,
        'funnel.visit_to_pay_rate' AS metric_id,
        CAST(paid_visitor_count * 100.0 / NULLIF(visitor_count, 0) AS DECIMAL(38,6)) AS metric_value,
        CAST(paid_visitor_count AS DECIMAL(38,6)) AS numerator,
        CAST(visitor_count AS DECIMAL(38,6)) AS denominator,
        'percent' AS unit,
        session_count AS source_row_count,
        'Strict session payment-attributed subjects divided by linked-or-anonymous visitors' AS evidence_note,
        data_freshness_at
    FROM behavior_rollup
    UNION ALL
    SELECT
        tenant_id,
        'funnel.cart_abandonment_rate',
        CAST(unpaid_cart_subject_count * 100.0 / NULLIF(cart_subject_count, 0) AS DECIMAL(38,6)),
        CAST(unpaid_cart_subject_count AS DECIMAL(38,6)),
        CAST(cart_subject_count AS DECIMAL(38,6)),
        'percent',
        session_count,
        'Distinct cart subjects without strict session payment attribution in loaded behavior history',
        data_freshness_at
    FROM behavior_rollup
    UNION ALL
    SELECT
        tenant_id,
        'buyer.new_paid_buyer_count',
        CAST(new_paid_buyer_count AS DECIMAL(38,6)),
        CAST(new_paid_buyer_count AS DECIMAL(38,6)),
        CAST(NULL AS DECIMAL(38,6)),
        'count',
        loaded_paid_order_count,
        CONCAT('First-ever paid buyers on latest loaded paid business day ', CAST(latest_paid_date AS STRING)),
        data_freshness_at
    FROM new_paid_buyer_rollup
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
