CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_commerce_session_funnel AS
SELECT
    session_current.tenant_id,
    session_current.session_id,
    DATE(session_current.started_at) AS session_date,
    session_current.current_status,
    session_current.started_at,
    session_current.last_activity_at,
    session_current.channel_code,
    session_current.entrypoint_code,
    session_current.current_principal_id,
    session_current.behavior_event_count,
    session_current.search_request_count,
    session_current.result_set_count,
    attribution.first_paid_at,
    attribution.paid_order_count,
    attribution.paid_payment_count,
    attribution.paid_shop_id,
    attribution.paid_channel_code,
    behavior.first_pdp_viewed_at,
    behavior.first_search_requested_at,
    behavior.first_search_result_exposed_at,
    behavior.first_search_result_clicked_at,
    behavior.first_cart_added_at,
    behavior.first_cart_removed_at,
    behavior.first_checkout_started_at,
    behavior.first_checkout_abandoned_at,
    CASE
        WHEN session_current.behavior_event_count > 0 THEN 1
        ELSE 0
    END AS engaged_session_flag,
    CASE WHEN behavior.first_pdp_viewed_at IS NULL THEN 0 ELSE 1 END AS pdp_viewed_session_flag,
    CASE WHEN behavior.first_search_requested_at IS NULL THEN 0 ELSE 1 END AS search_requested_session_flag,
    CASE WHEN behavior.first_search_result_exposed_at IS NULL THEN 0 ELSE 1 END AS search_exposed_session_flag,
    CASE WHEN behavior.first_search_result_clicked_at IS NULL THEN 0 ELSE 1 END AS search_click_session_flag,
    CASE WHEN behavior.first_cart_added_at IS NULL THEN 0 ELSE 1 END AS cart_added_session_flag,
    CASE WHEN behavior.first_cart_removed_at IS NULL THEN 0 ELSE 1 END AS cart_removed_session_flag,
    CASE WHEN behavior.first_checkout_started_at IS NULL THEN 0 ELSE 1 END AS checkout_session_flag,
    CASE WHEN behavior.first_checkout_abandoned_at IS NULL THEN 0 ELSE 1 END AS checkout_abandoned_session_flag,
    CASE WHEN attribution.first_paid_at IS NULL THEN 0 ELSE 1 END AS paid_session_flag,
    CASE WHEN session_current.current_principal_id IS NULL THEN 0 ELSE 1 END AS linked_session_flag,
    CASE WHEN session_current.current_status = 'ABANDONED' THEN 1 ELSE 0 END AS abandoned_session_flag,
    CASE WHEN session_current.current_status = 'EXPIRED' THEN 1 ELSE 0 END AS expired_session_flag
FROM yshopping_dim.dim_canonical_commerce_session_current session_current
LEFT JOIN (
    SELECT
        tenant_id,
        session_id,
        MIN(COALESCE(attributed_at, occurred_at)) AS first_paid_at,
        COUNT(DISTINCT order_id) AS paid_order_count,
        COUNT(DISTINCT payment_id) AS paid_payment_count,
        CASE WHEN COUNT(DISTINCT COALESCE(shop_id, '')) = 1 THEN MAX(shop_id) ELSE NULL END AS paid_shop_id,
        CASE WHEN COUNT(DISTINCT COALESCE(channel_code, '')) = 1 THEN MAX(channel_code) ELSE NULL END AS paid_channel_code
    FROM yshopping_dwd.dwd_canonical_commerce_session_payment_attribution_event
    GROUP BY tenant_id, session_id
) attribution
  ON attribution.tenant_id = session_current.tenant_id
 AND attribution.session_id = session_current.session_id
LEFT JOIN (
    SELECT
        tenant_id,
        session_id,
        MIN(CASE WHEN behavior_type = 'PDP_VIEWED' THEN COALESCE(behavior_occurred_at, occurred_at) END) AS first_pdp_viewed_at,
        MIN(CASE WHEN behavior_type = 'SEARCH_REQUESTED' THEN COALESCE(behavior_occurred_at, occurred_at) END) AS first_search_requested_at,
        MIN(CASE WHEN behavior_type = 'SEARCH_RESULT_EXPOSED' THEN COALESCE(behavior_occurred_at, occurred_at) END) AS first_search_result_exposed_at,
        MIN(CASE WHEN behavior_type = 'SEARCH_RESULT_CLICKED' THEN COALESCE(behavior_occurred_at, occurred_at) END) AS first_search_result_clicked_at,
        MIN(CASE WHEN behavior_type = 'CART_ADDED' THEN COALESCE(behavior_occurred_at, occurred_at) END) AS first_cart_added_at,
        MIN(CASE WHEN behavior_type = 'CART_REMOVED' THEN COALESCE(behavior_occurred_at, occurred_at) END) AS first_cart_removed_at,
        MIN(CASE WHEN behavior_type = 'CHECKOUT_STARTED' THEN COALESCE(behavior_occurred_at, occurred_at) END) AS first_checkout_started_at,
        MIN(CASE WHEN behavior_type = 'CHECKOUT_ABANDONED' THEN COALESCE(behavior_occurred_at, occurred_at) END) AS first_checkout_abandoned_at
    FROM yshopping_dwd.dwd_canonical_commerce_behavior_event
    GROUP BY tenant_id, session_id
) behavior
  ON behavior.tenant_id = session_current.tenant_id
 AND behavior.session_id = session_current.session_id;
