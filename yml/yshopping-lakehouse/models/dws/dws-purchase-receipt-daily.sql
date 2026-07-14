CREATE OR REPLACE VIEW yshopping_dws.dws_purchase_receipt_daily AS
SELECT
    tenant_id,
    DATE(occurred_at) AS business_date,
    supplier_id,
    warehouse_id,
    COUNT(DISTINCT receipt_id) AS receipt_count,
    COUNT(*) AS receipt_line_count,
    SUM(received_quantity) AS received_quantity,
    SUM(product_amount_yuan) AS product_amount_yuan,
    SUM(tax_amount_yuan) AS tax_amount_yuan,
    MAX(updated_at) AS updated_at
FROM yshopping_dwd.dwd_purchase_receipt_line
WHERE audit_status = 20
GROUP BY tenant_id, DATE(occurred_at), supplier_id, warehouse_id;
