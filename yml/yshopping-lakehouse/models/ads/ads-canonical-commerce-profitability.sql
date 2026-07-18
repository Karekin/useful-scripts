CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_commerce_profitability AS
SELECT
    tenant_id,
    COUNT(*) AS profitable_order_count,
    SUM(net_revenue_amount_minor) AS net_revenue_amount_minor,
    SUM(merchandise_cost_amount_minor) AS merchandise_cost_amount_minor,
    SUM(gross_profit_amount_minor) AS gross_profit_amount_minor,
    SUM(variable_fulfillment_cost_amount_minor) AS variable_fulfillment_cost_amount_minor,
    SUM(after_sale_loss_amount_minor) AS after_sale_loss_amount_minor,
    SUM(platform_marketing_amount_minor) AS platform_marketing_amount_minor,
    SUM(merchant_marketing_amount_minor) AS merchant_marketing_amount_minor,
    SUM(partner_marketing_amount_minor) AS partner_marketing_amount_minor,
    SUM(total_marketing_amount_minor) AS total_marketing_amount_minor,
    SUM(contribution_profit_amount_minor) AS contribution_profit_amount_minor,
    CASE
        WHEN SUM(net_revenue_amount_minor) = 0 THEN NULL
        ELSE CAST(SUM(contribution_profit_amount_minor) AS DECIMAL(24,6))
             / CAST(SUM(net_revenue_amount_minor) AS DECIMAL(24,6))
    END AS contribution_margin_rate,
    MAX(data_freshness_at) AS data_freshness_at
FROM yshopping_dws.dws_canonical_order_profitability_current
GROUP BY tenant_id;
