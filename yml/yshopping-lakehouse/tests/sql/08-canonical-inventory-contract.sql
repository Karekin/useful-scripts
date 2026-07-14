SELECT 'canonical_inventory_version_continuity' AS check_name, COUNT(*) AS violations
FROM (
  SELECT tenant_id, balance_id
  FROM yshopping_dwd.dwd_canonical_inventory_movement
  GROUP BY tenant_id, balance_id
  HAVING MIN(aggregate_version) <> 1
     OR MAX(aggregate_version) <> COUNT(*)
) gap
UNION ALL
SELECT 'canonical_inventory_available_invariant', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_movement
WHERE after_on_hand_quantity < 0
   OR after_reserved_quantity < 0
   OR after_available_quantity <> after_on_hand_quantity - after_reserved_quantity
UNION ALL
SELECT 'canonical_inventory_required_dimensions', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_movement
WHERE canonical_sku_id IS NULL OR canonical_sku_id = ''
   OR warehouse_id IS NULL OR warehouse_id = ''
   OR owner_id IS NULL OR owner_id = ''
   OR uom_code IS NULL OR uom_code = '';
