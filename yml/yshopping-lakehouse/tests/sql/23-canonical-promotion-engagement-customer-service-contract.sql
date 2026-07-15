-- Canonical promotion, engagement and customer-service first-slice DQC.
SELECT 'new_domain_event_id_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, event_id
    FROM yshopping_dwd.dwd_domain_event
    WHERE source_system IN ('cloudmold-promotion','cloudmold-engagement','cloudmold-customer-service')
    GROUP BY tenant_id, event_id HAVING COUNT(*) <> 1
) duplicate_events;

SELECT 'new_domain_aggregate_version_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, event_type, aggregate_id, aggregate_version, event_sequence
    FROM yshopping_dwd.dwd_domain_event
    WHERE source_system IN ('cloudmold-promotion','cloudmold-engagement','cloudmold-customer-service')
    GROUP BY tenant_id, event_type, aggregate_id, aggregate_version, event_sequence HAVING COUNT(*) <> 1
) duplicate_versions;

SELECT 'promotion_campaign_invalid_time_window' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_promotion_campaign_current
WHERE starts_at >= ends_at;

SELECT 'coupon_entitlement_orphan_template' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_coupon_entitlement_current entitlement
LEFT JOIN yshopping_dim.dim_canonical_coupon_template_current template
  ON template.tenant_id = entitlement.tenant_id AND template.template_id = entitlement.template_id
WHERE template.template_id IS NULL;

SELECT 'coupon_entitlement_missing_ledger_entry' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_coupon_entitlement_event
WHERE ledger_entry_id IS NULL OR ledger_entry_id = '';

SELECT 'coupon_entitlement_invalid_amount_snapshot' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_coupon_entitlement_current
WHERE face_amount_minor < 0 OR threshold_minor < 0 OR currency_code IS NULL;

SELECT 'advertising_click_without_impression' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_advertising_interaction_event child
LEFT JOIN yshopping_dwd.dwd_canonical_advertising_interaction_event parent
  ON parent.tenant_id = child.tenant_id AND parent.interaction_id = child.source_interaction_id
WHERE child.interaction_type = 'CLICK'
  AND (parent.interaction_id IS NULL OR parent.interaction_type <> 'IMPRESSION'
       OR parent.placement_id <> child.placement_id);

SELECT 'advertising_attribution_without_click' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_advertising_interaction_event child
LEFT JOIN yshopping_dwd.dwd_canonical_advertising_interaction_event parent
  ON parent.tenant_id = child.tenant_id AND parent.interaction_id = child.source_interaction_id
WHERE child.interaction_type = 'ATTRIBUTION'
  AND (parent.interaction_id IS NULL OR parent.interaction_type <> 'CLICK'
       OR parent.placement_id <> child.placement_id OR child.order_ref IS NULL
       OR child.attribution_amount_minor < 0 OR child.currency_code IS NULL);

SELECT 'favorite_without_behavior_event' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_collect_current
WHERE behavior_count = 0;

SELECT 'notification_delivery_orphan_campaign' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_notification_delivery_current delivery
LEFT JOIN yshopping_dim.dim_canonical_notification_campaign_current campaign
  ON campaign.tenant_id = delivery.tenant_id AND campaign.campaign_id = delivery.campaign_id
WHERE campaign.campaign_id IS NULL;

SELECT 'notification_progressed_without_attempt' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_push_readiness
WHERE progressed_without_attempt_count <> 0;

SELECT 'community_interaction_orphan_content' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_community_interaction_event interaction
LEFT JOIN yshopping_dim.dim_canonical_community_content_current content
  ON content.tenant_id = interaction.tenant_id AND content.content_id = interaction.target_id
WHERE interaction.target_type = 'CONTENT' AND content.content_id IS NULL;

SELECT 'community_moderation_orphan_content' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_community_moderation_current moderation
LEFT JOIN yshopping_dim.dim_canonical_community_content_current content
  ON content.tenant_id = moderation.tenant_id AND content.content_id = moderation.content_id
WHERE content.content_id IS NULL;

SELECT 'customer_service_message_orphan_ticket' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_customer_service_message_event message
LEFT JOIN yshopping_dim.dim_canonical_customer_service_ticket_current ticket
  ON ticket.tenant_id = message.tenant_id AND ticket.ticket_id = message.ticket_id
WHERE ticket.ticket_id IS NULL;

SELECT 'customer_service_attachment_orphan_message' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_customer_service_attachment_event attachment
LEFT JOIN yshopping_dwd.dwd_canonical_customer_service_message_event message
  ON message.tenant_id = attachment.tenant_id AND message.message_id = attachment.message_id
WHERE message.message_id IS NULL OR message.ticket_id <> attachment.ticket_id;

SELECT 'customer_service_review_orphan_ticket' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_customer_service_quality_review_event review
LEFT JOIN yshopping_dim.dim_canonical_customer_service_ticket_current ticket
  ON ticket.tenant_id = review.tenant_id AND ticket.ticket_id = review.ticket_id
WHERE ticket.ticket_id IS NULL OR review.score_basis_points < 0 OR review.score_basis_points > 10000;

SELECT 'customer_service_claim_orphan_ticket' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_customer_service_claim_current claim
LEFT JOIN yshopping_dim.dim_canonical_customer_service_ticket_current ticket
  ON ticket.tenant_id = claim.tenant_id AND ticket.ticket_id = claim.ticket_id
WHERE ticket.ticket_id IS NULL;

SELECT 'customer_service_claim_amount_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_customer_service_claim_current
WHERE requested_amount_minor < 0
   OR COALESCE(approved_amount_minor, 0) > requested_amount_minor
   OR COALESCE(paid_amount_minor, 0) > COALESCE(approved_amount_minor, 0)
   OR (current_status = 'PAID' AND compensation_entry_id IS NULL);

SELECT 'customer_service_raw_locator_leak' AS check_name,
       (SELECT COUNT(*) FROM yshopping_dwd.dwd_canonical_customer_service_message_event
         WHERE LOWER(content_token) LIKE 'http%' OR content_token LIKE '%@%' OR content_token LIKE '% %')
     + (SELECT COUNT(*) FROM yshopping_dwd.dwd_canonical_customer_service_attachment_event
         WHERE LOWER(object_token) LIKE 'http%' OR object_token LIKE '%@%' OR object_token LIKE '% %') AS violations;

SELECT 'customer_service_attachment_not_clean' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_customer_service_attachment_event
WHERE malware_scan_status <> 'CLEAN';

SELECT 'new_domain_readiness_semantics_invalid' AS check_name,
       (SELECT COUNT(*) FROM yshopping_ads.ads_canonical_activity_readiness
         WHERE model_semantics <> 'CANONICAL_CAMPAIGN_FIRST_SLICE')
     + (SELECT COUNT(*) FROM yshopping_ads.ads_canonical_coupon_readiness
         WHERE model_semantics <> 'CANONICAL_COUPON_RIGHTS_FIRST_SLICE')
     + (SELECT COUNT(*) FROM yshopping_ads.ads_canonical_advertising_readiness
         WHERE model_semantics <> 'CANONICAL_ADVERTISING_LINEAGE_FIRST_SLICE')
     + (SELECT COUNT(*) FROM yshopping_ads.ads_canonical_collect_readiness
         WHERE model_semantics <> 'CANONICAL_FAVORITE_FIRST_SLICE')
     + (SELECT COUNT(*) FROM yshopping_ads.ads_canonical_push_readiness
         WHERE model_semantics <> 'CANONICAL_NOTIFICATION_DELIVERY_FIRST_SLICE')
     + (SELECT COUNT(*) FROM yshopping_ads.ads_canonical_community_readiness
         WHERE model_semantics <> 'CANONICAL_COMMUNITY_MODERATION_FIRST_SLICE')
     + (SELECT COUNT(*) FROM yshopping_ads.ads_canonical_customer_service_readiness
         WHERE model_semantics <> 'CANONICAL_CUSTOMER_SERVICE_PII_SAFE_FIRST_SLICE') AS violations;
