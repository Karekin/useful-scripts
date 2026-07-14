CREATE OR REPLACE VIEW yshopping_dwd.dwd_purchase_receipt_line AS
SELECT
    'yudao-erp' AS source_system,
    h.tenant_id,
    h.id AS receipt_id,
    h.no AS receipt_no,
    i.id AS receipt_line_id,
    h.order_id AS purchase_order_id,
    i.order_item_id AS purchase_order_line_id,
    h.supplier_id,
    h.account_id,
    i.warehouse_id,
    i.product_id,
    i.product_unit_id,
    h.status AS audit_status,
    h.in_time AS occurred_at,
    i.count AS received_quantity,
    i.product_price AS unit_price_amount_yuan,
    i.total_price AS product_amount_yuan,
    i.tax_price AS tax_amount_yuan,
    h.total_price AS receipt_total_amount_yuan,
    h.payment_price AS paid_amount_yuan,
    'CNY' AS currency,
    REGEXP_EXTRACT(COALESCE(h.remark, ''), 'run_id=([A-Za-z0-9-]+)', 1) AS run_id,
    h.create_time AS recorded_at,
    GREATEST(h.update_time, i.update_time) AS updated_at
FROM yshopping_ods.erp_purchase_in h
JOIN yshopping_ods.erp_purchase_in_items i
  ON i.tenant_id = h.tenant_id AND i.in_id = h.id AND i.deleted = FALSE
WHERE h.deleted = FALSE;
