CREATE OR REPLACE VIEW yshopping_ads.ads_inventory_health AS
SELECT
    i.tenant_id,
    i.product_id,
    p.product_name,
    p.bar_code,
    i.warehouse_id,
    w.warehouse_name,
    i.on_hand_quantity,
    i.reserved_quantity,
    i.available_quantity,
    i.ledger_quantity,
    i.on_hand_quantity - i.ledger_quantity AS reconciliation_gap_quantity,
    CASE
      WHEN i.available_quantity <= 0 THEN 'OUT_OF_STOCK'
      WHEN i.available_quantity < 10 THEN 'LOW_STOCK'
      ELSE 'HEALTHY'
    END AS inventory_health_status,
    i.last_movement_at,
    i.updated_at
FROM yshopping_dws.dws_product_warehouse_inventory i
LEFT JOIN yshopping_dim.dim_erp_product_current p
  ON p.tenant_id = i.tenant_id AND p.erp_product_id = i.product_id
LEFT JOIN yshopping_dim.dim_warehouse_current w
  ON w.tenant_id = i.tenant_id AND w.warehouse_id = i.warehouse_id;
