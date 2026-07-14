SELECT 'receipt_movement_match' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_purchase_receipt_line r
LEFT JOIN yshopping_dwd.dwd_inventory_movement m
  ON m.tenant_id = r.tenant_id
 AND m.biz_id = r.receipt_id
 AND m.biz_item_id = r.receipt_line_id
 AND m.movement_type = 70
WHERE r.audit_status = 20
  AND (m.inventory_movement_id IS NULL OR m.delta_quantity <> r.received_quantity);
