CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_merchant_acquisition_daily AS
WITH governed_store_touch AS (
    SELECT
        tenant_id,
        session_id,
        merchant_id,
        shop_id,
        channel_code,
        MIN(COALESCE(behavior_occurred_at, occurred_at)) AS first_store_touch_at
    FROM yshopping_dwd.dwd_canonical_commerce_behavior_event
    WHERE merchant_id IS NOT NULL
      AND shop_id IS NOT NULL
      AND listing_id IS NOT NULL
      AND listing_offer_id IS NOT NULL
      AND behavior_type IN ('PDP_VIEWED', 'SEARCH_RESULT_CLICKED', 'CART_ADDED', 'CHECKOUT_STARTED')
    GROUP BY tenant_id, session_id, merchant_id, shop_id, channel_code
), paid_store_session AS (
    SELECT
        touch.tenant_id,
        touch.session_id,
        touch.merchant_id,
        touch.shop_id,
        touch.channel_code,
        touch.first_store_touch_at,
        attribution.principal_id,
        MIN(COALESCE(attribution.attributed_at, attribution.occurred_at)) AS first_paid_at
    FROM governed_store_touch touch
    JOIN yshopping_dwd.dwd_canonical_commerce_session_payment_attribution_event attribution
      ON attribution.tenant_id = touch.tenant_id
     AND attribution.session_id = touch.session_id
     AND attribution.merchant_id = touch.merchant_id
     AND attribution.shop_id = touch.shop_id
     AND attribution.channel_code = touch.channel_code
    GROUP BY
        touch.tenant_id,
        touch.session_id,
        touch.merchant_id,
        touch.shop_id,
        touch.channel_code,
        touch.first_store_touch_at,
        attribution.principal_id
), first_merchant_payment AS (
    SELECT
        ranked.tenant_id,
        ranked.merchant_id,
        ranked.shop_id,
        ranked.channel_code,
        ranked.principal_id,
        ranked.first_paid_at
    FROM (
        SELECT
            tenant_id,
            merchant_id,
            shop_id,
            channel_code,
            principal_id,
            COALESCE(attributed_at, occurred_at) AS first_paid_at,
            ROW_NUMBER() OVER (
                PARTITION BY tenant_id, merchant_id, principal_id
                ORDER BY COALESCE(attributed_at, occurred_at), recorded_at, event_id
            ) AS row_num
        FROM yshopping_dwd.dwd_canonical_commerce_session_payment_attribution_event
        WHERE merchant_id IS NOT NULL
          AND shop_id IS NOT NULL
          AND principal_id IS NOT NULL
    ) ranked
    WHERE ranked.row_num = 1
), store_visit_daily AS (
    SELECT
        tenant_id,
        DATE(first_store_touch_at) AS metric_date,
        merchant_id,
        shop_id,
        channel_code,
        COUNT(DISTINCT session_id) AS store_visitor_count
    FROM governed_store_touch
    GROUP BY tenant_id, DATE(first_store_touch_at), merchant_id, shop_id, channel_code
), paid_store_daily AS (
    SELECT
        tenant_id,
        DATE(first_store_touch_at) AS metric_date,
        merchant_id,
        shop_id,
        channel_code,
        COUNT(DISTINCT session_id) AS paid_session_count,
        COUNT(DISTINCT principal_id) AS paid_buyer_count,
        MAX(first_paid_at) AS latest_paid_at
    FROM paid_store_session
    GROUP BY tenant_id, DATE(first_store_touch_at), merchant_id, shop_id, channel_code
), new_buyer_daily AS (
    SELECT
        tenant_id,
        DATE(first_paid_at) AS metric_date,
        merchant_id,
        shop_id,
        channel_code,
        COUNT(DISTINCT principal_id) AS new_buyer_count
    FROM first_merchant_payment
    GROUP BY tenant_id, DATE(first_paid_at), merchant_id, shop_id, channel_code
), metric_keys AS (
    SELECT tenant_id, metric_date, merchant_id, shop_id, channel_code FROM store_visit_daily
    UNION DISTINCT
    SELECT tenant_id, metric_date, merchant_id, shop_id, channel_code FROM new_buyer_daily
)
SELECT
    metric_keys.tenant_id,
    metric_keys.metric_date,
    metric_keys.merchant_id,
    metric_keys.shop_id,
    metric_keys.channel_code,
    COALESCE(store_visit_daily.store_visitor_count, 0) AS store_visitor_count,
    COALESCE(paid_store_daily.paid_session_count, 0) AS paid_session_count,
    COALESCE(paid_store_daily.paid_buyer_count, 0) AS paid_buyer_count,
    COALESCE(new_buyer_daily.new_buyer_count, 0) AS new_buyer_count,
    ROUND(
        100.0 * COALESCE(paid_store_daily.paid_buyer_count, 0)
        / NULLIF(store_visit_daily.store_visitor_count, 0),
        2
    ) AS store_conversion_rate,
    paid_store_daily.latest_paid_at,
    'GOVERNED_LISTING_OFFER_TO_MERCHANT_STORE_ATTRIBUTION' AS model_semantics
FROM metric_keys
LEFT JOIN store_visit_daily
  ON store_visit_daily.tenant_id = metric_keys.tenant_id
 AND store_visit_daily.metric_date = metric_keys.metric_date
 AND store_visit_daily.merchant_id = metric_keys.merchant_id
 AND store_visit_daily.shop_id = metric_keys.shop_id
 AND store_visit_daily.channel_code = metric_keys.channel_code
LEFT JOIN paid_store_daily
  ON paid_store_daily.tenant_id = metric_keys.tenant_id
 AND paid_store_daily.metric_date = metric_keys.metric_date
 AND paid_store_daily.merchant_id = metric_keys.merchant_id
 AND paid_store_daily.shop_id = metric_keys.shop_id
 AND paid_store_daily.channel_code = metric_keys.channel_code
LEFT JOIN new_buyer_daily
  ON new_buyer_daily.tenant_id = metric_keys.tenant_id
 AND new_buyer_daily.metric_date = metric_keys.metric_date
 AND new_buyer_daily.merchant_id = metric_keys.merchant_id
 AND new_buyer_daily.shop_id = metric_keys.shop_id
 AND new_buyer_daily.channel_code = metric_keys.channel_code;
