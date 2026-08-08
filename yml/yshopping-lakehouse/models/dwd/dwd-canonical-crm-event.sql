-- PII-safe CRM first slice. Raw mobile, phone, email, address and free-text follow-up content stay outside the lakehouse.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_crm_customer_status_event AS
SELECT event_id, tenant_id, aggregate_id AS customer_aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.customer_id') AS customer_id,
       get_json_string(payload, '$.customer_code') AS customer_code,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.follow_up_status') AS BOOLEAN) AS follow_up_status,
       CAST(get_json_string(payload, '$.deal_status') AS BOOLEAN) AS deal_status,
       CAST(get_json_string(payload, '$.lock_status') AS BOOLEAN) AS lock_status,
       get_json_string(payload, '$.source_code') AS source_code,
       get_json_string(payload, '$.industry_code') AS industry_code,
       get_json_string(payload, '$.level_code') AS level_code,
       CAST(get_json_string(payload, '$.last_follow_up_at') AS DATETIME) AS last_follow_up_at,
       CAST(get_json_string(payload, '$.next_contact_at') AS DATETIME) AS next_contact_at,
       CAST(get_json_string(payload, '$.linked_contact_count') AS INT) AS linked_contact_count,
       CAST(get_json_string(payload, '$.linked_opportunity_count') AS INT) AS linked_opportunity_count
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'crm.customer.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-crm';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_crm_customer_owner_event AS
SELECT event_id, tenant_id, aggregate_id AS owner_change_aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.owner_change_id') AS owner_change_id,
       get_json_string(payload, '$.customer_id') AS customer_id,
       get_json_string(payload, '$.customer_code') AS customer_code,
       get_json_string(payload, '$.previous_owner_principal_id') AS previous_owner_principal_id,
       get_json_string(payload, '$.current_owner_principal_id') AS current_owner_principal_id,
       CAST(get_json_string(payload, '$.transferred_at') AS DATETIME) AS transferred_at,
       get_json_string(payload, '$.handover_reason_code') AS handover_reason_code,
       CAST(get_json_string(payload, '$.open_opportunity_count') AS INT) AS open_opportunity_count,
       CAST(get_json_string(payload, '$.open_pipeline_amount_minor') AS BIGINT) AS open_pipeline_amount_minor,
       get_json_string(payload, '$.currency_code') AS currency_code
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'crm.customer.owner_changed' AND schema_version = 1
  AND source_system = 'cloudmold-crm';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_crm_lead_status_event AS
SELECT event_id, tenant_id, aggregate_id AS lead_aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.lead_id') AS lead_id,
       get_json_string(payload, '$.lead_code') AS lead_code,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.follow_up_status') AS BOOLEAN) AS follow_up_status,
       get_json_string(payload, '$.source_code') AS source_code,
       get_json_string(payload, '$.industry_code') AS industry_code,
       get_json_string(payload, '$.level_code') AS level_code,
       get_json_string(payload, '$.converted_customer_id') AS converted_customer_id,
       CAST(get_json_string(payload, '$.last_follow_up_at') AS DATETIME) AS last_follow_up_at,
       CAST(get_json_string(payload, '$.next_contact_at') AS DATETIME) AS next_contact_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'crm.lead.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-crm';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_crm_contact_status_event AS
SELECT event_id, tenant_id, aggregate_id AS contact_aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.contact_id') AS contact_id,
       get_json_string(payload, '$.contact_code') AS contact_code,
       get_json_string(payload, '$.customer_id') AS customer_id,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.follow_up_status') AS BOOLEAN) AS follow_up_status,
       CAST(get_json_string(payload, '$.master_decision_maker') AS BOOLEAN) AS master_decision_maker,
       get_json_string(payload, '$.post_code') AS post_code,
       get_json_string(payload, '$.parent_contact_id') AS parent_contact_id,
       CAST(get_json_string(payload, '$.last_follow_up_at') AS DATETIME) AS last_follow_up_at,
       CAST(get_json_string(payload, '$.next_contact_at') AS DATETIME) AS next_contact_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'crm.contact.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-crm';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_crm_opportunity_stage_event AS
SELECT event_id, tenant_id, aggregate_id AS opportunity_aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.opportunity_id') AS opportunity_id,
       get_json_string(payload, '$.opportunity_code') AS opportunity_code,
       get_json_string(payload, '$.customer_id') AS customer_id,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.previous_stage_code') AS previous_stage_code,
       get_json_string(payload, '$.current_stage_code') AS current_stage_code,
       get_json_string(payload, '$.previous_pipeline_status') AS previous_pipeline_status,
       get_json_string(payload, '$.current_pipeline_status') AS current_pipeline_status,
       CAST(get_json_string(payload, '$.follow_up_status') AS BOOLEAN) AS follow_up_status,
       CAST(get_json_string(payload, '$.expected_deal_at') AS DATETIME) AS expected_deal_at,
       CAST(get_json_string(payload, '$.total_amount_minor') AS BIGINT) AS total_amount_minor,
       get_json_string(payload, '$.currency_code') AS currency_code,
       CAST(get_json_string(payload, '$.win_probability_basis_points') AS INT) AS win_probability_basis_points,
       CAST(get_json_string(payload, '$.linked_contact_count') AS INT) AS linked_contact_count,
       CAST(get_json_string(payload, '$.last_follow_up_at') AS DATETIME) AS last_follow_up_at,
       CAST(get_json_string(payload, '$.next_contact_at') AS DATETIME) AS next_contact_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'crm.opportunity.stage_changed' AND schema_version = 1
  AND source_system = 'cloudmold-crm';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_crm_follow_up_event AS
SELECT event_id, tenant_id, aggregate_id AS follow_up_aggregate_id, aggregate_version, occurred_at AS event_occurred_at,
       recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.run_id') AS run_id,
       get_json_string(payload, '$.follow_up_id') AS follow_up_id,
       get_json_string(payload, '$.biz_type') AS biz_type,
       get_json_string(payload, '$.biz_id') AS biz_id,
       get_json_string(payload, '$.customer_id') AS customer_id,
       get_json_string(payload, '$.lead_id') AS lead_id,
       get_json_string(payload, '$.contact_id') AS contact_id,
       get_json_string(payload, '$.opportunity_id') AS opportunity_id,
       get_json_string(payload, '$.owner_principal_id') AS owner_principal_id,
       get_json_string(payload, '$.actor_principal_id') AS actor_principal_id,
       get_json_string(payload, '$.follow_up_type_code') AS follow_up_type_code,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at,
       CAST(get_json_string(payload, '$.next_contact_at') AS DATETIME) AS next_contact_at,
       get_json_string(payload, '$.content_token') AS content_token,
       CAST(get_json_string(payload, '$.attachment_count') AS INT) AS attachment_count
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'crm.follow_up.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-crm';
