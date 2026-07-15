CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_activity_current AS
SELECT tenant_id, campaign_kind, current_status,
       COUNT(*) AS campaign_count,
       SUM(CASE WHEN current_status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_campaign_count,
       SUM(CASE WHEN starts_at IS NOT NULL AND ends_at IS NOT NULL AND starts_at >= ends_at THEN 1 ELSE 0 END)
           AS invalid_time_window_count,
       MAX(recorded_at) AS data_freshness_at
FROM yshopping_dim.dim_canonical_promotion_campaign_current
GROUP BY tenant_id, campaign_kind, current_status;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_coupon_current AS
SELECT entitlement.tenant_id, entitlement.campaign_id, entitlement.template_id,
       template.template_code, template.benefit_type, template.current_status AS template_status,
       COUNT(*) AS entitlement_count,
       SUM(CASE WHEN entitlement.current_status = 'AVAILABLE' THEN 1 ELSE 0 END) AS available_count,
       SUM(CASE WHEN entitlement.current_status = 'USED' THEN 1 ELSE 0 END) AS used_count,
       SUM(CASE WHEN entitlement.current_status = 'RETURNED' THEN 1 ELSE 0 END) AS returned_count,
       SUM(CASE WHEN entitlement.current_status = 'USED' THEN entitlement.face_amount_minor ELSE 0 END)
           AS used_face_amount_minor,
       MAX(entitlement.recorded_at) AS data_freshness_at
FROM yshopping_dim.dim_canonical_coupon_entitlement_current entitlement
LEFT JOIN yshopping_dim.dim_canonical_coupon_template_current template
  ON template.tenant_id = entitlement.tenant_id AND template.template_id = entitlement.template_id
GROUP BY entitlement.tenant_id, entitlement.campaign_id, entitlement.template_id,
         template.template_code, template.benefit_type, template.current_status;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_advertising_current AS
SELECT placement.tenant_id, placement.campaign_id, placement.placement_id, placement.placement_code,
       placement.channel_code, placement.page_code, placement.slot_code, placement.current_status,
       COUNT(interaction.interaction_id) AS interaction_count,
       SUM(CASE WHEN interaction.interaction_type = 'IMPRESSION' THEN 1 ELSE 0 END) AS impression_count,
       SUM(CASE WHEN interaction.interaction_type = 'CLICK' THEN 1 ELSE 0 END) AS click_count,
       SUM(CASE WHEN interaction.interaction_type = 'ATTRIBUTION' THEN 1 ELSE 0 END) AS attribution_count,
       SUM(CASE WHEN interaction.interaction_type = 'ATTRIBUTION'
                THEN COALESCE(interaction.attribution_amount_minor, 0) ELSE 0 END) AS attribution_amount_minor,
       MAX(COALESCE(interaction.recorded_at, placement.recorded_at)) AS data_freshness_at
FROM yshopping_dim.dim_canonical_advertising_placement_current placement
LEFT JOIN yshopping_dwd.dwd_canonical_advertising_interaction_event interaction
  ON interaction.tenant_id = placement.tenant_id AND interaction.placement_id = placement.placement_id
GROUP BY placement.tenant_id, placement.campaign_id, placement.placement_id, placement.placement_code,
         placement.channel_code, placement.page_code, placement.slot_code, placement.current_status;
