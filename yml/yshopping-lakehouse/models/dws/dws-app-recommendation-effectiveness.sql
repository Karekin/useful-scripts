CREATE OR REPLACE VIEW yshopping_dws.dws_app_recommendation_effectiveness AS
WITH item_rollup AS (
    SELECT
        tenant_id,
        decision_id,
        decision_token,
        COUNT(*) AS item_row_count,
        COUNT(DISTINCT listing_id) AS distinct_listing_count,
        MIN(occurred_at) AS generated_at
    FROM yshopping_dwd.dwd_app_recommendation_item_event
    WHERE event_type = 'app.recommendation.generated'
    GROUP BY tenant_id, decision_id, decision_token
), behavior_rollup AS (
    SELECT
        item.tenant_id,
        item.decision_id,
        item.decision_token,
        COUNT(DISTINCT CASE WHEN behavior.behavior_type = 'RECOMMENDATION_EXPOSED'
            THEN CONCAT(behavior.listing_id, ':', CAST(behavior.result_position AS STRING)) END) AS exposed_item_count,
        COUNT(DISTINCT CASE WHEN behavior.behavior_type = 'RECOMMENDATION_CLICKED'
            THEN CONCAT(behavior.listing_id, ':', CAST(behavior.result_position AS STRING)) END) AS clicked_item_count,
        MIN(CASE WHEN behavior.behavior_type = 'RECOMMENDATION_EXPOSED'
            THEN COALESCE(behavior.behavior_occurred_at, behavior.occurred_at) END) AS first_exposed_at,
        MIN(CASE WHEN behavior.behavior_type = 'RECOMMENDATION_CLICKED'
            THEN COALESCE(behavior.behavior_occurred_at, behavior.occurred_at) END) AS first_clicked_at
    FROM yshopping_dwd.dwd_app_recommendation_item_event item
    LEFT JOIN yshopping_dwd.dwd_canonical_commerce_behavior_event behavior
      ON behavior.tenant_id = item.tenant_id
     AND behavior.result_set_token = item.decision_token
     AND behavior.listing_id = item.listing_id
     AND behavior.result_position = item.rank_no
     AND behavior.behavior_type IN ('RECOMMENDATION_EXPOSED', 'RECOMMENDATION_CLICKED')
    WHERE item.event_type = 'app.recommendation.generated'
    GROUP BY item.tenant_id, item.decision_id, item.decision_token
)
SELECT
    decision.tenant_id,
    decision.decision_id,
    decision.decision_token,
    decision.session_id,
    decision.scene_code,
    decision.policy_version,
    decision.ttl_seconds,
    decision.item_count,
    item_rollup.item_row_count,
    item_rollup.distinct_listing_count,
    decision.generated_at,
    decision.served_at,
    behavior_rollup.first_exposed_at,
    behavior_rollup.first_clicked_at,
    COALESCE(behavior_rollup.exposed_item_count, 0) AS exposed_item_count,
    COALESCE(behavior_rollup.clicked_item_count, 0) AS clicked_item_count,
    CASE WHEN decision.served_flag = 1 THEN 1 ELSE 0 END AS served_flag,
    CASE WHEN COALESCE(behavior_rollup.exposed_item_count, 0) > 0 THEN 1 ELSE 0 END AS exposed_flag,
    CASE WHEN COALESCE(behavior_rollup.clicked_item_count, 0) > 0 THEN 1 ELSE 0 END AS clicked_flag,
    'APP_RECOMMENDATION_DECISION_WITH_EXACT_BEHAVIOR_TOKEN_JOIN' AS model_semantics
FROM yshopping_dim.dim_app_recommendation_decision_current decision
LEFT JOIN item_rollup
  ON item_rollup.tenant_id = decision.tenant_id
 AND item_rollup.decision_id = decision.decision_id
LEFT JOIN behavior_rollup
  ON behavior_rollup.tenant_id = decision.tenant_id
 AND behavior_rollup.decision_id = decision.decision_id;
