SELECT 'canonical_aftersales_event_version_continuity' AS check_name, COUNT(*) AS violations
FROM (
  SELECT event_type, tenant_id, aggregate_id
  FROM yshopping_dwd.dwd_domain_event
  WHERE event_type IN ('after_sale.status.changed', 'after_sale.refund.status.changed',
                       'return_fulfillment.status.changed', 'return_fulfillment.inspection.decided',
                       'after_sale.resolution_saga.status.changed')
  GROUP BY event_type, tenant_id, aggregate_id
  HAVING MIN(aggregate_version) <> 1 OR MAX(aggregate_version) <> COUNT(*)
) gap
UNION ALL
SELECT 'canonical_aftersales_event_id_unique', COUNT(*)
FROM (
  SELECT event_id
  FROM yshopping_dwd.dwd_domain_event
  WHERE event_type IN ('after_sale.status.changed', 'after_sale.refund.status.changed',
                       'return_fulfillment.status.changed', 'return_fulfillment.inspection.decided',
                       'after_sale.resolution_saga.status.changed')
  GROUP BY event_id HAVING COUNT(*) > 1
) duplicate_event
UNION ALL
SELECT 'canonical_aftersales_replay_idempotency_unique', COUNT(*)
FROM (
  SELECT tenant_id, event_type, idempotency_key
  FROM yshopping_dwd.dwd_domain_event
  WHERE event_type IN ('after_sale.status.changed', 'after_sale.refund.status.changed',
                       'return_fulfillment.status.changed', 'return_fulfillment.inspection.decided',
                       'after_sale.resolution_saga.status.changed')
  GROUP BY tenant_id, event_type, idempotency_key HAVING COUNT(*) > 1
) duplicate_replay
UNION ALL
SELECT 'canonical_after_sale_status_continuity', COUNT(*)
FROM (
  SELECT previous_status,
         LAG(current_status) OVER (PARTITION BY tenant_id, after_sale_id ORDER BY aggregate_version) expected_previous,
         aggregate_version
  FROM yshopping_dwd.dwd_canonical_after_sale_status_event
) history
WHERE (aggregate_version = 1 AND previous_status IS NOT NULL)
   OR (aggregate_version > 1 AND NOT previous_status <=> expected_previous)
UNION ALL
SELECT 'canonical_after_sale_allowed_transition', COUNT(*)
FROM yshopping_dwd.dwd_canonical_after_sale_status_event
WHERE NOT (
       (previous_status IS NULL AND current_status = 'REQUESTED')
    OR (previous_status = 'REQUESTED' AND current_status = 'APPROVED')
    OR (previous_status = 'APPROVED' AND current_status = 'RESOLUTION_PENDING')
    OR (previous_status = 'RESOLUTION_PENDING' AND current_status = 'COMPLETED')
)
UNION ALL
SELECT 'canonical_after_sale_refund_allowed_transition', COUNT(*)
FROM yshopping_dwd.dwd_canonical_after_sale_refund_status_event
WHERE NOT (
       (aggregate_version = 1 AND previous_status = 'NOT_REQUESTED' AND current_status = 'REQUESTED')
    OR (aggregate_version = 2 AND previous_status = 'REQUESTED' AND current_status = 'SUCCEEDED')
);

SELECT 'canonical_return_fulfillment_status_continuity', COUNT(*)
FROM (
  SELECT previous_status,
         LAG(current_status) OVER (PARTITION BY tenant_id, return_fulfillment_id ORDER BY aggregate_version)
           expected_previous,
         aggregate_version
  FROM yshopping_dwd.dwd_canonical_return_fulfillment_status_event
) history
WHERE (aggregate_version = 1 AND previous_status IS NOT NULL)
   OR (aggregate_version > 1 AND NOT previous_status <=> expected_previous)
UNION ALL
SELECT 'canonical_return_fulfillment_allowed_transition', COUNT(*)
FROM yshopping_dwd.dwd_canonical_return_fulfillment_status_event
WHERE NOT (
       (previous_status IS NULL AND current_status = 'CREATED')
    OR (previous_status = 'CREATED' AND current_status = 'HANDED_OVER')
    OR (previous_status = 'HANDED_OVER' AND current_status = 'IN_TRANSIT')
    OR (previous_status = 'IN_TRANSIT' AND current_status = 'RECEIVED')
    OR (previous_status = 'RECEIVED' AND current_status = 'INSPECTION_ACCEPTED')
)
UNION ALL
SELECT 'canonical_after_sale_saga_status_continuity', COUNT(*)
FROM (
  SELECT previous_status,
         LAG(current_status) OVER (PARTITION BY tenant_id, saga_id ORDER BY aggregate_version)
           expected_previous,
         aggregate_version
  FROM yshopping_dwd.dwd_canonical_after_sale_resolution_saga_event
) history
WHERE (aggregate_version = 1 AND previous_status IS NOT NULL)
   OR (aggregate_version > 1 AND NOT previous_status <=> expected_previous)
UNION ALL
SELECT 'canonical_after_sale_saga_allowed_transition', COUNT(*)
FROM yshopping_dwd.dwd_canonical_after_sale_resolution_saga_event
WHERE NOT (
       (previous_status IS NULL AND current_status = 'REQUESTED')
    OR (previous_status = 'REQUESTED' AND current_status = 'RETURNING_INVENTORY')
    OR (previous_status = 'RETURNING_INVENTORY' AND current_status IN ('INVENTORY_RETURNED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'INVENTORY_RETURNED' AND current_status IN ('REVERSING_BENEFITS', 'REFUNDING_PAYMENT'))
    OR (previous_status = 'REVERSING_BENEFITS' AND current_status IN ('BENEFITS_REVERSED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'BENEFITS_REVERSED' AND current_status = 'REFUNDING_PAYMENT')
    OR (previous_status = 'REFUNDING_PAYMENT' AND current_status IN ('PAYMENT_REFUNDED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'PAYMENT_REFUNDED' AND current_status = 'CONFIRMING_ORDER_REFUND')
    OR (previous_status = 'CONFIRMING_ORDER_REFUND' AND current_status IN ('ORDER_REFUNDED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'ORDER_REFUNDED' AND current_status = 'RETURNING_ORDER')
    OR (previous_status = 'RETURNING_ORDER' AND current_status IN ('ORDER_RETURNED', 'RETRY_SCHEDULED', 'MANUAL_REVIEW'))
    OR (previous_status = 'ORDER_RETURNED' AND current_status = 'COMPLETED')
    OR (previous_status = 'RETRY_SCHEDULED' AND current_status IN ('RETURNING_INVENTORY', 'REVERSING_BENEFITS', 'REFUNDING_PAYMENT', 'CONFIRMING_ORDER_REFUND', 'RETURNING_ORDER', 'MANUAL_REVIEW'))
    OR (previous_status = 'MANUAL_REVIEW' AND current_status = 'RETRY_SCHEDULED')
)
UNION ALL
SELECT 'canonical_after_sale_saga_terminal_shape', COUNT(*)
FROM yshopping_dwd.dwd_canonical_after_sale_resolution_saga_event
WHERE current_status = 'COMPLETED' AND (
      aggregate_version < IF(benefit_amount_minor = 0, 10, 12)
   OR MOD(aggregate_version - IF(benefit_amount_minor = 0, 10, 12), 2) <> 0
   OR active_step <> 'NONE' OR step_ordinal <> IF(benefit_amount_minor = 0, 5, 6)
   OR accepted_quantity <> quantity OR returned_quantity <> quantity
   OR approved_amount_minor <> refunded_amount_minor
   OR inventory_operation_id IS NULL OR inventory_ledger_transaction_id IS NULL
   OR payment_refund_transaction_id IS NULL OR order_refund_operation_id IS NULL
   OR order_return_operation_id IS NULL OR order_version IS NULL
   OR get_json_bool(checkpoints, '$.inventory_returned') <> TRUE
   OR get_json_bool(checkpoints, '$.payment_refunded') <> TRUE
   OR get_json_bool(checkpoints, '$.order_refund_confirmed') <> TRUE
   OR get_json_bool(checkpoints, '$.order_returned') <> TRUE
   OR error_code IS NOT NULL OR error_message IS NOT NULL OR next_retry_at IS NOT NULL
);

SELECT 'canonical_aftersales_exact_aggregate_identity', COUNT(*)
FROM (
  SELECT event_id FROM yshopping_dwd.dwd_canonical_after_sale_status_event
   WHERE after_sale_id <> payload_after_sale_id OR after_sale_item_id IS NULL
  UNION ALL
  SELECT event_id FROM yshopping_dwd.dwd_canonical_after_sale_refund_status_event
   WHERE refund_id IS NULL OR payload_refund_id <> after_sale_id
      OR after_sale_id IS NULL OR after_sale_item_id IS NULL
  UNION ALL
  SELECT event_id FROM yshopping_dwd.dwd_canonical_return_fulfillment_status_event
   WHERE return_fulfillment_id IS NULL OR after_sale_id IS NULL OR after_sale_item_id IS NULL
  UNION ALL
  SELECT event_id FROM yshopping_dwd.dwd_canonical_return_fulfillment_inspection_event
   WHERE inspection_id IS NULL OR return_fulfillment_id IS NULL OR after_sale_id IS NULL
      OR after_sale_item_id IS NULL
) invalid_identity
UNION ALL
SELECT 'canonical_aftersales_quantity_conservation', COUNT(*)
FROM yshopping_dwd.dwd_canonical_return_fulfillment_inspection_event
WHERE received_quantity < 0 OR accepted_quantity < 0 OR rejected_quantity < 0
   OR received_quantity <> accepted_quantity + rejected_quantity
UNION ALL
SELECT 'canonical_aftersales_money_entitlement', COUNT(*)
FROM yshopping_dwd.dwd_canonical_after_sale_refund_status_event
WHERE approved_amount_minor < 0 OR refunded_amount_minor < 0
   OR refunded_amount_minor > approved_amount_minor
   OR (current_status = 'SUCCEEDED' AND refunded_amount_minor <> approved_amount_minor)
UNION ALL
SELECT 'canonical_aftersales_return_shipping_money', COUNT(*)
FROM yshopping_dwd.dwd_canonical_return_fulfillment_status_event
WHERE return_shipping_amount_minor <> 0 OR currency_code <> 'CNY';

SELECT 'canonical_aftersales_exact_cross_fact_links', COUNT(*)
FROM yshopping_dws.dws_canonical_after_sale_resolution_current
WHERE after_sale_id IS NULL OR order_id IS NULL OR order_item_id IS NULL OR payment_id IS NULL
   OR after_sale_item_id IS NULL OR case_after_sale_item_id <> after_sale_item_id
   OR return_after_sale_item_id <> after_sale_item_id
   OR inspection_after_sale_item_id <> after_sale_item_id
   OR refund_after_sale_item_id <> after_sale_item_id
   OR original_order_sku_id IS NULL OR original_order_sku_id <> canonical_sku_id
   OR original_order_quantity <> requested_quantity
   OR original_order_line_amount_minor <> original_order_discount_amount_minor + original_order_net_amount_minor
   OR original_order_net_amount_minor <> approved_amount_minor
   OR original_listing_id <> listing_id OR original_offer_id <> offer_id
   OR return_fulfillment_id IS NULL OR inspection_id IS NULL
   OR requested_quantity <> received_quantity
   OR approved_amount_minor <> refund_entitlement_amount_minor
   OR currency_code <> refund_currency_code OR currency_code <> return_shipping_currency_code
   OR payload_saga_id <> saga_id OR payload_refund_id <> after_sale_id
   OR reported_return_shipment_id <> return_shipment_id
   OR reported_canonical_sku_id <> canonical_sku_id
   OR reported_quantity <> requested_quantity OR reported_accepted_quantity <> accepted_quantity
   OR reported_returned_quantity <> inventory_return_quantity
   OR reported_uom_code <> return_uom_code
   OR reported_approved_amount_minor <> approved_amount_minor
   OR reported_refunded_amount_minor <> refunded_amount_minor
   OR reported_currency_code <> currency_code
UNION ALL
SELECT 'canonical_aftersales_effect_recorded_order', COUNT(*)
FROM yshopping_dws.dws_canonical_after_sale_resolution_current
WHERE saga_status = 'COMPLETED' AND recorded_order_valid <> TRUE
UNION ALL
SELECT 'canonical_aftersales_cancellation_return_separation', COUNT(*)
FROM (
  SELECT after_sale.tenant_id, after_sale.saga_id
  FROM yshopping_dim.dim_canonical_after_sale_resolution_saga_current after_sale
  JOIN yshopping_dim.dim_canonical_order_cancellation_saga_current cancellation
    ON cancellation.tenant_id = after_sale.tenant_id AND cancellation.saga_id = after_sale.saga_id
  UNION ALL
  SELECT tenant_id, saga_id
  FROM yshopping_dws.dws_canonical_after_sale_resolution_current
  WHERE saga_status = 'COMPLETED' AND order_status = 'CANCELLED'
) conflated_flow
UNION ALL
SELECT 'canonical_aftersales_pii_isolation', COUNT(*)
FROM yshopping_dwd.dwd_domain_event
WHERE event_type IN ('after_sale.status.changed', 'after_sale.refund.status.changed',
                     'return_fulfillment.status.changed', 'return_fulfillment.inspection.decided',
                     'after_sale.resolution_saga.status.changed')
  AND (LOWER(CAST(payload AS STRING)) LIKE '%buyer_phone%'
    OR LOWER(CAST(payload AS STRING)) LIKE '%receiver_phone%'
    OR LOWER(CAST(payload AS STRING)) LIKE '%receiver_name%'
    OR LOWER(CAST(payload AS STRING)) LIKE '%full_address%')
UNION ALL
SELECT 'canonical_aftersales_buyer_daily_nonnegative', COUNT(*)
FROM yshopping_dws.dws_canonical_aftersales_buyer_1d
WHERE tenant_id <= 0 OR buyer_id IS NULL OR business_date IS NULL
   OR requested_case_count < 0 OR approved_case_count < 0 OR completed_case_count < 0
   OR requested_quantity < 0 OR approved_refund_amount_minor < 0 OR refunded_amount_minor < 0
   OR return_shipping_amount_minor < 0
UNION ALL
SELECT 'canonical_aftersales_completed_reconciled', COUNT(*)
FROM yshopping_ads.ads_canonical_after_sale_readiness
WHERE saga_status = 'COMPLETED' AND readiness_status <> 'RECONCILED'
UNION ALL
SELECT 'canonical_aftersales_recovery_not_reconciled', COUNT(*)
FROM yshopping_ads.ads_canonical_after_sale_readiness
WHERE saga_status IN ('RETRY_SCHEDULED', 'MANUAL_REVIEW') AND readiness_status = 'RECONCILED';
