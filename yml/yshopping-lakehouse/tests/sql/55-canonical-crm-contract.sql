SELECT 'crm_customer_current_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, customer_id
    FROM yshopping_dim.dim_canonical_crm_customer_current
    GROUP BY tenant_id, customer_id
    HAVING COUNT(*) <> 1
) duplicate_rows;

SELECT 'crm_customer_owner_event_orphan_customer' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_crm_customer_owner_event owner_event
LEFT JOIN yshopping_dim.dim_canonical_crm_customer_current customer
  ON customer.tenant_id = owner_event.tenant_id AND customer.customer_id = owner_event.customer_id
WHERE customer.customer_id IS NULL;

SELECT 'crm_lead_converted_customer_missing' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_crm_lead_current lead
LEFT JOIN yshopping_dim.dim_canonical_crm_customer_current customer
  ON customer.tenant_id = lead.tenant_id AND customer.customer_id = lead.converted_customer_id
WHERE lead.current_status = 'CONVERTED'
  AND (lead.converted_customer_id IS NULL OR customer.customer_id IS NULL);

SELECT 'crm_contact_customer_missing' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_crm_contact_current contact
LEFT JOIN yshopping_dim.dim_canonical_crm_customer_current customer
  ON customer.tenant_id = contact.tenant_id AND customer.customer_id = contact.customer_id
WHERE customer.customer_id IS NULL;

SELECT 'crm_opportunity_customer_missing' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_crm_opportunity_current opportunity
LEFT JOIN yshopping_dim.dim_canonical_crm_customer_current customer
  ON customer.tenant_id = opportunity.tenant_id AND customer.customer_id = opportunity.customer_id
WHERE customer.customer_id IS NULL;

SELECT 'crm_follow_up_entity_missing' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_crm_follow_up_event follow_up
LEFT JOIN yshopping_dim.dim_canonical_crm_customer_current customer
  ON customer.tenant_id = follow_up.tenant_id AND customer.customer_id = follow_up.biz_id
  AND follow_up.biz_type = 'CUSTOMER'
LEFT JOIN yshopping_dim.dim_canonical_crm_lead_current lead
  ON lead.tenant_id = follow_up.tenant_id AND lead.lead_id = follow_up.biz_id
  AND follow_up.biz_type = 'LEAD'
LEFT JOIN yshopping_dim.dim_canonical_crm_contact_current contact
  ON contact.tenant_id = follow_up.tenant_id AND contact.contact_id = follow_up.biz_id
  AND follow_up.biz_type = 'CONTACT'
LEFT JOIN yshopping_dim.dim_canonical_crm_opportunity_current opportunity
  ON opportunity.tenant_id = follow_up.tenant_id AND opportunity.opportunity_id = follow_up.biz_id
  AND follow_up.biz_type = 'OPPORTUNITY'
WHERE (follow_up.biz_type = 'CUSTOMER' AND customer.customer_id IS NULL)
   OR (follow_up.biz_type = 'LEAD' AND lead.lead_id IS NULL)
   OR (follow_up.biz_type = 'CONTACT' AND contact.contact_id IS NULL)
   OR (follow_up.biz_type = 'OPPORTUNITY' AND opportunity.opportunity_id IS NULL);

SELECT 'crm_follow_up_customer_context_missing' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_crm_follow_up_event
WHERE biz_type IN ('CUSTOMER', 'CONTACT', 'OPPORTUNITY')
  AND customer_id IS NULL;

SELECT 'crm_follow_up_raw_locator_leak' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_crm_follow_up_event
WHERE LOWER(content_token) LIKE 'http%' OR content_token LIKE '%@%' OR content_token LIKE '% %';

SELECT 'crm_customer_profile_negative_pipeline' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_crm_customer_profile_current
WHERE open_pipeline_amount_minor < 0
   OR won_amount_minor < 0
   OR weighted_pipeline_amount_minor < 0
   OR open_opportunity_count < 0
   OR won_opportunity_count < 0
   OR lost_opportunity_count < 0;

SELECT 'crm_funnel_invalid_counts' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_crm_funnel_current
WHERE new_lead_count < 0
   OR contacted_lead_count < 0
   OR qualified_lead_count < 0
   OR converted_lead_count < 0
   OR open_opportunity_count < 0
   OR won_opportunity_count < 0
   OR lost_opportunity_count < 0
   OR open_pipeline_amount_minor < 0
   OR weighted_pipeline_amount_minor < 0
   OR won_amount_minor < 0;

SELECT 'crm_owner_performance_rate_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_crm_owner_performance_current
WHERE (win_rate_basis_points IS NOT NULL AND (win_rate_basis_points < 0 OR win_rate_basis_points > 10000))
   OR follow_up_count < customer_follow_up_count
   OR follow_up_count < contact_follow_up_count
   OR follow_up_count < opportunity_follow_up_count;

SELECT 'crm_readiness_semantics_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_crm_readiness
WHERE model_semantics <> 'CANONICAL_CRM_PII_SAFE_PIPELINE_FIRST_SLICE';
