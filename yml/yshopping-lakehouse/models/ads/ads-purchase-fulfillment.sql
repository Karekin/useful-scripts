CREATE OR REPLACE VIEW yshopping_ads.ads_purchase_fulfillment AS
SELECT
    tenant_id,
    purchase_order_id,
    purchase_order_no,
    supplier_id,
    MAX(occurred_at) AS ordered_at,
    SUM(ordered_quantity) AS ordered_quantity,
    SUM(received_quantity) AS received_quantity,
    SUM(returned_quantity) AS returned_quantity,
    CASE WHEN SUM(ordered_quantity) = 0 THEN 0
         ELSE SUM(received_quantity) / SUM(ordered_quantity) END AS receipt_fulfillment_rate,
    CASE
      WHEN SUM(received_quantity) >= SUM(ordered_quantity) THEN 'FULFILLED'
      WHEN SUM(received_quantity) > 0 THEN 'PARTIAL'
      ELSE 'OPEN'
    END AS fulfillment_status,
    MAX(updated_at) AS updated_at
FROM yshopping_dwd.dwd_purchase_order_line
WHERE audit_status = 20
GROUP BY tenant_id, purchase_order_id, purchase_order_no, supplier_id;
