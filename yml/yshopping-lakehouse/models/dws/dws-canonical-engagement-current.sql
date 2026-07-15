CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_collect_current AS
SELECT favorite.tenant_id, favorite.principal_id, favorite.canonical_spu_id, favorite.current_status,
       favorite.favorite_id, favorite.favorite_event_count,
       COUNT(behavior.behavior_id) AS behavior_count,
       MAX(COALESCE(behavior.recorded_at, favorite.recorded_at)) AS data_freshness_at
FROM yshopping_dim.dim_canonical_favorite_current favorite
LEFT JOIN yshopping_dwd.dwd_canonical_favorite_behavior_event behavior
  ON behavior.tenant_id = favorite.tenant_id AND behavior.favorite_id = favorite.favorite_id
GROUP BY favorite.tenant_id, favorite.principal_id, favorite.canonical_spu_id,
         favorite.current_status, favorite.favorite_id, favorite.favorite_event_count;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_push_current AS
SELECT delivery.tenant_id, delivery.campaign_id, campaign.campaign_code, delivery.channel,
       delivery.current_status AS delivery_status,
       COUNT(*) AS delivery_count,
       SUM(CASE WHEN delivery.current_status IN ('DELIVERED','OPENED','CLICKED') THEN 1 ELSE 0 END)
           AS delivered_count,
       SUM(CASE WHEN delivery.current_status = 'FAILED' THEN 1 ELSE 0 END) AS failed_count,
       SUM(COALESCE(attempt.attempt_count, 0)) AS attempt_count,
       SUM(COALESCE(receipt.receipt_count, 0)) AS receipt_count,
       MAX(GREATEST(delivery.recorded_at,
                    COALESCE(attempt.recorded_at, delivery.recorded_at),
                    COALESCE(receipt.recorded_at, delivery.recorded_at))) AS data_freshness_at
FROM yshopping_dim.dim_canonical_notification_delivery_current delivery
LEFT JOIN yshopping_dim.dim_canonical_notification_campaign_current campaign
  ON campaign.tenant_id = delivery.tenant_id AND campaign.campaign_id = delivery.campaign_id
LEFT JOIN (
    SELECT tenant_id, delivery_id, COUNT(*) AS attempt_count, MAX(recorded_at) AS recorded_at
    FROM yshopping_dwd.dwd_canonical_notification_attempt_event GROUP BY tenant_id, delivery_id
) attempt ON attempt.tenant_id = delivery.tenant_id AND attempt.delivery_id = delivery.delivery_id
LEFT JOIN (
    SELECT tenant_id, delivery_id, COUNT(*) AS receipt_count, MAX(recorded_at) AS recorded_at
    FROM yshopping_dwd.dwd_canonical_notification_receipt_event GROUP BY tenant_id, delivery_id
) receipt ON receipt.tenant_id = delivery.tenant_id AND receipt.delivery_id = delivery.delivery_id
GROUP BY delivery.tenant_id, delivery.campaign_id, campaign.campaign_code,
         delivery.channel, delivery.current_status;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_community_current AS
SELECT content.tenant_id, content.content_type, content.current_status,
       COUNT(*) AS content_count,
       SUM(COALESCE(interaction.interaction_count, 0)) AS interaction_count,
       SUM(COALESCE(moderation.moderation_case_count, 0)) AS moderation_case_count,
       SUM(COALESCE(moderation.open_moderation_case_count, 0)) AS open_moderation_case_count,
       MAX(GREATEST(content.recorded_at,
                    COALESCE(interaction.recorded_at, content.recorded_at),
                    COALESCE(moderation.recorded_at, content.recorded_at))) AS data_freshness_at
FROM yshopping_dim.dim_canonical_community_content_current content
LEFT JOIN (
    SELECT tenant_id, target_id AS content_id, COUNT(*) AS interaction_count, MAX(recorded_at) AS recorded_at
    FROM yshopping_dwd.dwd_canonical_community_interaction_event
    WHERE target_type = 'CONTENT' GROUP BY tenant_id, target_id
) interaction ON interaction.tenant_id = content.tenant_id AND interaction.content_id = content.content_id
LEFT JOIN (
    SELECT tenant_id, content_id, COUNT(*) AS moderation_case_count,
           SUM(CASE WHEN current_status = 'OPEN' THEN 1 ELSE 0 END) AS open_moderation_case_count,
           MAX(recorded_at) AS recorded_at
    FROM yshopping_dim.dim_canonical_community_moderation_current GROUP BY tenant_id, content_id
) moderation ON moderation.tenant_id = content.tenant_id AND moderation.content_id = content.content_id
GROUP BY content.tenant_id, content.content_type, content.current_status;
