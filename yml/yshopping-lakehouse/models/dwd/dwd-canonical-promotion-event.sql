-- Canonical promotion first slice: activity campaigns, coupon rights and advertising lineage.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_promotion_campaign_event AS
SELECT event_id, tenant_id, aggregate_id AS campaign_id, aggregate_version,
       occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.campaign_code') AS campaign_code,
       get_json_string(payload, '$.campaign_kind') AS campaign_kind,
       get_json_string(payload, '$.name') AS campaign_name,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.starts_at') AS DATETIME) AS starts_at,
       CAST(get_json_string(payload, '$.ends_at') AS DATETIME) AS ends_at,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'promotion.campaign.state_changed' AND schema_version = 1
  AND source_system = 'cloudmold-promotion';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_coupon_template_event AS
SELECT event_id, tenant_id, aggregate_id AS template_id, aggregate_version,
       occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.template_code') AS template_code,
       get_json_string(payload, '$.campaign_id') AS campaign_id,
       get_json_string(payload, '$.title') AS title,
       get_json_string(payload, '$.benefit_type') AS benefit_type,
       CAST(get_json_string(payload, '$.face_amount_minor') AS BIGINT) AS face_amount_minor,
       CAST(get_json_string(payload, '$.threshold_minor') AS BIGINT) AS threshold_minor,
       CAST(get_json_string(payload, '$.discount_basis_points') AS INT) AS discount_basis_points,
       CAST(get_json_string(payload, '$.cap_amount_minor') AS BIGINT) AS cap_amount_minor,
       get_json_string(payload, '$.currency_code') AS currency_code,
       get_json_string(payload, '$.funder_type') AS funder_type,
       get_json_string(payload, '$.merchant_id') AS merchant_id,
       CAST(get_json_string(payload, '$.valid_from') AS DATETIME) AS valid_from,
       CAST(get_json_string(payload, '$.valid_to') AS DATETIME) AS valid_to,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'promotion.coupon_template.state_changed' AND schema_version = 1
  AND source_system = 'cloudmold-promotion';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_coupon_entitlement_event AS
SELECT event_id, tenant_id, aggregate_id AS entitlement_id, aggregate_version,
       occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.entitlement_code') AS entitlement_code,
       get_json_string(payload, '$.template_id') AS template_id,
       get_json_string(payload, '$.campaign_id') AS campaign_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.order_ref') AS order_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.face_amount_minor') AS BIGINT) AS face_amount_minor,
       CAST(get_json_string(payload, '$.threshold_minor') AS BIGINT) AS threshold_minor,
       get_json_string(payload, '$.currency_code') AS currency_code,
       get_json_string(payload, '$.operation') AS operation,
       get_json_string(payload, '$.ledger_entry_id') AS ledger_entry_id,
       get_json_string(payload, '$.reason') AS reason
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'promotion.coupon_entitlement.state_changed' AND schema_version = 1
  AND source_system = 'cloudmold-promotion';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_advertising_placement_event AS
SELECT event_id, tenant_id, aggregate_id AS placement_id, aggregate_version,
       occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.placement_code') AS placement_code,
       get_json_string(payload, '$.campaign_id') AS campaign_id,
       get_json_string(payload, '$.name') AS placement_name,
       get_json_string(payload, '$.channel_code') AS channel_code,
       get_json_string(payload, '$.page_code') AS page_code,
       get_json_string(payload, '$.slot_code') AS slot_code,
       get_json_string(payload, '$.creative_ref') AS creative_ref,
       CAST(get_json_string(payload, '$.valid_from') AS DATETIME) AS valid_from,
       CAST(get_json_string(payload, '$.valid_to') AS DATETIME) AS valid_to,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'promotion.advertising_placement.state_changed' AND schema_version = 1
  AND source_system = 'cloudmold-promotion';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_advertising_interaction_event AS
SELECT event_id, tenant_id, aggregate_id AS interaction_id, aggregate_version,
       occurred_at AS event_occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.interaction_type') AS interaction_type,
       get_json_string(payload, '$.deduplication_key') AS deduplication_key,
       get_json_string(payload, '$.placement_id') AS placement_id,
       get_json_string(payload, '$.campaign_id') AS campaign_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.session_id') AS session_id,
       get_json_string(payload, '$.source_interaction_id') AS source_interaction_id,
       get_json_string(payload, '$.order_ref') AS order_ref,
       CAST(get_json_string(payload, '$.attribution_amount_minor') AS BIGINT) AS attribution_amount_minor,
       get_json_string(payload, '$.currency_code') AS currency_code,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'promotion.advertising_interaction.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-promotion';
