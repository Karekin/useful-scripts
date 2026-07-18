CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_order_case_event AS
SELECT event_id, tenant_id, aggregate_id AS order_risk_case_id, aggregate_version, occurred_at AS event_occurred_at,
       recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.case_id') AS case_id,
       get_json_string(payload, '$.order_id') AS order_id,
       get_json_string(payload, '$.payment_id') AS payment_id,
       get_json_string(payload, '$.risk_type') AS risk_type,
       get_json_string(payload, '$.reason_code') AS reason_code,
       get_json_string(payload, '$.review_status') AS review_status,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.order_review.linked' AND schema_version = 1 AND source_system = 'cloudmold-risk';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_payment_dispute_event AS
SELECT event_id, tenant_id, aggregate_id AS dispute_id, aggregate_version, occurred_at AS event_occurred_at,
       recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.order_id') AS order_id,
       get_json_string(payload, '$.payment_id') AS payment_id,
       get_json_string(payload, '$.case_id') AS case_id,
       get_json_string(payload, '$.decision_id') AS decision_id,
       get_json_string(payload, '$.dispute_type') AS dispute_type,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.reason_code') AS reason_code,
       CAST(get_json_string(payload, '$.amount_minor') AS BIGINT) AS amount_minor,
       get_json_string(payload, '$.currency_code') AS currency_code,
       get_json_string(payload, '$.external_ref') AS external_ref,
       CAST(get_json_string(payload, '$.opened_at') AS DATETIME) AS opened_at,
       CAST(get_json_string(payload, '$.resolved_at') AS DATETIME) AS resolved_at,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.payment_dispute.status_changed' AND schema_version = 1 AND source_system = 'cloudmold-risk';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_risk_loss_entry_event AS
SELECT event_id, tenant_id, aggregate_id AS loss_entry_id, aggregate_version, occurred_at AS event_occurred_at,
       recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.order_id') AS order_id,
       get_json_string(payload, '$.payment_id') AS payment_id,
       get_json_string(payload, '$.dispute_id') AS dispute_id,
       get_json_string(payload, '$.decision_id') AS decision_id,
       get_json_string(payload, '$.entry_type') AS entry_type,
       CAST(get_json_string(payload, '$.signed_amount_minor') AS BIGINT) AS signed_amount_minor,
       get_json_string(payload, '$.currency_code') AS currency_code,
       get_json_string(payload, '$.external_ref') AS external_ref,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'risk.loss_entry.posted' AND schema_version = 1 AND source_system = 'cloudmold-risk';
