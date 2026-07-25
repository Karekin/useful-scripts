CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_procurement_otif_current AS
WITH promise AS (
    SELECT
        promise.tenant_id,
        promise.promise_id,
        promise.run_id,
        promise.promise_key,
        promise.purchase_order_id,
        promise.purchase_order_no,
        promise.purchase_order_line_id,
        promise.supplier_id,
        promise.product_id,
        promise.product_unit_id,
        promise.ordered_quantity,
        promise.promised_receipt_at,
        promise.promise_timezone,
        promise.grace_minutes,
        promise.pause_minutes,
        DATE_ADD(
            DATE_ADD(promise.promised_receipt_at, INTERVAL promise.grace_minutes MINUTE),
            INTERVAL promise.pause_minutes MINUTE
        ) AS effective_deadline_at,
        promise.promise_frozen_at,
        promise.current_status AS promise_status,
        promise.recorded_at AS promise_recorded_at
    FROM yshopping_dim.dim_canonical_procurement_purchase_promise_current promise
), order_line AS (
    SELECT
        tenant_id,
        purchase_order_line_id,
        purchase_order_id,
        purchase_order_no,
        supplier_id,
        product_id,
        product_unit_id,
        ordered_quantity AS erp_ordered_quantity,
        received_quantity AS erp_received_quantity,
        updated_at AS order_line_updated_at
    FROM yshopping_dwd.dwd_purchase_order_line
    WHERE audit_status = 20
), receipt_total AS (
    SELECT
        tenant_id,
        purchase_order_line_id,
        SUM(received_quantity) AS total_received_quantity,
        MAX(occurred_at) AS latest_receipt_at,
        MAX(updated_at) AS receipt_updated_at
    FROM yshopping_dwd.dwd_purchase_receipt_line
    WHERE audit_status = 20
    GROUP BY tenant_id, purchase_order_line_id
), receipt_on_time AS (
    SELECT
        promise.tenant_id,
        promise.purchase_order_line_id,
        COALESCE(SUM(receipt.received_quantity), 0) AS on_time_received_quantity
    FROM promise
    LEFT JOIN yshopping_dwd.dwd_purchase_receipt_line receipt
      ON receipt.tenant_id = promise.tenant_id
     AND receipt.purchase_order_line_id = promise.purchase_order_line_id
     AND receipt.audit_status = 20
     AND receipt.occurred_at <= promise.effective_deadline_at
    GROUP BY promise.tenant_id, promise.purchase_order_line_id
)
SELECT
    promise.tenant_id,
    promise.promise_id,
    promise.run_id,
    promise.promise_key,
    promise.purchase_order_id,
    COALESCE(order_line.purchase_order_no, promise.purchase_order_no) AS purchase_order_no,
    promise.purchase_order_line_id,
    COALESCE(order_line.supplier_id, promise.supplier_id) AS supplier_id,
    COALESCE(order_line.product_id, promise.product_id) AS product_id,
    COALESCE(order_line.product_unit_id, promise.product_unit_id) AS product_unit_id,
    COALESCE(order_line.erp_ordered_quantity, promise.ordered_quantity) AS ordered_quantity,
    promise.promised_receipt_at,
    promise.promise_timezone,
    promise.grace_minutes,
    promise.pause_minutes,
    promise.effective_deadline_at,
    promise.promise_frozen_at,
    promise.promise_status,
    COALESCE(order_line.erp_received_quantity, 0) AS erp_received_quantity,
    COALESCE(receipt_total.total_received_quantity, 0) AS total_received_quantity,
    COALESCE(receipt_on_time.on_time_received_quantity, 0) AS on_time_received_quantity,
    receipt_total.latest_receipt_at,
    GREATEST(
        promise.promise_recorded_at,
        COALESCE(order_line.order_line_updated_at, promise.promise_recorded_at),
        COALESCE(receipt_total.receipt_updated_at, promise.promise_recorded_at)
    ) AS data_freshness_at,
    CASE
        WHEN promise.promise_status = 'ACTIVE'
         AND (
             promise.effective_deadline_at <= GREATEST(
                 promise.promise_recorded_at,
                 COALESCE(order_line.order_line_updated_at, promise.promise_recorded_at),
                 COALESCE(receipt_total.receipt_updated_at, promise.promise_recorded_at)
             )
             OR COALESCE(receipt_on_time.on_time_received_quantity, 0)
                >= COALESCE(order_line.erp_ordered_quantity, promise.ordered_quantity)
         )
        THEN TRUE ELSE FALSE
    END AS comparable_otif,
    CASE
        WHEN COALESCE(receipt_total.total_received_quantity, 0)
             >= COALESCE(order_line.erp_ordered_quantity, promise.ordered_quantity)
        THEN TRUE ELSE FALSE
    END AS received_in_full,
    CASE
        WHEN COALESCE(receipt_on_time.on_time_received_quantity, 0)
             >= COALESCE(order_line.erp_ordered_quantity, promise.ordered_quantity)
        THEN TRUE ELSE FALSE
    END AS on_time_in_full,
    CASE
        WHEN promise.promise_status = 'CANCELLED' THEN 'PROMISE_CANCELLED'
        WHEN COALESCE(receipt_on_time.on_time_received_quantity, 0)
             >= COALESCE(order_line.erp_ordered_quantity, promise.ordered_quantity)
        THEN 'DUE_ON_TIME_IN_FULL'
        WHEN promise.effective_deadline_at > GREATEST(
            promise.promise_recorded_at,
            COALESCE(order_line.order_line_updated_at, promise.promise_recorded_at),
            COALESCE(receipt_total.receipt_updated_at, promise.promise_recorded_at)
        ) THEN 'PROMISE_PENDING_NOT_DUE'
        WHEN COALESCE(receipt_total.total_received_quantity, 0)
             >= COALESCE(order_line.erp_ordered_quantity, promise.ordered_quantity)
        THEN 'DUE_LATE_FULL'
        WHEN COALESCE(receipt_total.total_received_quantity, 0) > 0
        THEN 'DUE_PARTIAL'
        ELSE 'DUE_OPEN'
    END AS otif_status
FROM promise
LEFT JOIN order_line
  ON order_line.tenant_id = promise.tenant_id
 AND order_line.purchase_order_line_id = promise.purchase_order_line_id
LEFT JOIN receipt_total
  ON receipt_total.tenant_id = promise.tenant_id
 AND receipt_total.purchase_order_line_id = promise.purchase_order_line_id
LEFT JOIN receipt_on_time
  ON receipt_on_time.tenant_id = promise.tenant_id
 AND receipt_on_time.purchase_order_line_id = promise.purchase_order_line_id;
