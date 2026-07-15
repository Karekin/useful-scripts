CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_favorite_current AS
SELECT event_id, tenant_id, favorite_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key, principal_id, canonical_spu_id, previous_status, current_status,
       behavior_type, source_system_ref, source_type, source_id, run_id, favorite_event_count
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, favorite_id) AS favorite_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, favorite_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_favorite_status_event event
) ranked WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_notification_campaign_current AS
SELECT event_id, tenant_id, campaign_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key, campaign_code, channel, campaign_name, previous_status,
       current_status, source_system_ref, source_type, source_id, run_id, campaign_event_count
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, campaign_id) AS campaign_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, campaign_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_notification_campaign_event event
) ranked WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_notification_delivery_current AS
SELECT event_id, tenant_id, delivery_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key, delivery_key, campaign_id, principal_id, channel,
       previous_status, current_status, provider_reference, run_id, delivery_event_count
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, delivery_id) AS delivery_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, delivery_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_notification_delivery_event event
) ranked WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_community_content_current AS
SELECT event_id, tenant_id, content_id, aggregate_version, occurred_at, recorded_at, correlation_id,
       causation_id, idempotency_key, author_principal_id, content_type, body_ref,
       previous_status, current_status, source_system_ref, source_type, source_id, run_id,
       content_event_count
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, content_id) AS content_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, content_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_community_content_event event
) ranked WHERE row_num = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_community_moderation_current AS
SELECT event_id, tenant_id, moderation_case_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key, content_id, reporter_principal_id,
       moderator_principal_id, reason_code, previous_status, current_status, decision,
       decision_reason_code, run_id,
       moderation_event_count
FROM (
    SELECT event.*, COUNT(*) OVER (PARTITION BY tenant_id, moderation_case_id) AS moderation_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, moderation_case_id
                              ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS row_num
    FROM yshopping_dwd.dwd_canonical_community_moderation_event event
) ranked WHERE row_num = 1;
