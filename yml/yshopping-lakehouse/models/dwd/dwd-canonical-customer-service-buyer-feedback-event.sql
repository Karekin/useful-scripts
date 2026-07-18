CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_customer_service_buyer_feedback_event AS
SELECT event_id,
       tenant_id,
       aggregate_id AS feedback_id,
       aggregate_version,
       occurred_at AS event_occurred_at,
       recorded_at,
       correlation_id,
       causation_id,
       idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.ticket_id') AS ticket_id,
       get_json_string(payload, '$.customer_principal_id') AS customer_principal_id,
       get_json_string(payload, '$.touchpoint_code') AS touchpoint_code,
       get_json_string(payload, '$.sentiment_code') AS sentiment_code,
       CAST(get_json_string(payload, '$.score_basis_points') AS INT) AS score_basis_points,
       get_json_string(payload, '$.reason_code') AS reason_code,
       get_json_string(payload, '$.comment_token') AS comment_token,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'customer_service.buyer_feedback.recorded'
  AND schema_version = 1
  AND source_system = 'cloudmold-customer-service';
