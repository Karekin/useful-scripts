SELECT 'advertising_ledger_invalid_money_or_currency' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_advertising_ledger_event
WHERE amount_minor <= 0
   OR currency_code <> 'CNY'
   OR entry_type NOT IN ('SPEND', 'REVENUE')
   OR (entry_type = 'SPEND' AND revenue_type IS NOT NULL)
   OR (entry_type = 'REVENUE' AND revenue_type NOT IN (
       'ADVERTISING', 'COMMISSION', 'FULFILLMENT_SERVICE', 'PAYMENT_SERVICE', 'OTHER_PLATFORM_REVENUE'
   ));

SELECT 'advertising_revenue_without_attribution_link' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_advertising_ledger_event ledger
LEFT JOIN yshopping_dwd.dwd_canonical_advertising_interaction_event interaction
  ON interaction.tenant_id = ledger.tenant_id
 AND interaction.interaction_id = ledger.source_interaction_id
WHERE ledger.entry_type = 'REVENUE'
  AND ledger.source_interaction_id IS NOT NULL
  AND (interaction.interaction_id IS NULL
       OR interaction.interaction_type <> 'ATTRIBUTION'
       OR interaction.campaign_id <> ledger.campaign_id
       OR NOT (interaction.order_ref <=> ledger.order_ref));

SELECT 'promotion_experiment_missing_baseline_or_cost' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_promotion_experiment_result_current
WHERE baseline_contribution_profit_minor < 0
   OR treatment_contribution_profit_minor < 0
   OR incremental_contribution_profit_minor
      <> treatment_contribution_profit_minor - baseline_contribution_profit_minor
   OR promotion_cost_minor <= 0
   OR eligible_population_count <= 0
   OR treatment_population_count <= 0
   OR control_population_count <= 0
   OR treatment_population_count + control_population_count > eligible_population_count
   OR currency_code <> 'CNY'
   OR methodology_ref IS NULL
   OR TRIM(methodology_ref) = ''
   OR measured_from >= measured_to;

SELECT 'ad_roas_computed_without_spend' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_marketing_campaign_performance
WHERE ad_roas IS NOT NULL
  AND ad_spend_amount_minor = 0;

SELECT 'promotion_roi_exposed_without_baseline' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_marketing_campaign_performance
WHERE promotion_roi IS NOT NULL
  AND (promotion_roi_status <> 'READY'
       OR experiment_id IS NULL
       OR promotion_cost_minor <= 0);

SELECT 'platform_take_rate_component_without_attribution' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_marketing_campaign_performance
WHERE platform_take_rate_ad_revenue_component IS NOT NULL
  AND attribution_amount_minor = 0;

SELECT 'platform_take_rate_without_controlled_revenue_or_gmv' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_platform_revenue_take_rate
WHERE platform_take_rate IS NOT NULL
  AND (readiness_status <> 'READY'
       OR platform_revenue_amount_minor = 0
       OR gmv_amount_minor = 0);
