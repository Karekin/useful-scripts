CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_order_item_profitability_current AS
WITH funding_by_item AS (
    SELECT
        allocation.tenant_id,
        allocation.order_id,
        allocation.order_item_id,
        SUM(IF(funding.funder_type = 'PLATFORM', funding.amount_minor, 0)) AS platform_marketing_amount_minor,
        SUM(IF(funding.funder_type = 'MERCHANT', funding.amount_minor, 0)) AS merchant_marketing_amount_minor,
        SUM(IF(funding.funder_type = 'PARTNER', funding.amount_minor, 0)) AS partner_marketing_amount_minor,
        SUM(funding.amount_minor) AS total_marketing_amount_minor,
        MAX(funding.recorded_at) AS marketing_freshness_at
    FROM yshopping_dwd.dwd_canonical_order_benefit_allocation_event allocation
    JOIN yshopping_dwd.dwd_canonical_order_benefit_funding_event funding
      ON funding.tenant_id = allocation.tenant_id
     AND funding.order_id = allocation.order_id
     AND funding.benefit_application_id = allocation.benefit_application_id
     AND funding.benefit_allocation_id = allocation.benefit_allocation_id
    GROUP BY allocation.tenant_id, allocation.order_id, allocation.order_item_id
), fulfillment_cost_by_item AS (
    SELECT
        tenant_id,
        order_id,
        order_item_id,
        SUM(COALESCE(variable_fulfillment_cost_minor, 0)) AS variable_fulfillment_cost_minor,
        MAX(item_freshness_at) AS fulfillment_cost_freshness_at
    FROM yshopping_dws.dws_canonical_fulfillment_item_current
    GROUP BY tenant_id, order_id, order_item_id
), return_loss_by_item AS (
    SELECT
        tenant_id,
        order_id,
        order_item_id,
        SUM(COALESCE(return_shipping_amount_minor, 0)) AS after_sale_loss_amount_minor,
        MAX(data_freshness_at) AS after_sale_freshness_at
    FROM yshopping_dws.dws_canonical_after_sale_resolution_current
    GROUP BY tenant_id, order_id, order_item_id
)
SELECT
    item.tenant_id,
    item.run_id,
    item.order_id,
    item.order_no,
    item.order_item_id,
    benefit.line_key,
    item.canonical_sku_id,
    item.quantity,
    item.order_status,
    item.currency_code,
    item.line_amount_minor AS gross_amount_minor,
    COALESCE(benefit.discount_amount_minor, 0) AS discount_amount_minor,
    item.listing_id,
    item.listing_offer_id,
    item.channel_code,
    item.shop_id,
    item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0) AS booked_net_revenue_amount_minor,
    COALESCE(settlement.refunded_net_amount_minor, 0) AS refunded_net_amount_minor,
    item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0)
        - COALESCE(settlement.refunded_net_amount_minor, 0) AS net_revenue_amount_minor,
    item.merchandise_cost_minor,
    item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0)
        - COALESCE(settlement.refunded_net_amount_minor, 0)
        - COALESCE(item.merchandise_cost_minor, 0) AS gross_profit_amount_minor,
    COALESCE(fulfillment.variable_fulfillment_cost_minor, 0) AS variable_fulfillment_cost_amount_minor,
    COALESCE(after_sale.after_sale_loss_amount_minor, 0) AS after_sale_loss_amount_minor,
    COALESCE(marketing.platform_marketing_amount_minor, 0) AS platform_marketing_amount_minor,
    COALESCE(marketing.merchant_marketing_amount_minor, 0) AS merchant_marketing_amount_minor,
    COALESCE(marketing.partner_marketing_amount_minor, 0) AS partner_marketing_amount_minor,
    COALESCE(marketing.total_marketing_amount_minor, 0) AS total_marketing_amount_minor,
    item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0)
        - COALESCE(settlement.refunded_net_amount_minor, 0)
        - COALESCE(item.merchandise_cost_minor, 0)
        - COALESCE(fulfillment.variable_fulfillment_cost_minor, 0)
        - COALESCE(after_sale.after_sale_loss_amount_minor, 0) AS contribution_profit_amount_minor,
    CASE
        WHEN item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0)
             - COALESCE(settlement.refunded_net_amount_minor, 0) = 0 THEN NULL
        ELSE CAST(
            item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0)
                - COALESCE(settlement.refunded_net_amount_minor, 0)
                - COALESCE(item.merchandise_cost_minor, 0)
                - COALESCE(fulfillment.variable_fulfillment_cost_minor, 0)
                - COALESCE(after_sale.after_sale_loss_amount_minor, 0)
            AS DECIMAL(24,6)
        ) / CAST(
            item.line_amount_minor - COALESCE(benefit.discount_amount_minor, 0)
                - COALESCE(settlement.refunded_net_amount_minor, 0)
            AS DECIMAL(24,6)
        )
    END AS contribution_margin_rate,
    GREATEST(
        item.item_freshness_at,
        COALESCE(marketing.marketing_freshness_at, item.item_freshness_at),
        COALESCE(fulfillment.fulfillment_cost_freshness_at, item.item_freshness_at),
        COALESCE(after_sale.after_sale_freshness_at, item.item_freshness_at)
    ) AS data_freshness_at
FROM yshopping_dws.dws_canonical_order_item_current item
LEFT JOIN yshopping_dws.dws_canonical_order_item_benefit_current benefit
  ON benefit.tenant_id = item.tenant_id
 AND benefit.order_id = item.order_id
 AND benefit.order_item_id = item.order_item_id
LEFT JOIN yshopping_dim.dim_canonical_order_item_return_settlement_current settlement
  ON settlement.tenant_id = item.tenant_id
 AND settlement.order_item_id = item.order_item_id
LEFT JOIN funding_by_item marketing
  ON marketing.tenant_id = item.tenant_id
 AND marketing.order_id = item.order_id
 AND marketing.order_item_id = item.order_item_id
LEFT JOIN fulfillment_cost_by_item fulfillment
  ON fulfillment.tenant_id = item.tenant_id
 AND fulfillment.order_id = item.order_id
 AND fulfillment.order_item_id = item.order_item_id
LEFT JOIN return_loss_by_item after_sale
  ON after_sale.tenant_id = item.tenant_id
 AND after_sale.order_id = item.order_id
 AND after_sale.order_item_id = item.order_item_id
WHERE item.merchandise_cost_minor IS NOT NULL;
