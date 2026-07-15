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
   OR COALESCE(after_in_transit_quantity, 0) < 0
   OR (schema_version IN (1, 2)
       AND after_available_quantity <> after_on_hand_quantity - after_reserved_quantity)
   OR (schema_version = 3 AND stock_status = 'SELLABLE' AND quality_status = 'QUALIFIED'
       AND after_available_quantity <> after_on_hand_quantity - after_reserved_quantity)
   OR (schema_version = 3 AND (stock_status <> 'SELLABLE' OR quality_status <> 'QUALIFIED')
       AND after_available_quantity <> 0)
UNION ALL
SELECT 'canonical_inventory_required_dimensions', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_movement
WHERE canonical_sku_id IS NULL OR canonical_sku_id = ''
   OR warehouse_id IS NULL OR warehouse_id = ''
   OR owner_id IS NULL OR owner_id = ''
   OR base_uom_code IS NULL OR base_uom_code = ''
UNION ALL
SELECT 'canonical_inventory_v3_required_dimensions', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_movement
WHERE schema_version = 3
  AND (owner_type <> 'MERCHANT'
    OR owner_id IS NULL OR owner_id = ''
    OR canonical_sku_id IS NULL OR canonical_sku_id = ''
    OR warehouse_id IS NULL OR warehouse_id = ''
    OR location_id IS NULL OR location_id = ''
    OR stock_status NOT IN ('SELLABLE', 'NON_SELLABLE')
    OR quality_status NOT IN ('PENDING_QC', 'QUALIFIED', 'DAMAGED', 'REJECTED')
    OR base_uom_code IS NULL OR base_uom_code = ''
    OR ledger_transaction_id IS NULL OR movement_group_id IS NULL
    OR entry_role <> 'SINGLE')
UNION ALL
SELECT 'canonical_inventory_v3_lot_is_explicit_not_fabricated', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_movement
WHERE schema_version = 3
  AND ((lot_id IS NULL AND lot_code IS NOT NULL)
    OR (lot_id IS NOT NULL AND (lot_code IS NULL OR lot_code = ''))
    OR COALESCE(lot_code, '') IN ('NO_LOT', 'DEFAULT', 'UNKNOWN'))
UNION ALL
SELECT 'canonical_inventory_v3_movement_conservation', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_movement
WHERE schema_version = 3
  AND (delta_in_transit_quantity <> 0
    OR delta_on_hand_quantity IS NULL OR delta_reserved_quantity IS NULL
    OR (movement_type IN ('PURCHASE_RECEIPT', 'SALE_RETURN')
        AND (delta_on_hand_quantity <= 0 OR delta_reserved_quantity <> 0))
    OR (movement_type = 'RESERVATION'
        AND (delta_on_hand_quantity <> 0 OR delta_reserved_quantity <= 0))
    OR (movement_type = 'SALE_SHIPMENT'
        AND (delta_on_hand_quantity >= 0 OR delta_reserved_quantity <> delta_on_hand_quantity))
    OR (movement_type = 'RESERVATION_RELEASE'
        AND (delta_on_hand_quantity <> 0 OR delta_reserved_quantity >= 0)))
UNION ALL
SELECT 'canonical_inventory_v3_reservation_allocation_contract', COUNT(*)
FROM yshopping_dwd.dwd_canonical_inventory_movement
WHERE schema_version = 3
  AND ((movement_type IN ('RESERVATION', 'SALE_SHIPMENT', 'RESERVATION_RELEASE')
        AND (reservation_id IS NULL OR allocation_id IS NULL))
    OR (movement_type IN ('PURCHASE_RECEIPT', 'SALE_RETURN')
        AND (reservation_id IS NOT NULL OR allocation_id IS NOT NULL)));
