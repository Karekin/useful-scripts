CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_order_profitability_current AS
SELECT
    tenant_id,
    run_id,
    order_id,
    order_no,
    currency_code,
    COUNT(*) AS profitability_item_count,
    SUM(booked_net_revenue_amount_minor) AS booked_net_revenue_amount_minor,
    SUM(refunded_net_amount_minor) AS refunded_net_amount_minor,
    SUM(net_revenue_amount_minor) AS net_revenue_amount_minor,
    SUM(COALESCE(merchandise_cost_minor, 0)) AS merchandise_cost_amount_minor,
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
FROM yshopping_dws.dws_canonical_order_item_profitability_current
GROUP BY tenant_id, run_id, order_id, order_no, currency_code;
