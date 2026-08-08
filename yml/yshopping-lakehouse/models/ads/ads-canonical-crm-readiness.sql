CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_crm_readiness AS
SELECT profile.tenant_id,
       COUNT(*) AS customer_profile_count,
       SUM(CASE WHEN profile.current_status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_customer_count,
       COALESCE(MAX(funnel.owner_count), 0) AS funnel_owner_count,
       COALESCE(MAX(perf.owner_count), 0) AS performance_owner_count,
       COALESCE(MAX(lead.lead_count), 0) AS lead_count,
       COALESCE(MAX(lead.converted_lead_count), 0) AS converted_lead_count,
       SUM(profile.contact_count) AS contact_count,
       SUM(profile.open_opportunity_count) AS open_opportunity_count,
       SUM(profile.won_opportunity_count) AS won_opportunity_count,
       SUM(profile.open_pipeline_amount_minor) AS open_pipeline_amount_minor,
       SUM(profile.won_amount_minor) AS won_amount_minor,
       SUM(profile.follow_up_count) AS follow_up_count,
       SUM(profile.overdue_follow_up_flag) AS overdue_customer_count,
       SUM(CASE WHEN profile.current_owner_principal_id IS NULL THEN 1 ELSE 0 END)
           AS missing_owner_customer_count,
       COALESCE(MAX(owner_move.transfer_count), 0) AS customer_transfer_count,
       CASE
           WHEN SUM(CASE WHEN profile.current_owner_principal_id IS NULL THEN 1 ELSE 0 END) > 0
             THEN 'OWNER_MISSING'
           WHEN SUM(profile.open_pipeline_amount_minor) < 0 OR SUM(profile.won_amount_minor) < 0
             THEN 'PIPELINE_AMOUNT_INVALID'
           ELSE 'READY'
       END AS readiness_status,
       MAX(profile.data_freshness_at) AS data_freshness_at,
       'CANONICAL_CRM_PII_SAFE_PIPELINE_FIRST_SLICE' AS model_semantics
FROM yshopping_dws.dws_canonical_crm_customer_profile_current profile
LEFT JOIN (
    SELECT tenant_id, COUNT(*) AS lead_count,
           SUM(CASE WHEN current_status = 'CONVERTED' THEN 1 ELSE 0 END) AS converted_lead_count
    FROM yshopping_dim.dim_canonical_crm_lead_current
    GROUP BY tenant_id
) lead ON lead.tenant_id = profile.tenant_id
LEFT JOIN (
    SELECT tenant_id, COUNT(*) AS owner_count
    FROM yshopping_dws.dws_canonical_crm_funnel_current
    GROUP BY tenant_id
) funnel ON funnel.tenant_id = profile.tenant_id
LEFT JOIN (
    SELECT tenant_id, COUNT(*) AS owner_count
    FROM yshopping_dws.dws_canonical_crm_owner_performance_current
    GROUP BY tenant_id
) perf ON perf.tenant_id = profile.tenant_id
LEFT JOIN (
    SELECT tenant_id, COUNT(*) AS transfer_count
    FROM yshopping_dwd.dwd_canonical_crm_customer_owner_event
    GROUP BY tenant_id
) owner_move ON owner_move.tenant_id = profile.tenant_id
GROUP BY profile.tenant_id;
