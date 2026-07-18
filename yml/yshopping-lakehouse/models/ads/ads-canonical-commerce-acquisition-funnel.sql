CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_commerce_acquisition_funnel AS
SELECT
    tenant_id,
    session_date,
    channel_code,
    entrypoint_code,
    COUNT(*) AS session_count,
    SUM(linked_session_flag) AS linked_session_count,
    SUM(engaged_session_flag) AS engaged_session_count,
    SUM(pdp_viewed_session_flag) AS pdp_viewed_session_count,
    SUM(search_requested_session_flag) AS search_requested_session_count,
    SUM(search_exposed_session_flag) AS search_exposed_session_count,
    SUM(search_click_session_flag) AS search_click_session_count,
    SUM(cart_added_session_flag) AS cart_added_session_count,
    SUM(cart_removed_session_flag) AS cart_removed_session_count,
    SUM(checkout_session_flag) AS checkout_session_count,
    SUM(checkout_abandoned_session_flag) AS checkout_abandoned_session_count,
    SUM(paid_session_flag) AS paid_session_count,
    SUM(abandoned_session_flag) AS abandoned_session_count,
    SUM(expired_session_flag) AS expired_session_count,
    ROUND(100.0 * SUM(engaged_session_flag) / NULLIF(COUNT(*), 0), 2) AS engagement_rate,
    ROUND(100.0 * SUM(search_requested_session_flag) / NULLIF(COUNT(*), 0), 2) AS search_request_rate,
    ROUND(100.0 * SUM(cart_added_session_flag) / NULLIF(COUNT(*), 0), 2) AS cart_add_rate,
    ROUND(100.0 * SUM(checkout_session_flag) / NULLIF(COUNT(*), 0), 2) AS checkout_rate,
    ROUND(100.0 * SUM(paid_session_flag) / NULLIF(COUNT(*), 0), 2) AS visit_to_pay_rate,
    ROUND(100.0 * SUM(abandoned_session_flag) / NULLIF(COUNT(*), 0), 2) AS abandoned_rate,
    MAX(last_activity_at) AS data_freshness_at,
    'CANONICAL_COMMERCE_BEHAVIOR_SESSION_FUNNEL' AS model_semantics
FROM yshopping_dws.dws_canonical_commerce_session_funnel
GROUP BY
    tenant_id,
    session_date,
    channel_code,
    entrypoint_code;
