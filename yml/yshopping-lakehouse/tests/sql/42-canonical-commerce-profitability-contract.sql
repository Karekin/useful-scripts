SELECT 'canonical_order_item_profitability_net_revenue_negative' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_order_item_profitability_current
WHERE net_revenue_amount_minor < 0;

SELECT 'canonical_order_item_profitability_gross_profit_mismatch', COUNT(*)
FROM yshopping_dws.dws_canonical_order_item_profitability_current
WHERE gross_profit_amount_minor
      <> net_revenue_amount_minor - COALESCE(merchandise_cost_minor, 0);

SELECT 'canonical_order_item_profitability_contribution_profit_mismatch', COUNT(*)
FROM yshopping_dws.dws_canonical_order_item_profitability_current
WHERE contribution_profit_amount_minor
      <> gross_profit_amount_minor
         - variable_fulfillment_cost_amount_minor
         - after_sale_loss_amount_minor;

SELECT 'canonical_order_profitability_order_rollup_mismatch', COUNT(*)
FROM (
    SELECT item.tenant_id, item.order_id
    FROM yshopping_dws.dws_canonical_order_item_profitability_current item
    JOIN yshopping_dws.dws_canonical_order_profitability_current summary
      ON summary.tenant_id = item.tenant_id
     AND summary.order_id = item.order_id
    GROUP BY item.tenant_id, item.order_id,
             summary.net_revenue_amount_minor,
             summary.merchandise_cost_amount_minor,
             summary.gross_profit_amount_minor,
             summary.variable_fulfillment_cost_amount_minor,
             summary.after_sale_loss_amount_minor,
             summary.contribution_profit_amount_minor
    HAVING SUM(item.net_revenue_amount_minor) <> summary.net_revenue_amount_minor
        OR SUM(COALESCE(item.merchandise_cost_minor, 0)) <> summary.merchandise_cost_amount_minor
        OR SUM(item.gross_profit_amount_minor) <> summary.gross_profit_amount_minor
        OR SUM(item.variable_fulfillment_cost_amount_minor) <> summary.variable_fulfillment_cost_amount_minor
        OR SUM(item.after_sale_loss_amount_minor) <> summary.after_sale_loss_amount_minor
        OR SUM(item.contribution_profit_amount_minor) <> summary.contribution_profit_amount_minor
) mismatches;
