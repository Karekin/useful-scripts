CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_advertising_economics_daily AS
WITH experiment_merchant AS (
    SELECT
        tenant_id,
        campaign_id,
        CASE WHEN COUNT(DISTINCT merchant_id) = 1 THEN MIN(merchant_id) ELSE NULL END AS merchant_id
    FROM yshopping_dim.dim_canonical_promotion_experiment_result_current
    GROUP BY tenant_id, campaign_id
), ledger_daily AS (
    SELECT
        tenant_id,
        campaign_id,
        placement_id,
        merchant_id,
        CAST(occurred_at AS DATE) AS event_date,
        SUM(IF(entry_type = 'SPEND', amount_minor, 0)) AS ad_spend_amount_minor,
        SUM(IF(entry_type = 'REVENUE', amount_minor, 0)) AS platform_revenue_amount_minor,
        SUM(IF(entry_type = 'REVENUE' AND revenue_type = 'ADVERTISING', amount_minor, 0)) AS ad_revenue_amount_minor,
        SUM(IF(entry_type = 'REVENUE' AND revenue_type = 'COMMISSION', amount_minor, 0)) AS commission_revenue_amount_minor,
        SUM(IF(entry_type = 'REVENUE' AND revenue_type = 'FULFILLMENT_SERVICE', amount_minor, 0))
            AS fulfillment_revenue_amount_minor,
        SUM(IF(entry_type = 'REVENUE' AND revenue_type = 'PAYMENT_SERVICE', amount_minor, 0))
            AS payment_service_revenue_amount_minor,
        SUM(IF(entry_type = 'REVENUE' AND revenue_type = 'OTHER_PLATFORM_REVENUE', amount_minor, 0))
            AS other_platform_revenue_amount_minor,
        COUNT(*) AS ledger_entry_count,
        MAX(recorded_at) AS ledger_freshness_at
    FROM yshopping_dwd.dwd_canonical_advertising_ledger_event
    GROUP BY tenant_id, campaign_id, placement_id, merchant_id, CAST(occurred_at AS DATE)
), interaction_daily AS (
    SELECT
        tenant_id,
        campaign_id,
        placement_id,
        CAST(occurred_at AS DATE) AS event_date,
        COUNT(DISTINCT IF(interaction_type = 'ATTRIBUTION', order_ref, NULL)) AS attribution_order_count,
        SUM(IF(interaction_type = 'ATTRIBUTION', attribution_amount_minor, 0)) AS attribution_amount_minor,
        SUM(IF(interaction_type = 'IMPRESSION', 1, 0)) AS impression_count,
        SUM(IF(interaction_type = 'CLICK', 1, 0)) AS click_count,
        SUM(IF(interaction_type = 'ATTRIBUTION', 1, 0)) AS attribution_count,
        MAX(recorded_at) AS interaction_freshness_at
    FROM yshopping_dwd.dwd_canonical_advertising_interaction_event
    GROUP BY tenant_id, campaign_id, placement_id, CAST(occurred_at AS DATE)
), campaign_merchant AS (
    SELECT
        tenant_id,
        campaign_id,
        CASE WHEN COUNT(DISTINCT merchant_id) = 1 THEN MIN(merchant_id) ELSE NULL END AS merchant_id,
        COUNT(DISTINCT merchant_id) AS merchant_binding_count
    FROM (
        SELECT tenant_id, campaign_id, merchant_id
        FROM ledger_daily
        WHERE merchant_id IS NOT NULL
        UNION ALL
        SELECT tenant_id, campaign_id, merchant_id
        FROM experiment_merchant
        WHERE merchant_id IS NOT NULL
    ) merchant_sources
    GROUP BY tenant_id, campaign_id
), daily_keys AS (
    SELECT tenant_id, campaign_id, placement_id, event_date
    FROM interaction_daily
    UNION
    SELECT tenant_id, campaign_id, placement_id, event_date
    FROM ledger_daily
)
SELECT
    keyset.tenant_id,
    keyset.campaign_id,
    merchant.merchant_id,
    keyset.placement_id,
    keyset.event_date,
    COALESCE(interaction.attribution_order_count, 0) AS attribution_order_count,
    COALESCE(interaction.attribution_amount_minor, 0) AS attribution_amount_minor,
    COALESCE(interaction.impression_count, 0) AS impression_count,
    COALESCE(interaction.click_count, 0) AS click_count,
    COALESCE(interaction.attribution_count, 0) AS attribution_count,
    COALESCE(ledger.ad_spend_amount_minor, 0) AS ad_spend_amount_minor,
    COALESCE(ledger.platform_revenue_amount_minor, 0) AS platform_revenue_amount_minor,
    COALESCE(ledger.ad_revenue_amount_minor, 0) AS ad_revenue_amount_minor,
    COALESCE(ledger.commission_revenue_amount_minor, 0) AS commission_revenue_amount_minor,
    COALESCE(ledger.fulfillment_revenue_amount_minor, 0) AS fulfillment_revenue_amount_minor,
    COALESCE(ledger.payment_service_revenue_amount_minor, 0) AS payment_service_revenue_amount_minor,
    COALESCE(ledger.other_platform_revenue_amount_minor, 0) AS other_platform_revenue_amount_minor,
    COALESCE(ledger.ledger_entry_count, 0) AS ledger_entry_count,
    COALESCE(merchant.merchant_binding_count, 0) AS merchant_binding_count,
    CASE
        WHEN COALESCE(ledger.ad_spend_amount_minor, 0) = 0 THEN NULL
        ELSE CAST(COALESCE(interaction.attribution_amount_minor, 0) AS DECIMAL(24, 6))
             / CAST(ledger.ad_spend_amount_minor AS DECIMAL(24, 6))
    END AS ad_roas,
    CASE
        WHEN COALESCE(interaction.attribution_amount_minor, 0) = 0 THEN NULL
        ELSE CAST(COALESCE(ledger.ad_revenue_amount_minor, 0) AS DECIMAL(24, 6))
             / CAST(interaction.attribution_amount_minor AS DECIMAL(24, 6))
    END AS ad_revenue_take_rate_component,
    GREATEST(
        COALESCE(interaction.interaction_freshness_at, CAST('1970-01-01 00:00:00' AS DATETIME)),
        COALESCE(ledger.ledger_freshness_at, CAST('1970-01-01 00:00:00' AS DATETIME))
    ) AS data_freshness_at
FROM daily_keys keyset
LEFT JOIN interaction_daily interaction
  ON interaction.tenant_id = keyset.tenant_id
 AND interaction.campaign_id = keyset.campaign_id
 AND interaction.placement_id <=> keyset.placement_id
 AND interaction.event_date = keyset.event_date
LEFT JOIN ledger_daily ledger
  ON ledger.tenant_id = keyset.tenant_id
 AND ledger.campaign_id = keyset.campaign_id
 AND ledger.placement_id <=> keyset.placement_id
 AND ledger.event_date = keyset.event_date
LEFT JOIN campaign_merchant merchant
  ON merchant.tenant_id = keyset.tenant_id
 AND merchant.campaign_id = keyset.campaign_id;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_promotion_experiment_current AS
WITH campaign_resolution AS (
    SELECT
        application.tenant_id,
        application.order_id,
        application.benefit_application_id,
        CASE
            WHEN application.benefit_source_type IN ('CAMPAIGN', 'PROMOTION') THEN application.benefit_source_id
            WHEN application.entitlement_id IS NOT NULL THEN entitlement.campaign_id
            WHEN application.benefit_source_type = 'COUPON_ENTITLEMENT' THEN entitlement.campaign_id
            WHEN application.benefit_source_type = 'COUPON_TEMPLATE' THEN template.campaign_id
            ELSE NULL
        END AS campaign_id
    FROM yshopping_dim.dim_canonical_order_benefit_application_current application
    LEFT JOIN yshopping_dim.dim_canonical_coupon_entitlement_current entitlement
      ON entitlement.tenant_id = application.tenant_id
     AND entitlement.entitlement_id = application.entitlement_id
    LEFT JOIN yshopping_dim.dim_canonical_coupon_template_current template
      ON template.tenant_id = application.tenant_id
     AND template.template_id = application.benefit_source_id
), campaign_funding AS (
    SELECT
        resolution.tenant_id,
        resolution.campaign_id,
        SUM(IF(funding.funder_type = 'PLATFORM', funding.amount_minor, 0)) AS platform_promotion_cost_minor,
        SUM(IF(funding.funder_type = 'MERCHANT', funding.amount_minor, 0)) AS merchant_promotion_cost_minor,
        SUM(IF(funding.funder_type = 'PARTNER', funding.amount_minor, 0)) AS partner_promotion_cost_minor,
        SUM(funding.amount_minor) AS total_booked_promotion_cost_minor,
        MAX(funding.recorded_at) AS funding_freshness_at
    FROM campaign_resolution resolution
    JOIN yshopping_dwd.dwd_canonical_order_benefit_funding_event funding
      ON funding.tenant_id = resolution.tenant_id
     AND funding.order_id = resolution.order_id
     AND funding.benefit_application_id = resolution.benefit_application_id
    WHERE resolution.campaign_id IS NOT NULL
    GROUP BY resolution.tenant_id, resolution.campaign_id
)
SELECT
    experiment.tenant_id,
    experiment.campaign_id,
    experiment.merchant_id,
    experiment.experiment_id,
    experiment.experiment_code,
    experiment.measured_from,
    experiment.measured_to,
    experiment.baseline_contribution_profit_minor,
    experiment.treatment_contribution_profit_minor,
    experiment.incremental_contribution_profit_minor,
    experiment.promotion_cost_minor,
    experiment.eligible_population_count,
    experiment.treatment_population_count,
    experiment.control_population_count,
    experiment.currency_code,
    experiment.methodology_ref,
    COALESCE(funding.platform_promotion_cost_minor, 0) AS platform_promotion_cost_minor,
    COALESCE(funding.merchant_promotion_cost_minor, 0) AS merchant_promotion_cost_minor,
    COALESCE(funding.partner_promotion_cost_minor, 0) AS partner_promotion_cost_minor,
    COALESCE(funding.total_booked_promotion_cost_minor, 0) AS total_booked_promotion_cost_minor,
    CASE
        WHEN experiment.promotion_cost_minor = 0 THEN NULL
        ELSE CAST(experiment.incremental_contribution_profit_minor AS DECIMAL(24, 6))
             / CAST(experiment.promotion_cost_minor AS DECIMAL(24, 6))
    END AS promotion_roi,
    GREATEST(
        experiment.recorded_at,
        COALESCE(funding.funding_freshness_at, experiment.recorded_at)
    ) AS data_freshness_at
FROM yshopping_dim.dim_canonical_promotion_experiment_result_current experiment
LEFT JOIN campaign_funding funding
  ON funding.tenant_id = experiment.tenant_id
 AND funding.campaign_id = experiment.campaign_id;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_platform_revenue_take_rate_current AS
WITH revenue_by_tenant AS (
    SELECT
        tenant_id,
        SUM(platform_revenue_amount_minor) AS platform_revenue_amount_minor,
        SUM(ad_revenue_amount_minor) AS advertising_revenue_amount_minor,
        SUM(commission_revenue_amount_minor) AS commission_revenue_amount_minor,
        SUM(fulfillment_revenue_amount_minor) AS fulfillment_revenue_amount_minor,
        SUM(payment_service_revenue_amount_minor) AS payment_service_revenue_amount_minor,
        SUM(other_platform_revenue_amount_minor) AS other_platform_revenue_amount_minor,
        MAX(data_freshness_at) AS revenue_freshness_at
    FROM yshopping_dws.dws_canonical_advertising_economics_daily
    GROUP BY tenant_id
), gmv_by_tenant AS (
    SELECT
        tenant_id,
        SUM(line_amount_minor) AS gmv_amount_minor,
        MAX(item_freshness_at) AS gmv_freshness_at
    FROM yshopping_dws.dws_canonical_order_item_current
    WHERE order_status IN ('PAYMENT_CONFIRMED', 'SHIPPED', 'DELIVERED', 'COMPLETED', 'RETURNED')
    GROUP BY tenant_id
)
SELECT
    gmv.tenant_id,
    gmv.gmv_amount_minor,
    COALESCE(revenue.platform_revenue_amount_minor, 0) AS platform_revenue_amount_minor,
    COALESCE(revenue.advertising_revenue_amount_minor, 0) AS advertising_revenue_amount_minor,
    COALESCE(revenue.commission_revenue_amount_minor, 0) AS commission_revenue_amount_minor,
    COALESCE(revenue.fulfillment_revenue_amount_minor, 0) AS fulfillment_revenue_amount_minor,
    COALESCE(revenue.payment_service_revenue_amount_minor, 0) AS payment_service_revenue_amount_minor,
    COALESCE(revenue.other_platform_revenue_amount_minor, 0) AS other_platform_revenue_amount_minor,
    CASE
        WHEN gmv.gmv_amount_minor = 0 OR COALESCE(revenue.platform_revenue_amount_minor, 0) = 0 THEN NULL
        ELSE CAST(COALESCE(revenue.platform_revenue_amount_minor, 0) AS DECIMAL(24, 6))
             / CAST(gmv.gmv_amount_minor AS DECIMAL(24, 6))
    END AS platform_take_rate,
    GREATEST(
        gmv.gmv_freshness_at,
        COALESCE(revenue.revenue_freshness_at, gmv.gmv_freshness_at)
    ) AS data_freshness_at
FROM gmv_by_tenant gmv
LEFT JOIN revenue_by_tenant revenue
  ON revenue.tenant_id = gmv.tenant_id;
