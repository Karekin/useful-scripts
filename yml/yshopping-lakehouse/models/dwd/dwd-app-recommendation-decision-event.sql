CREATE OR REPLACE VIEW yshopping_dwd.dwd_app_recommendation_decision_event AS
SELECT
    event_id,
    event_type,
    tenant_id,
    aggregate_id AS decision_id,
    aggregate_version,
    event_sequence,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.session_id') AS session_id,
    get_json_string(payload, '$.scene_code') AS scene_code,
    get_json_string(payload, '$.decision_token') AS decision_token,
    get_json_string(payload, '$.policy_version') AS policy_version,
    CAST(get_json_string(payload, '$.ttl_seconds') AS INT) AS ttl_seconds,
    CAST(get_json_string(payload, '$.item_count') AS INT) AS item_count,
    CAST(get_json_string(payload, '$.expires_at') AS DATETIME) AS expires_at,
    json_query(payload, '$.items') AS items
FROM yshopping_dwd.dwd_domain_event
WHERE event_type IN ('app.recommendation.generated', 'app.recommendation.served')
  AND schema_version = 1
  AND source_system = 'cloudmold-app-commerce';
