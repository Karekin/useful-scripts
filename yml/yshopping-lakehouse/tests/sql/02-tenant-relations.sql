SELECT 'tenant_relations' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_purchase_receipt_line r
LEFT JOIN yshopping_dim.dim_erp_product_current p
  ON p.tenant_id = r.tenant_id AND p.erp_product_id = r.product_id
LEFT JOIN yshopping_dim.dim_warehouse_current w
  ON w.tenant_id = r.tenant_id AND w.warehouse_id = r.warehouse_id
LEFT JOIN yshopping_dim.dim_supplier_current s
  ON s.tenant_id = r.tenant_id AND s.supplier_id = r.supplier_id
WHERE p.erp_product_id IS NULL OR w.warehouse_id IS NULL OR s.supplier_id IS NULL;
