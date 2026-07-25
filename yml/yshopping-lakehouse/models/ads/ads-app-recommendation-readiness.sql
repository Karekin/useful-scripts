CREATE OR REPLACE VIEW yshopping_ads.ads_app_recommendation_readiness AS
SELECT
    tenant_id,
    DATE(generated_at) AS metric_date,
    scene_code,
    policy_version,
    COUNT(*) AS generated_decision_count,
    SUM(served_flag) AS served_decision_count,
    SUM(exposed_flag) AS exposed_decision_count,
    SUM(clicked_flag) AS clicked_decision_count,
    SUM(item_count) AS declared_item_count,
    SUM(item_row_count) AS generated_item_row_count,
    MAX(COALESCE(first_clicked_at, first_exposed_at, served_at, generated_at)) AS data_freshness_at,
    CASE
        WHEN COUNT(*) = 0 THEN 'EMPTY'
        WHEN SUM(CASE WHEN item_count = item_row_count AND served_flag = 1 THEN 1 ELSE 0 END) = COUNT(*)
            THEN 'READY'
        ELSE 'PARTIAL'
    END AS readiness_status,
    'APP_RECOMMENDATION_DECISION_AND_EXACT_RESULTSETTOKEN_BEHAVIOR_JOIN' AS model_semantics
FROM yshopping_dws.dws_app_recommendation_effectiveness
GROUP BY tenant_id, DATE(generated_at), scene_code, policy_version;
