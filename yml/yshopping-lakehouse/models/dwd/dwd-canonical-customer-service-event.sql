-- PII-safe customer-service first slice. Raw message bodies and object locators are intentionally absent.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_customer_service_ticket_event AS
SELECT event_id, tenant_id, aggregate_id AS ticket_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.ticket_no') AS ticket_no,
       get_json_string(payload, '$.customer_principal_id') AS customer_principal_id,
       get_json_string(payload, '$.channel_code') AS channel_code,
       get_json_string(payload, '$.priority') AS priority,
       get_json_string(payload, '$.category_code') AS category_code,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.assigned_agent_principal_id') AS assigned_agent_principal_id,
       get_json_string(payload, '$.primary_order_ref') AS primary_order_ref,
       get_json_string(payload, '$.primary_after_sale_ref') AS primary_after_sale_ref,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'customer_service.ticket.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-customer-service';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_customer_service_message_event AS
SELECT event_id, tenant_id, aggregate_id AS message_id, aggregate_version,
       occurred_at AS event_occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.ticket_id') AS ticket_id,
       get_json_string(payload, '$.direction') AS direction,
       get_json_string(payload, '$.sender_type') AS sender_type,
       get_json_string(payload, '$.sender_principal_id') AS sender_principal_id,
       get_json_string(payload, '$.message_type') AS message_type,
       get_json_string(payload, '$.content_token') AS content_token,
       CAST(get_json_string(payload, '$.attachment_count') AS INT) AS attachment_count,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'customer_service.message.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-customer-service';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_customer_service_attachment_event AS
SELECT event_id, tenant_id, aggregate_id AS attachment_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.ticket_id') AS ticket_id,
       get_json_string(payload, '$.message_id') AS message_id,
       get_json_string(payload, '$.media_type') AS media_type,
       get_json_string(payload, '$.object_token') AS object_token,
       get_json_string(payload, '$.content_sha256') AS content_sha256,
       CAST(get_json_string(payload, '$.size_bytes') AS BIGINT) AS size_bytes,
       get_json_string(payload, '$.malware_scan_status') AS malware_scan_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'customer_service.attachment.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-customer-service';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_customer_service_quality_review_event AS
SELECT event_id, tenant_id, aggregate_id AS review_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.ticket_id') AS ticket_id,
       get_json_string(payload, '$.reviewer_principal_id') AS reviewer_principal_id,
       CAST(get_json_string(payload, '$.score_basis_points') AS INT) AS score_basis_points,
       get_json_string(payload, '$.outcome_code') AS outcome_code,
       get_json_string(payload, '$.reason_code') AS reason_code
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'customer_service.quality_review.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-customer-service';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_customer_service_claim_event AS
SELECT event_id, tenant_id, aggregate_id AS claim_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.claim_code') AS claim_code,
       get_json_string(payload, '$.ticket_id') AS ticket_id,
       get_json_string(payload, '$.claim_type') AS claim_type,
       get_json_string(payload, '$.order_ref') AS order_ref,
       get_json_string(payload, '$.after_sale_ref') AS after_sale_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.requested_amount_minor') AS BIGINT) AS requested_amount_minor,
       CAST(get_json_string(payload, '$.approved_amount_minor') AS BIGINT) AS approved_amount_minor,
       CAST(get_json_string(payload, '$.paid_amount_minor') AS BIGINT) AS paid_amount_minor,
       get_json_string(payload, '$.currency_code') AS currency_code,
       get_json_string(payload, '$.reason_code') AS reason_code,
       get_json_string(payload, '$.compensation_entry_id') AS compensation_entry_id,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'customer_service.claim.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-customer-service';
