CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_commerce_search_request_funnel AS
SELECT
    submitted.tenant_id,
    submitted.session_id,
    submitted.search_token,
    DATE(submitted.requested_at) AS search_date,
    submitted.requested_at,
    progression.first_result_exposed_at,
    progression.first_result_clicked_at,
    progression.first_pdp_viewed_at,
    progression.first_cart_added_at,
    progression.first_checkout_started_at,
    progression.first_checkout_abandoned_at,
    progression.result_set_count,
    progression.search_click_count,
    1 AS search_requested_flag,
    CASE WHEN progression.first_result_exposed_at IS NULL THEN 0 ELSE 1 END AS search_result_exposed_flag,
    CASE WHEN progression.first_result_clicked_at IS NULL THEN 0 ELSE 1 END AS search_result_clicked_flag,
    CASE WHEN progression.first_pdp_viewed_at IS NULL THEN 0 ELSE 1 END AS pdp_viewed_flag,
    CASE WHEN progression.first_cart_added_at IS NULL THEN 0 ELSE 1 END AS cart_added_flag,
    CASE WHEN progression.first_checkout_started_at IS NULL THEN 0 ELSE 1 END AS checkout_started_flag,
    CASE WHEN progression.first_checkout_abandoned_at IS NULL THEN 0 ELSE 1 END AS checkout_abandoned_flag,
    progression.best_clicked_result_position
FROM (
    SELECT
        tenant_id,
        session_id,
        search_token,
        MIN(COALESCE(behavior_occurred_at, occurred_at)) AS requested_at
    FROM yshopping_dwd.dwd_canonical_commerce_behavior_event
    WHERE behavior_type = 'SEARCH_REQUESTED'
      AND search_token IS NOT NULL
    GROUP BY tenant_id, session_id, search_token
) submitted
LEFT JOIN (
    SELECT
        request.tenant_id,
        request.session_id,
        request.search_token,
        MIN(CASE WHEN event.behavior_type = 'SEARCH_RESULT_EXPOSED' THEN COALESCE(event.behavior_occurred_at, event.occurred_at) END) AS first_result_exposed_at,
        MIN(CASE WHEN event.behavior_type = 'SEARCH_RESULT_CLICKED' THEN COALESCE(event.behavior_occurred_at, event.occurred_at) END) AS first_result_clicked_at,
        MIN(CASE WHEN event.behavior_type = 'PDP_VIEWED' THEN COALESCE(event.behavior_occurred_at, event.occurred_at) END) AS first_pdp_viewed_at,
        MIN(CASE WHEN event.behavior_type = 'CART_ADDED' THEN COALESCE(event.behavior_occurred_at, event.occurred_at) END) AS first_cart_added_at,
        MIN(CASE WHEN event.behavior_type = 'CHECKOUT_STARTED' THEN COALESCE(event.behavior_occurred_at, event.occurred_at) END) AS first_checkout_started_at,
        MIN(CASE WHEN event.behavior_type = 'CHECKOUT_ABANDONED' THEN COALESCE(event.behavior_occurred_at, event.occurred_at) END) AS first_checkout_abandoned_at,
        COUNT(DISTINCT CASE WHEN event.result_set_token IS NOT NULL THEN event.result_set_token END) AS result_set_count,
        SUM(CASE WHEN event.behavior_type = 'SEARCH_RESULT_CLICKED' THEN 1 ELSE 0 END) AS search_click_count,
        MIN(CASE WHEN event.behavior_type = 'SEARCH_RESULT_CLICKED' THEN event.result_position END) AS best_clicked_result_position
    FROM (
        SELECT
            tenant_id,
            session_id,
            search_token,
            MIN(COALESCE(behavior_occurred_at, occurred_at)) AS requested_at
        FROM yshopping_dwd.dwd_canonical_commerce_behavior_event
        WHERE behavior_type = 'SEARCH_REQUESTED'
          AND search_token IS NOT NULL
        GROUP BY tenant_id, session_id, search_token
    ) request
    LEFT JOIN yshopping_dwd.dwd_canonical_commerce_behavior_event event
      ON event.tenant_id = request.tenant_id
     AND event.session_id = request.session_id
     AND event.search_token = request.search_token
     AND COALESCE(event.behavior_occurred_at, event.occurred_at) >= request.requested_at
    GROUP BY request.tenant_id, request.session_id, request.search_token
) progression
  ON progression.tenant_id = submitted.tenant_id
 AND progression.session_id = submitted.session_id
 AND progression.search_token = submitted.search_token;
