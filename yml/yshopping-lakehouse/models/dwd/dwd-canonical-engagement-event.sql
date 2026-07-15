-- Canonical engagement first slice: favorite behavior, notification delivery and community moderation.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_favorite_status_event AS
SELECT event_id, tenant_id, aggregate_id AS favorite_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.canonical_spu_id') AS canonical_spu_id,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.behavior_type') AS behavior_type,
       get_json_string(payload, '$.source_system') AS source_system_ref,
       get_json_string(payload, '$.source_type') AS source_type,
       get_json_string(payload, '$.source_id') AS source_id,
       get_json_string(payload, '$.run_id') AS run_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.favorite.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-engagement';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_favorite_behavior_event AS
SELECT event_id, tenant_id, aggregate_id AS favorite_aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.behavior_id') AS behavior_id,
       get_json_string(payload, '$.favorite_id') AS favorite_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.canonical_spu_id') AS canonical_spu_id,
       get_json_string(payload, '$.behavior_type') AS behavior_type,
       get_json_string(payload, '$.favorite_status') AS favorite_status,
       get_json_string(payload, '$.run_id') AS run_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.favorite.behavior_recorded' AND schema_version = 1
  AND source_system = 'cloudmold-engagement';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_notification_campaign_event AS
SELECT event_id, tenant_id, aggregate_id AS campaign_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.campaign_code') AS campaign_code,
       get_json_string(payload, '$.channel') AS channel,
       get_json_string(payload, '$.campaign_name') AS campaign_name,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.source_system') AS source_system_ref,
       get_json_string(payload, '$.source_type') AS source_type,
       get_json_string(payload, '$.source_id') AS source_id,
       get_json_string(payload, '$.run_id') AS run_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.notification.campaign_status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-engagement';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_notification_delivery_event AS
SELECT event_id, tenant_id, aggregate_id AS delivery_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.delivery_key') AS delivery_key,
       get_json_string(payload, '$.campaign_id') AS campaign_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.channel') AS channel,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.provider_reference') AS provider_reference,
       get_json_string(payload, '$.run_id') AS run_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.notification.delivery_status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-engagement';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_notification_attempt_event AS
SELECT event_id, tenant_id, aggregate_id AS delivery_aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.attempt_id') AS attempt_id,
       get_json_string(payload, '$.delivery_id') AS delivery_id,
       get_json_string(payload, '$.campaign_id') AS campaign_id,
       CAST(get_json_string(payload, '$.attempt_no') AS INT) AS attempt_no,
       get_json_string(payload, '$.outcome') AS outcome,
       get_json_string(payload, '$.provider_reference') AS provider_reference,
       get_json_string(payload, '$.provider_code') AS provider_code,
       get_json_string(payload, '$.delivery_status') AS delivery_status,
       get_json_string(payload, '$.run_id') AS run_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.notification.delivery_attempt_recorded' AND schema_version = 1
  AND source_system = 'cloudmold-engagement';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_notification_receipt_event AS
SELECT event_id, tenant_id, aggregate_id AS delivery_aggregate_id, aggregate_version, occurred_at AS event_occurred_at,
       recorded_at, correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.receipt_id') AS receipt_id,
       get_json_string(payload, '$.delivery_id') AS delivery_id,
       get_json_string(payload, '$.campaign_id') AS campaign_id,
       get_json_string(payload, '$.external_receipt_id') AS external_receipt_id,
       get_json_string(payload, '$.receipt_status') AS receipt_status,
       get_json_string(payload, '$.delivery_status') AS delivery_status,
       CAST(get_json_string(payload, '$.received_at') AS DATETIME) AS received_at,
       get_json_string(payload, '$.run_id') AS run_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.notification.delivery_receipt_recorded' AND schema_version = 1
  AND source_system = 'cloudmold-engagement';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_community_content_event AS
SELECT event_id, tenant_id, aggregate_id AS content_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.author_principal_id') AS author_principal_id,
       get_json_string(payload, '$.content_type') AS content_type,
       get_json_string(payload, '$.body_ref') AS body_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.source_system') AS source_system_ref,
       get_json_string(payload, '$.source_type') AS source_type,
       get_json_string(payload, '$.source_id') AS source_id,
       get_json_string(payload, '$.run_id') AS run_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.community.content_status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-engagement';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_community_interaction_event AS
SELECT event_id, tenant_id, aggregate_id AS interaction_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.actor_principal_id') AS actor_principal_id,
       get_json_string(payload, '$.interaction_type') AS interaction_type,
       get_json_string(payload, '$.target_type') AS target_type,
       get_json_string(payload, '$.target_id') AS target_id,
       get_json_string(payload, '$.payload_ref') AS payload_ref,
       get_json_string(payload, '$.run_id') AS run_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.community.interaction_recorded' AND schema_version = 1
  AND source_system = 'cloudmold-engagement';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_community_moderation_event AS
SELECT event_id, tenant_id, aggregate_id AS moderation_case_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.content_id') AS content_id,
       get_json_string(payload, '$.reporter_principal_id') AS reporter_principal_id,
       get_json_string(payload, '$.moderator_principal_id') AS moderator_principal_id,
       get_json_string(payload, '$.reason_code') AS reason_code,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.decision') AS decision,
       get_json_string(payload, '$.decision_reason_code') AS decision_reason_code,
       get_json_string(payload, '$.run_id') AS run_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'engagement.community.moderation_status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-engagement';
