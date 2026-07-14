SELECT 'purchase_header_line_balance' AS check_name, COUNT(*) AS violations
FROM (
  SELECT h.tenant_id, h.id,
         h.total_count AS header_quantity,
         COALESCE(SUM(i.count), 0) AS line_quantity,
         h.total_product_price AS header_product_amount,
         COALESCE(SUM(i.total_price), 0) AS line_product_amount
  FROM yshopping_ods.erp_purchase_order h
  LEFT JOIN yshopping_ods.erp_purchase_order_items i
    ON i.tenant_id = h.tenant_id AND i.order_id = h.id AND i.deleted = FALSE
  WHERE h.deleted = FALSE
  GROUP BY h.tenant_id, h.id, h.total_count, h.total_product_price
  HAVING header_quantity <> line_quantity OR header_product_amount <> line_product_amount
) x;
