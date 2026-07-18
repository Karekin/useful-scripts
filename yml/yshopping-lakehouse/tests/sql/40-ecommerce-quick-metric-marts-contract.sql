SELECT 'refund_cycle_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, refund_id
    FROM yshopping_dws.dws_canonical_after_sale_refund_cycle
    GROUP BY tenant_id, refund_id
    HAVING COUNT(*) <> 1
) duplicate_refund;

SELECT 'refund_cycle_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_after_sale_refund_cycle
WHERE requested_at IS NULL
   OR succeeded_at IS NULL
   OR succeeded_at < requested_at
   OR refund_cycle_hours < 0;

SELECT 'inventory_sell_through_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_inventory_sell_through_30d
WHERE denominator_quantity_30d <= 0
   OR net_sold_quantity_30d < 0
   OR shipped_quantity_30d < returned_quantity_30d
   OR sell_through_rate_30d < 0
   OR sell_through_rate_30d > 100;

SELECT 'service_first_response_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_customer_service_ticket_current
WHERE first_response_minutes IS NOT NULL
  AND (
      first_customer_inbound_at IS NULL
      OR first_agent_outbound_at IS NULL
      OR first_agent_outbound_at < first_customer_inbound_at
      OR first_response_minutes < 0
  );
