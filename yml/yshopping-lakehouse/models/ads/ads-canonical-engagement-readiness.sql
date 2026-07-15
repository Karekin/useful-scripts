CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_collect_readiness AS
SELECT tenant_id,
       COUNT(*) AS favorite_count,
       SUM(CASE WHEN current_status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_favorite_count,
       SUM(behavior_count) AS behavior_count,
       SUM(CASE WHEN behavior_count = 0 THEN 1 ELSE 0 END) AS favorite_without_behavior_count,
       CASE WHEN SUM(CASE WHEN behavior_count = 0 THEN 1 ELSE 0 END) = 0
            THEN 'READY' ELSE 'MISSING_BEHAVIOR' END AS readiness_status,
       MAX(data_freshness_at) AS data_freshness_at,
       'CANONICAL_FAVORITE_FIRST_SLICE' AS model_semantics
FROM yshopping_dws.dws_canonical_collect_current GROUP BY tenant_id;

CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_push_readiness AS
SELECT tenant_id,
       SUM(delivery_count) AS delivery_count,
       SUM(delivered_count) AS delivered_count,
       SUM(failed_count) AS failed_count,
       SUM(attempt_count) AS attempt_count,
       SUM(receipt_count) AS receipt_count,
       SUM(CASE WHEN delivery_status <> 'QUEUED' AND attempt_count = 0 THEN delivery_count ELSE 0 END)
           AS progressed_without_attempt_count,
       CASE WHEN SUM(CASE WHEN delivery_status <> 'QUEUED' AND attempt_count = 0 THEN delivery_count ELSE 0 END) = 0
            THEN 'READY' ELSE 'MISSING_ATTEMPT' END AS readiness_status,
       MAX(data_freshness_at) AS data_freshness_at,
       'CANONICAL_NOTIFICATION_DELIVERY_FIRST_SLICE' AS model_semantics
FROM yshopping_dws.dws_canonical_push_current GROUP BY tenant_id;

CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_community_readiness AS
SELECT tenant_id,
       SUM(content_count) AS content_count,
       SUM(interaction_count) AS interaction_count,
       SUM(moderation_case_count) AS moderation_case_count,
       SUM(open_moderation_case_count) AS open_moderation_case_count,
       CASE WHEN SUM(open_moderation_case_count) = 0 THEN 'READY' ELSE 'MODERATION_PENDING' END
           AS readiness_status,
       MAX(data_freshness_at) AS data_freshness_at,
       'CANONICAL_COMMUNITY_MODERATION_FIRST_SLICE' AS model_semantics
FROM yshopping_dws.dws_canonical_community_current GROUP BY tenant_id;
