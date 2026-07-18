CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_marketing_campaign_performance AS
WITH daily AS (
    SELECT *
    FROM yshopping_dws.dws_canonical_advertising_economics_daily
), daily_rollup AS (
    SELECT
        tenant_id,
        campaign_id,
        merchant_id,
        SUM(attribution_order_count) AS attribution_order_count,
        SUM(attribution_amount_minor) AS attribution_amount_minor,
        SUM(impression_count) AS impression_count,
        SUM(click_count) AS click_count,
        SUM(attribution_count) AS attribution_count,
        SUM(ad_spend_amount_minor) AS ad_spend_amount_minor,
        SUM(platform_revenue_amount_minor) AS platform_revenue_amount_minor,
        SUM(ad_revenue_amount_minor) AS ad_revenue_amount_minor,
        SUM(commission_revenue_amount_minor) AS commission_revenue_amount_minor,
        SUM(fulfillment_revenue_amount_minor) AS fulfillment_revenue_amount_minor,
        SUM(payment_service_revenue_amount_minor) AS payment_service_revenue_amount_minor,
        SUM(other_platform_revenue_amount_minor) AS other_platform_revenue_amount_minor,
        SUM(ledger_entry_count) AS ledger_entry_count,
        MAX(merchant_binding_count) AS merchant_binding_count,
        MAX(data_freshness_at) AS data_freshness_at
    FROM daily
    GROUP BY tenant_id, campaign_id, merchant_id
)
SELECT
    campaign.tenant_id,
    campaign.campaign_id,
    COALESCE(experiment.merchant_id, daily.merchant_id) AS merchant_id,
    campaign.campaign_code,
    campaign.campaign_kind,
    campaign.current_status AS campaign_status,
    COALESCE(daily.attribution_order_count, 0) AS attribution_order_count,
    COALESCE(daily.attribution_amount_minor, 0) AS attribution_amount_minor,
    COALESCE(daily.impression_count, 0) AS impression_count,
    COALESCE(daily.click_count, 0) AS click_count,
    COALESCE(daily.attribution_count, 0) AS attribution_count,
    COALESCE(daily.ad_spend_amount_minor, 0) AS ad_spend_amount_minor,
    COALESCE(daily.platform_revenue_amount_minor, 0) AS platform_revenue_amount_minor,
    COALESCE(daily.ad_revenue_amount_minor, 0) AS ad_revenue_amount_minor,
    COALESCE(daily.commission_revenue_amount_minor, 0) AS commission_revenue_amount_minor,
    COALESCE(daily.fulfillment_revenue_amount_minor, 0) AS fulfillment_revenue_amount_minor,
    COALESCE(daily.payment_service_revenue_amount_minor, 0) AS payment_service_revenue_amount_minor,
    COALESCE(daily.other_platform_revenue_amount_minor, 0) AS other_platform_revenue_amount_minor,
    COALESCE(daily.ledger_entry_count, 0) AS ledger_entry_count,
    COALESCE(daily.merchant_binding_count, 0) AS merchant_binding_count,
    CASE
        WHEN COALESCE(daily.ad_spend_amount_minor, 0) = 0 THEN NULL
        ELSE CAST(COALESCE(daily.attribution_amount_minor, 0) AS DECIMAL(24, 6))
             / CAST(daily.ad_spend_amount_minor AS DECIMAL(24, 6))
    END AS ad_roas,
    CASE
        WHEN COALESCE(daily.attribution_amount_minor, 0) = 0 THEN NULL
        ELSE CAST(COALESCE(daily.ad_revenue_amount_minor, 0) AS DECIMAL(24, 6))
             / CAST(daily.attribution_amount_minor AS DECIMAL(24, 6))
    END AS platform_take_rate_ad_revenue_component,
    experiment.experiment_id,
    experiment.experiment_code,
    experiment.baseline_contribution_profit_minor,
    experiment.treatment_contribution_profit_minor,
    experiment.incremental_contribution_profit_minor,
    experiment.promotion_cost_minor,
    experiment.platform_promotion_cost_minor,
    experiment.merchant_promotion_cost_minor,
    experiment.partner_promotion_cost_minor,
    experiment.total_booked_promotion_cost_minor,
    experiment.promotion_roi,
    CASE
        WHEN COALESCE(daily.ad_spend_amount_minor, 0) > 0 THEN 'READY'
        WHEN COALESCE(daily.attribution_amount_minor, 0) > 0 THEN 'BLOCKED_MISSING_SPEND'
        ELSE 'BLOCKED_NO_ADVERTISING_LEDGER'
    END AS ad_roas_status,
    CASE
        WHEN experiment.experiment_id IS NULL THEN 'BLOCKED_MISSING_BASELINE'
        WHEN experiment.promotion_cost_minor <= 0 THEN 'BLOCKED_MISSING_COST'
        ELSE 'READY'
    END AS promotion_roi_status,
    GREATEST(
        campaign.recorded_at,
        COALESCE(daily.data_freshness_at, campaign.recorded_at),
        COALESCE(experiment.data_freshness_at, campaign.recorded_at)
    ) AS data_freshness_at
FROM yshopping_dim.dim_canonical_promotion_campaign_current campaign
LEFT JOIN daily_rollup daily
  ON daily.tenant_id = campaign.tenant_id
 AND daily.campaign_id = campaign.campaign_id
LEFT JOIN yshopping_dws.dws_canonical_promotion_experiment_current experiment
  ON experiment.tenant_id = campaign.tenant_id
 AND experiment.campaign_id = campaign.campaign_id
 AND (experiment.merchant_id <=> daily.merchant_id OR daily.merchant_id IS NULL)
WHERE campaign.current_status IN ('ACTIVE', 'PAUSED', 'COMPLETED');

CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_platform_revenue_take_rate AS
SELECT
    tenant_id,
    gmv_amount_minor,
    platform_revenue_amount_minor,
    advertising_revenue_amount_minor,
    commission_revenue_amount_minor,
    fulfillment_revenue_amount_minor,
    payment_service_revenue_amount_minor,
    other_platform_revenue_amount_minor,
    platform_take_rate,
    data_freshness_at,
    CASE
        WHEN platform_revenue_amount_minor = 0 THEN 'BLOCKED_MISSING_REVENUE_LEDGER'
        WHEN gmv_amount_minor = 0 THEN 'BLOCKED_MISSING_GMV'
        ELSE 'READY'
    END AS readiness_status
FROM yshopping_dws.dws_canonical_platform_revenue_take_rate_current;
