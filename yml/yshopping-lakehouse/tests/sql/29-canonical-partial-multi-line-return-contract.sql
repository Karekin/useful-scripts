SELECT 'canonical_order_return_settlement_event_id_duplicate' AS check_name, COUNT(*) AS violations
FROM (
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event
  GROUP BY event_id HAVING COUNT(*) <> 1
) duplicate_event
UNION ALL
SELECT 'canonical_order_return_settlement_effect_duplicate', COUNT(*)
FROM (
  SELECT tenant_id, settlement_effect_id
  FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event
  GROUP BY tenant_id, settlement_effect_id HAVING COUNT(*) <> 1
) duplicate_effect
UNION ALL
SELECT 'canonical_order_return_settlement_idempotency_duplicate', COUNT(*)
FROM (
  SELECT tenant_id, idempotency_key
  FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event
  GROUP BY tenant_id, idempotency_key HAVING COUNT(*) <> 1
) duplicate_replay;

SELECT 'canonical_order_return_settlement_version_gap', COUNT(*)
FROM (
  SELECT tenant_id, order_id
  FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event
  GROUP BY tenant_id, order_id
  HAVING MIN(aggregate_version) <> 1 OR MAX(aggregate_version) <> COUNT(*)
) version_gap
UNION ALL
SELECT 'canonical_order_return_settlement_identity_invalid', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event
WHERE aggregate_order_id <> order_id
   OR settlement_effect_id IS NULL OR after_sale_id IS NULL OR after_sale_item_id IS NULL
   OR order_id IS NULL OR order_item_id IS NULL
   OR quantity <= 0 OR item_ordered_quantity <= 0 OR order_total_quantity <= 0
   OR item_returned_quantity <= 0 OR item_returned_quantity > item_ordered_quantity
   OR order_returned_quantity <= 0 OR order_returned_quantity > order_total_quantity
   OR gross_amount_minor <> benefit_amount_minor + net_amount_minor
   OR net_amount_minor <= 0 OR refunded_net_amount_minor <= 0
   OR reversed_benefit_amount_minor < 0
   OR inventory_operation_id IS NULL OR inventory_ledger_transaction_id IS NULL
   OR payment_refund_transaction_id IS NULL
   OR NOT ((benefit_amount_minor = 0 AND benefit_reversal_batch_id IS NULL)
       OR (benefit_amount_minor > 0 AND benefit_reversal_batch_id IS NOT NULL))
   OR NOT ((full_return = TRUE AND settlement_status = 'FULL'
            AND order_returned_quantity = order_total_quantity)
       OR (full_return = FALSE AND settlement_status = 'PARTIAL'
            AND order_returned_quantity < order_total_quantity));

SELECT 'canonical_order_return_settlement_cumulative_delta_invalid', COUNT(*)
FROM (
  SELECT settlement.*,
         COALESCE(LAG(order_returned_quantity) OVER (
             PARTITION BY tenant_id, order_id ORDER BY aggregate_version), 0) AS prior_order_quantity,
         COALESCE(LAG(refunded_net_amount_minor) OVER (
             PARTITION BY tenant_id, order_id ORDER BY aggregate_version), 0) AS prior_refunded_net,
         COALESCE(LAG(reversed_benefit_amount_minor) OVER (
             PARTITION BY tenant_id, order_id ORDER BY aggregate_version), 0) AS prior_reversed_benefit,
         COALESCE(LAG(item_returned_quantity) OVER (
             PARTITION BY tenant_id, order_item_id ORDER BY aggregate_version), 0) AS prior_item_quantity
  FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event settlement
) history
WHERE order_returned_quantity <> prior_order_quantity + quantity
   OR refunded_net_amount_minor <> prior_refunded_net + net_amount_minor
   OR reversed_benefit_amount_minor <> prior_reversed_benefit + benefit_amount_minor
   OR item_returned_quantity <> prior_item_quantity + quantity
UNION ALL
SELECT 'canonical_order_return_settlement_order_total_invalid', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event settlement
LEFT JOIN (
  SELECT tenant_id, order_id, SUM(quantity) AS expected_total_quantity
  FROM yshopping_dws.dws_canonical_order_item_current
  GROUP BY tenant_id, order_id
) item_total
  ON item_total.tenant_id = settlement.tenant_id AND item_total.order_id = settlement.order_id
WHERE item_total.expected_total_quantity IS NULL
   OR settlement.order_total_quantity <> item_total.expected_total_quantity;

SELECT 'canonical_order_return_settlement_saga_link_invalid', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event settlement
LEFT JOIN yshopping_dim.dim_canonical_after_sale_resolution_saga_current saga
  ON saga.tenant_id = settlement.tenant_id
 AND saga.after_sale_id = settlement.after_sale_id
 AND saga.order_settlement_effect_id = settlement.settlement_effect_id
WHERE saga.saga_id IS NULL
   OR saga.schema_version <> 3
   OR saga.after_sale_item_id <> settlement.after_sale_item_id
   OR saga.order_id <> settlement.order_id
   OR saga.order_item_id <> settlement.order_item_id
   OR saga.quantity <> settlement.quantity
   OR saga.gross_amount_minor <> settlement.gross_amount_minor
   OR saga.benefit_amount_minor <> settlement.benefit_amount_minor
   OR saga.net_amount_minor <> settlement.net_amount_minor
   OR saga.inventory_operation_id <> settlement.inventory_operation_id
   OR saga.inventory_ledger_transaction_id <> settlement.inventory_ledger_transaction_id
   OR saga.payment_refund_transaction_id <> settlement.payment_refund_transaction_id
   OR NOT (saga.benefit_reversal_batch_id <=> settlement.benefit_reversal_batch_id)
   OR saga.order_settlement_version <> settlement.aggregate_version
   OR saga.order_return_full <> settlement.full_return
UNION ALL
SELECT 'canonical_order_return_settlement_payment_link_invalid', COUNT(*)
FROM yshopping_dwd.dwd_canonical_order_after_sale_settlement_event settlement
LEFT JOIN yshopping_dwd.dwd_canonical_payment_status_event payment
  ON payment.tenant_id = settlement.tenant_id
 AND payment.transaction_id = settlement.payment_refund_transaction_id
 AND payment.transaction_type = 'REFUND'
WHERE payment.event_id IS NULL OR payment.schema_version <> 3
   OR payment.order_id <> settlement.order_id
   OR payment.refund_amount_minor <> settlement.net_amount_minor
   OR payment.refunded_amount_minor <> settlement.refunded_net_amount_minor
   OR payment.remaining_refundable_amount_minor
        <> payment.captured_amount_minor - payment.refunded_amount_minor
   OR NOT ((settlement.full_return = TRUE AND payment.current_status = 'REFUNDED'
            AND payment.remaining_refundable_amount_minor = 0)
       OR (settlement.full_return = FALSE AND payment.current_status = 'PARTIALLY_REFUNDED'
            AND payment.remaining_refundable_amount_minor > 0));

SELECT 'canonical_partial_multi_line_return_completed_unreconciled', COUNT(*)
FROM yshopping_ads.ads_canonical_after_sale_readiness
WHERE saga_status = 'COMPLETED' AND readiness_status <> 'RECONCILED';
