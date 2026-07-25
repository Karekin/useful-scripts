CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_engagement_reaction_event AS
SELECT
    event_id,
    tenant_id,
    aggregate_id AS reaction_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.actor_principal_id') AS actor_principal_id,
    get_json_string(payload, '$.reaction_type') AS reaction_type,
    get_json_string(payload, '$.target_type') AS target_type,
    get_json_string(payload, '$.target_id') AS target_id,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.community.reaction_status_changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-engagement';
