SELECT 'app_recommendation_current_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, decision_id
    FROM yshopping_dim.dim_app_recommendation_decision_current
    GROUP BY tenant_id, decision_id
    HAVING COUNT(*) <> 1
) duplicate_decision;

SELECT 'app_recommendation_served_before_generated' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_app_recommendation_decision_current
WHERE served_at IS NOT NULL
  AND generated_at IS NOT NULL
  AND served_at < generated_at;

SELECT 'app_recommendation_item_count_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_app_recommendation_effectiveness
WHERE item_count <> item_row_count
   OR distinct_listing_count > item_row_count;

SELECT 'app_recommendation_behavior_exact_join_missing' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_commerce_behavior_event behavior
LEFT JOIN yshopping_dwd.dwd_app_recommendation_item_event item
  ON item.tenant_id = behavior.tenant_id
 AND item.event_type = 'app.recommendation.generated'
 AND item.decision_token = behavior.result_set_token
 AND item.listing_id = behavior.listing_id
 AND item.rank_no = behavior.result_position
WHERE behavior.behavior_type IN ('RECOMMENDATION_EXPOSED', 'RECOMMENDATION_CLICKED')
  AND item.decision_id IS NULL;

SELECT 'app_cart_current_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, cart_id
    FROM yshopping_dim.dim_app_cart_current
    GROUP BY tenant_id, cart_id
    HAVING COUNT(*) <> 1
) duplicate_cart;

SELECT 'app_cart_selected_count_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_app_cart_current
WHERE line_count < 0
   OR selected_line_count < 0
   OR selected_line_count > line_count;

SELECT 'app_cart_line_materialization_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_app_cart_current
WHERE line_count <> line_row_count
   OR selected_line_count <> selected_item_row_count;
