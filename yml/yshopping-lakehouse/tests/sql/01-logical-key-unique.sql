SELECT 'logical_key_unique' AS check_name, COUNT(*) AS violations
FROM (
  SELECT tenant_id, inventory_movement_id
  FROM yshopping_dwd.dwd_inventory_movement
  GROUP BY tenant_id, inventory_movement_id
  HAVING COUNT(*) > 1
) x;
