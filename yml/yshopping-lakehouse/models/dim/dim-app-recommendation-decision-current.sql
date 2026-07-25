CREATE OR REPLACE VIEW yshopping_dim.dim_app_recommendation_decision_current AS
WITH generated AS (
    SELECT *
    FROM yshopping_dwd.dwd_app_recommendation_decision_event
    WHERE event_type = 'app.recommendation.generated'
), served AS (
    SELECT *
    FROM yshopping_dwd.dwd_app_recommendation_decision_event
    WHERE event_type = 'app.recommendation.served'
), latest AS (
    SELECT
        event.*,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, decision_id
            ORDER BY event_sequence DESC, recorded_at DESC, event_id DESC
        ) AS row_num
    FROM yshopping_dwd.dwd_app_recommendation_decision_event event
)
SELECT
    latest.event_id,
    latest.tenant_id,
    latest.decision_id,
    latest.aggregate_version,
    latest.event_type AS current_event_type,
    latest.event_sequence,
    latest.occurred_at,
    latest.recorded_at,
    latest.session_id,
    latest.scene_code,
    latest.decision_token,
    latest.policy_version,
    latest.ttl_seconds,
    latest.item_count,
    latest.expires_at,
    generated.occurred_at AS generated_at,
    served.occurred_at AS served_at,
    CASE WHEN served.decision_id IS NULL THEN 0 ELSE 1 END AS served_flag
FROM latest
LEFT JOIN generated
  ON generated.tenant_id = latest.tenant_id
 AND generated.decision_id = latest.decision_id
LEFT JOIN served
  ON served.tenant_id = latest.tenant_id
 AND served.decision_id = latest.decision_id
WHERE latest.row_num = 1;
