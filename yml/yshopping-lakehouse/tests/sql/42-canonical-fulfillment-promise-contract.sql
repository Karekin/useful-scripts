SELECT 'fulfillment_promise_current_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, fulfillment_id
    FROM yshopping_dws.dws_canonical_fulfillment_promise_current
    GROUP BY tenant_id, fulfillment_id
    HAVING COUNT(*) <> 1
) duplicate_rows
UNION ALL
SELECT 'fulfillment_promise_pair_incomplete', COUNT(*)
FROM yshopping_dws.dws_canonical_fulfillment_promise_current
WHERE delivery_promise_present = TRUE
  AND (delivery_promise_version_ref IS NULL OR promised_delivery_at IS NULL OR promise_frozen_at IS NULL)
UNION ALL
SELECT 'fulfillment_promise_frozen_after_deadline', COUNT(*)
FROM yshopping_dws.dws_canonical_fulfillment_promise_current
WHERE delivery_promise_present = TRUE
  AND promise_frozen_at > promised_delivery_at
UNION ALL
SELECT 'fulfillment_promise_readiness_invalid', COUNT(*)
FROM yshopping_ads.ads_canonical_fulfillment_promise_readiness
WHERE readiness_status NOT IN (
    'PROMISE_MISSING',
    'PROMISED_DELIVERED_ON_TIME',
    'PROMISED_DELIVERED_LATE',
    'PROMISED_PENDING',
    'PROMISE_INCOMPLETE'
)
UNION ALL
SELECT 'fulfillment_promise_on_time_state_invalid', COUNT(*)
FROM yshopping_ads.ads_canonical_fulfillment_promise_readiness
WHERE readiness_status = 'PROMISED_DELIVERED_ON_TIME'
  AND (fulfillment_status <> 'DELIVERED' OR delivered_on_time <> TRUE)
UNION ALL
SELECT 'fulfillment_promise_late_state_invalid', COUNT(*)
FROM yshopping_ads.ads_canonical_fulfillment_promise_readiness
WHERE readiness_status = 'PROMISED_DELIVERED_LATE'
  AND (fulfillment_status <> 'DELIVERED' OR delivered_on_time <> FALSE)
UNION ALL
SELECT 'fulfillment_promise_metric_rate_mismatch', COUNT(*)
FROM yshopping_ads.ads_canonical_fulfillment_promise_metrics
WHERE delivered_promise_count <= 0
   OR on_time_delivery_count > delivered_promise_count
   OR ABS(fulfillment_on_time_delivery_rate - buyer_delivery_promise_hit_rate) > 0.000001;
