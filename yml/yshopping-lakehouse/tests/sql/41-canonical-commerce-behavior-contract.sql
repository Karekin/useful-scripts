SELECT 'commerce_session_current_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, session_id
    FROM yshopping_dim.dim_canonical_commerce_session_current
    GROUP BY tenant_id, session_id
    HAVING COUNT(*) <> 1
) duplicate_session;

SELECT 'commerce_session_link_without_principal' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_commerce_session_current
WHERE identity_link_event_count > 0
  AND current_principal_id IS NULL;

SELECT 'commerce_session_funnel_invalid_timeline' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_commerce_session_funnel
WHERE (first_search_requested_at IS NOT NULL AND first_search_requested_at < started_at)
   OR (first_search_result_exposed_at IS NOT NULL AND first_search_requested_at IS NULL)
   OR (first_search_result_exposed_at IS NOT NULL AND first_search_result_exposed_at < first_search_requested_at)
   OR (first_search_result_clicked_at IS NOT NULL AND first_search_result_exposed_at IS NULL)
   OR (first_search_result_clicked_at IS NOT NULL AND first_search_result_clicked_at < first_search_result_exposed_at)
   OR (first_checkout_started_at IS NOT NULL AND first_cart_added_at IS NULL)
   OR (first_checkout_abandoned_at IS NOT NULL AND first_checkout_started_at IS NULL)
   OR (first_paid_at IS NOT NULL AND first_checkout_started_at IS NULL)
   OR (first_paid_at IS NOT NULL AND first_paid_at < first_checkout_started_at);

SELECT 'commerce_session_payment_attribution_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, payment_id
    FROM yshopping_dwd.dwd_canonical_commerce_session_payment_attribution_event
    GROUP BY tenant_id, payment_id
    HAVING COUNT(*) <> 1
) duplicate_payment_attribution;

SELECT 'commerce_session_payment_attribution_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_commerce_session_payment_attribution_event
WHERE checkout_token IS NULL
   OR order_id IS NULL
   OR payment_id IS NULL
   OR order_status NOT IN ('PAYMENT_CONFIRMED', 'SHIPPED', 'DELIVERED', 'COMPLETED', 'RETURNED')
   OR attributed_at IS NULL;

SELECT 'commerce_session_funnel_search_count_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_commerce_session_funnel
WHERE (search_requested_session_flag = 0 AND search_request_count <> 0)
   OR (search_requested_session_flag = 1 AND search_request_count = 0)
   OR search_exposed_session_flag > search_requested_session_flag
   OR search_click_session_flag > search_exposed_session_flag
   OR checkout_abandoned_session_flag > checkout_session_flag
   OR paid_session_flag > checkout_session_flag;

SELECT 'commerce_search_request_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, session_id, search_token
    FROM yshopping_dws.dws_canonical_commerce_search_request_funnel
    GROUP BY tenant_id, session_id, search_token
    HAVING COUNT(*) <> 1
) duplicate_request;

SELECT 'commerce_search_request_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_commerce_search_request_funnel
WHERE requested_at IS NULL
   OR search_token IS NULL
   OR (search_result_exposed_flag = 1 AND first_result_exposed_at < requested_at)
   OR (search_result_clicked_flag = 1 AND first_result_clicked_at < requested_at)
   OR (search_result_clicked_flag = 1 AND search_result_exposed_flag = 0)
   OR (search_result_clicked_flag = 1 AND best_clicked_result_position IS NULL)
   OR (checkout_started_flag = 1 AND cart_added_flag = 0)
   OR (checkout_abandoned_flag = 1 AND checkout_started_flag = 0);

SELECT 'commerce_acquisition_funnel_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_commerce_acquisition_funnel
WHERE session_count <= 0
   OR linked_session_count > session_count
   OR engaged_session_count > session_count
   OR pdp_viewed_session_count > session_count
   OR search_requested_session_count > session_count
   OR search_exposed_session_count > search_requested_session_count
   OR search_click_session_count > search_exposed_session_count
   OR cart_added_session_count > session_count
   OR cart_removed_session_count > cart_added_session_count
   OR checkout_session_count > cart_added_session_count
   OR checkout_abandoned_session_count > checkout_session_count
   OR paid_session_count > checkout_session_count
   OR abandoned_session_count > session_count
   OR expired_session_count > session_count
   OR engagement_rate < 0 OR engagement_rate > 100
   OR search_request_rate < 0 OR search_request_rate > 100
   OR cart_add_rate < 0 OR cart_add_rate > 100
   OR checkout_rate < 0 OR checkout_rate > 100
   OR visit_to_pay_rate < 0 OR visit_to_pay_rate > 100
   OR abandoned_rate < 0 OR abandoned_rate > 100
   OR model_semantics <> 'CANONICAL_COMMERCE_BEHAVIOR_SESSION_FUNNEL';

SELECT 'merchant_acquisition_dimension_missing' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_merchant_acquisition_daily
WHERE merchant_id IS NULL
   OR shop_id IS NULL
   OR channel_code IS NULL
   OR model_semantics <> 'GOVERNED_LISTING_OFFER_TO_MERCHANT_STORE_ATTRIBUTION';

SELECT 'merchant_acquisition_metric_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_merchant_acquisition_daily
WHERE store_visitor_count < 0
   OR paid_session_count < 0
   OR paid_buyer_count < 0
   OR new_buyer_count < 0
   OR paid_session_count > store_visitor_count
   OR paid_buyer_count > paid_session_count
   OR (store_visitor_count = 0 AND paid_buyer_count > 0)
   OR store_conversion_rate < 0
   OR store_conversion_rate > 100;

SELECT 'merchant_acquisition_ads_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_merchant_acquisition_metrics ads
LEFT JOIN yshopping_dws.dws_canonical_merchant_acquisition_daily dws
  ON dws.tenant_id = ads.tenant_id
 AND dws.metric_date = ads.metric_date
 AND dws.merchant_id = ads.merchant_id
 AND dws.shop_id = ads.shop_id
 AND dws.channel_code = ads.channel_code
WHERE dws.tenant_id IS NULL
   OR ads.store_visitor_count <> dws.store_visitor_count
   OR ads.paid_buyer_count <> dws.paid_buyer_count
   OR ads.new_buyer_count <> dws.new_buyer_count
   OR NOT (ads.store_conversion_rate <=> dws.store_conversion_rate);
