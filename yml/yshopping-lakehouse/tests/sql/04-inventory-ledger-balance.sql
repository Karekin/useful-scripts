SELECT 'inventory_ledger_balance' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_product_warehouse_inventory
WHERE on_hand_quantity <> ledger_quantity OR available_quantity <> on_hand_quantity - reserved_quantity;
