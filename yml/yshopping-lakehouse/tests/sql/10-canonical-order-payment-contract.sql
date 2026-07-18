SELECT 'canonical_order_version_continuity' AS check_name, COUNT(*) AS violations
FROM (
  SELECT tenant_id, order_id
  FROM yshopping_dwd.dwd_canonical_order_status_event
  GROUP BY tenant_id, order_id
  HAVING MIN(aggregate_version) <> 1 OR MAX(aggregate_version) <> COUNT(*)
) gap
UNION ALL
SELECT 'canonical_order_status_continuity', COUNT(*)
FROM (
  SELECT previous_status,
         LAG(current_status) OVER (PARTITION BY tenant_id, order_id ORDER BY aggregate_version) AS expected_previous,
         aggregate_version
  FROM yshopping_dwd.dwd_canonical_order_status_event
) history
WHERE (aggregate_version = 1 AND previous_status IS NOT NULL)
   OR (aggregate_version > 1 AND NOT previous_status <=> expected_previous)
UNION ALL
SELECT 'canonical_order_cancellation_transition', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_status_event
WHERE (current_status = 'CANCELLATION_PENDING'
       AND (cancellation_saga_id IS NULL OR cancellation_saga_id = ''
            OR NOT ((cancellation_mode = 'PAID_UNSHIPPED'
                     AND previous_status = 'PAYMENT_CONFIRMED'
                     AND pre_cancellation_status = 'PAYMENT_CONFIRMED')
                 OR ((cancellation_mode IS NULL OR cancellation_mode = 'UNPAID_RESERVED')
                     AND previous_status = 'INVENTORY_RESERVED'
                     AND pre_cancellation_status = 'INVENTORY_RESERVED'))))
   OR (current_status = 'CANCELLED' AND cancellation_saga_id IS NOT NULL
       AND (previous_status <> 'CANCELLATION_PENDING'
            OR NOT ((cancellation_mode = 'PAID_UNSHIPPED'
                     AND pre_cancellation_status = 'PAYMENT_CONFIRMED')
                 OR ((cancellation_mode IS NULL OR cancellation_mode = 'UNPAID_RESERVED')
                     AND pre_cancellation_status = 'INVENTORY_RESERVED'))))
UNION ALL
SELECT 'canonical_order_money_invariant', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_status_event
WHERE product_amount_minor < 0 OR shipping_amount_minor < 0 OR discount_amount_minor < 0
   OR payable_amount_minor <> product_amount_minor + shipping_amount_minor - discount_amount_minor
   OR currency_code <> 'CNY'
UNION ALL
SELECT 'canonical_order_item_amount_balance', COUNT(*)
FROM (
  SELECT event.tenant_id, event.event_id, event.product_amount_minor, SUM(item.line_amount_minor) AS item_amount_minor
  FROM yshopping_dwd.dwd_canonical_order_status_event event
  JOIN yshopping_dwd.dwd_canonical_order_item_event item ON item.event_id = event.event_id
  GROUP BY event.tenant_id, event.event_id, event.product_amount_minor
  HAVING event.product_amount_minor <> SUM(item.line_amount_minor)
) mismatch
UNION ALL
SELECT 'canonical_order_item_reservation_required', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_item_event
WHERE order_status IN ('INVENTORY_RESERVED', 'CANCELLATION_PENDING', 'PAYMENT_CONFIRMED', 'SHIPPED', 'COMPLETED', 'REFUNDED', 'RETURNED')
  AND (reservation_id IS NULL OR reservation_id = '')
UNION ALL
SELECT 'canonical_payment_version_continuity', COUNT(*)
FROM (
  SELECT tenant_id, payment_id
  FROM yshopping_dwd.dwd_canonical_payment_status_event
  GROUP BY tenant_id, payment_id
  HAVING MIN(aggregate_version) <> 1 OR MAX(aggregate_version) <> COUNT(*)
) gap
UNION ALL
SELECT 'canonical_payment_money_invariant', COUNT(*)
FROM yshopping_dwd.dwd_canonical_payment_status_event
WHERE payable_amount_minor < 0 OR captured_amount_minor < 0 OR refunded_amount_minor < 0
   OR captured_amount_minor > payable_amount_minor OR refunded_amount_minor > captured_amount_minor
   OR currency_code <> 'CNY'
UNION ALL
SELECT 'canonical_payment_order_match', COUNT(*)
FROM yshopping_dim.dim_canonical_payment_current payment
LEFT JOIN yshopping_dwd.dwd_canonical_order_status_event order_payment
  ON order_payment.tenant_id = payment.tenant_id
 AND order_payment.order_id = payment.order_id
 AND order_payment.payment_id = payment.payment_id
 AND order_payment.current_status = 'PAYMENT_CONFIRMED'
WHERE order_payment.order_id IS NULL
   OR order_payment.payable_amount_minor <> payment.payable_amount_minor
   OR order_payment.currency_code <> payment.currency_code
   OR order_payment.run_id <> payment.run_id
UNION ALL
SELECT 'canonical_payment_test_provider_boundary', COUNT(*)
FROM yshopping_dwd.dwd_canonical_payment_status_event
WHERE provider_code <> 'INTERNAL_TEST' OR test_mode <> TRUE
UNION ALL
SELECT 'canonical_commerce_terminal_reconciliation', COUNT(*)
FROM yshopping_ads.ads_canonical_commerce_readiness commerce
WHERE commerce.order_status = 'RETURNED' AND commerce.readiness_status <> 'RECONCILED'
  -- The legacy commerce slice expects a direct TRADE_ORDER SALE_RETURN. A governed
  -- AfterSale return is reconciled by its stricter, item-linked readiness model.
  AND NOT EXISTS (
    SELECT 1
    FROM yshopping_ads.ads_canonical_after_sale_readiness aftersale
    WHERE aftersale.tenant_id = commerce.tenant_id
      AND aftersale.order_id = commerce.order_id
      AND aftersale.readiness_status = 'RECONCILED'
  );
