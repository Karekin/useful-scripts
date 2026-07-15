CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_activity_readiness AS
SELECT tenant_id,
       SUM(campaign_count) AS campaign_count,
       SUM(active_campaign_count) AS active_campaign_count,
       SUM(invalid_time_window_count) AS invalid_time_window_count,
       CASE WHEN SUM(invalid_time_window_count) = 0 THEN 'READY' ELSE 'INVALID_TIME_WINDOW' END AS readiness_status,
       MAX(data_freshness_at) AS data_freshness_at,
       'CANONICAL_CAMPAIGN_FIRST_SLICE' AS model_semantics
FROM yshopping_dws.dws_canonical_activity_current GROUP BY tenant_id;

CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_coupon_readiness AS
SELECT tenant_id,
       COUNT(DISTINCT template_id) AS template_count,
       SUM(entitlement_count) AS entitlement_count,
       SUM(available_count) AS available_count,
       SUM(used_count) AS used_count,
       SUM(returned_count) AS returned_count,
       SUM(used_face_amount_minor) AS used_face_amount_minor,
       SUM(CASE WHEN template_code IS NULL THEN entitlement_count ELSE 0 END) AS orphan_entitlement_count,
       CASE WHEN SUM(CASE WHEN template_code IS NULL THEN entitlement_count ELSE 0 END) = 0
            THEN 'READY' ELSE 'ORPHAN_ENTITLEMENT' END AS readiness_status,
       MAX(data_freshness_at) AS data_freshness_at,
       'CANONICAL_COUPON_RIGHTS_FIRST_SLICE' AS model_semantics
FROM yshopping_dws.dws_canonical_coupon_current GROUP BY tenant_id;

CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_advertising_readiness AS
SELECT tenant_id,
       COUNT(*) AS placement_count,
       SUM(interaction_count) AS interaction_count,
       SUM(impression_count) AS impression_count,
       SUM(click_count) AS click_count,
       SUM(attribution_count) AS attribution_count,
       SUM(attribution_amount_minor) AS attribution_amount_minor,
       SUM(CASE WHEN click_count > impression_count OR attribution_count > click_count THEN 1 ELSE 0 END)
           AS lineage_anomaly_placement_count,
       CASE WHEN SUM(CASE WHEN click_count > impression_count OR attribution_count > click_count THEN 1 ELSE 0 END) = 0
            THEN 'READY' ELSE 'LINEAGE_ANOMALY' END AS readiness_status,
       MAX(data_freshness_at) AS data_freshness_at,
       'CANONICAL_ADVERTISING_LINEAGE_FIRST_SLICE' AS model_semantics
FROM yshopping_dws.dws_canonical_advertising_current GROUP BY tenant_id;
