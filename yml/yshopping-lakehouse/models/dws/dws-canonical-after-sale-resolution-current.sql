CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_after_sale_resolution_current AS
WITH inspection AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, inspection_id ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
    ) AS row_num
    FROM yshopping_dwd.dwd_canonical_return_fulfillment_inspection_event
), inventory_return AS (
    SELECT tenant_id, business_id AS after_sale_id, business_item_id AS after_sale_item_id,
           COUNT(*) AS inventory_return_event_count,
           COUNT(DISTINCT idempotency_key) AS inventory_return_idempotency_count,
           SUM(delta_on_hand_quantity) AS inventory_return_quantity,
           MAX(recorded_at) AS inventory_returned_recorded_at
    FROM yshopping_dwd.dwd_canonical_inventory_movement
    WHERE movement_type = 'SALE_RETURN' AND business_type = 'AFTER_SALE_RETURN'
    GROUP BY tenant_id, business_id, business_item_id
), case_events AS (
    SELECT tenant_id, after_sale_id, COUNT(*) AS after_sale_event_count,
           COUNT(DISTINCT idempotency_key) AS after_sale_idempotency_count,
           MAX(IF(current_status = 'COMPLETED', recorded_at, NULL)) AS after_sale_completed_recorded_at
    FROM yshopping_dwd.dwd_canonical_after_sale_status_event
    GROUP BY tenant_id, after_sale_id
), return_events AS (
    SELECT tenant_id, return_fulfillment_id, COUNT(*) AS return_fulfillment_event_count,
           COUNT(DISTINCT idempotency_key) AS return_fulfillment_idempotency_count,
           MAX(IF(current_status = 'INSPECTION_ACCEPTED', recorded_at, NULL)) AS return_accepted_recorded_at
    FROM yshopping_dwd.dwd_canonical_return_fulfillment_status_event
    GROUP BY tenant_id, return_fulfillment_id
), refund_events AS (
    SELECT tenant_id, refund_id, COUNT(*) AS refund_event_count,
           COUNT(DISTINCT idempotency_key) AS refund_idempotency_count,
           MAX(IF(current_status = 'SUCCEEDED', recorded_at, NULL)) AS refund_succeeded_recorded_at
    FROM yshopping_dwd.dwd_canonical_after_sale_refund_status_event
    GROUP BY tenant_id, refund_id
)
SELECT
    saga.tenant_id, saga.run_id, saga.saga_id, saga.after_sale_id, saga.after_sale_item_id,
    saga.order_id, saga.order_item_id,
    saga.payment_id, saga.return_fulfillment_id, saga.inspection_id,
    saga.payload_saga_id, saga.return_shipment_id AS reported_return_shipment_id,
    saga.canonical_sku_id AS reported_canonical_sku_id, saga.quantity AS reported_quantity,
    saga.accepted_quantity AS reported_accepted_quantity,
    saga.returned_quantity AS reported_returned_quantity, saga.uom_code AS reported_uom_code,
    saga.approved_amount_minor AS reported_approved_amount_minor,
    saga.gross_amount_minor AS reported_gross_amount_minor,
    saga.benefit_amount_minor AS reported_benefit_amount_minor,
    saga.net_amount_minor AS reported_net_amount_minor,
    saga.refunded_amount_minor AS reported_refunded_amount_minor,
    saga.currency_code AS reported_currency_code, saga.checkpoints,
    saga.schema_version AS saga_schema_version,
    saga.aggregate_version AS saga_version, saga.saga_event_count, saga.retry_event_count,
    saga.manual_review_event_count, saga.max_attempt, saga.previous_status AS saga_previous_status,
    saga.current_status AS saga_status, saga.active_step, saga.step_ordinal, saga.attempt,
    after_sale.payload_after_sale_id, after_sale.resolution_saga_id,
    after_sale.after_sale_item_id AS case_after_sale_item_id,
    after_sale.after_sale_no, after_sale.after_sale_type, after_sale.reason_code,
    after_sale.responsibility, after_sale.reason, after_sale.buyer_id,
    after_sale.listing_id, after_sale.listing_offer_id AS offer_id,
    after_sale.canonical_sku_id, after_sale.quantity AS requested_quantity,
    after_sale.approved_amount_minor, after_sale.currency_code, after_sale.current_status AS after_sale_status,
    order_item.canonical_sku_id AS original_order_sku_id,
    order_item.quantity AS original_order_quantity,
    order_item.line_amount_minor AS original_order_line_amount_minor,
    COALESCE(order_benefit.discount_amount_minor, 0) AS original_order_discount_amount_minor,
    COALESCE(order_benefit.net_amount_minor, order_item.line_amount_minor) AS original_order_net_amount_minor,
    order_item.listing_id AS original_listing_id,
    order_item.listing_offer_id AS original_offer_id,
    COALESCE(case_events.after_sale_event_count, 0) AS after_sale_event_count,
    COALESCE(case_events.after_sale_idempotency_count, 0) AS after_sale_idempotency_count,
    return_fulfillment.current_status AS return_fulfillment_status,
    return_fulfillment.after_sale_item_id AS return_after_sale_item_id,
    return_fulfillment.warehouse_id, return_fulfillment.owner_id, return_fulfillment.return_shipment_id,
    return_fulfillment.carrier_code, return_fulfillment.waybill_no,
    return_fulfillment.return_shipping_amount_minor,
    return_fulfillment.currency_code AS return_shipping_currency_code,
    return_fulfillment.uom_code AS return_uom_code,
    COALESCE(return_events.return_fulfillment_event_count, 0) AS return_fulfillment_event_count,
    COALESCE(return_events.return_fulfillment_idempotency_count, 0) AS return_fulfillment_idempotency_count,
    inspection.after_sale_item_id AS inspection_after_sale_item_id,
    inspection.inspection_result, inspection.quality_status, inspection.received_quantity,
    inspection.accepted_quantity, inspection.rejected_quantity,
    refund.refund_id, refund.payload_refund_id, refund.after_sale_item_id AS refund_after_sale_item_id,
    refund.current_status AS refund_status, refund.refund_transaction_id,
    refund.provider_code, refund.approved_amount_minor AS refund_entitlement_amount_minor,
    refund.refunded_amount_minor, refund.currency_code AS refund_currency_code,
    refund.gross_amount_minor AS refund_gross_amount_minor,
    refund.benefit_amount_minor AS refund_benefit_amount_minor,
    refund.net_amount_minor AS refund_net_amount_minor,
    COALESCE(refund_events.refund_event_count, 0) AS refund_event_count,
    COALESCE(refund_events.refund_idempotency_count, 0) AS refund_idempotency_count,
    COALESCE(inventory_return.inventory_return_event_count, 0) AS inventory_return_event_count,
    COALESCE(inventory_return.inventory_return_idempotency_count, 0) AS inventory_return_idempotency_count,
    COALESCE(inventory_return.inventory_return_quantity, 0) AS inventory_return_quantity,
    order_current.current_status AS order_status, order_current.aggregate_version AS current_order_version,
    payment.current_status AS payment_status, payment.refunded_amount_minor AS payment_refunded_amount_minor,
    saga.inventory_operation_id, saga.inventory_ledger_transaction_id,
    saga.benefit_reversal_status, saga.benefit_reversal_batch_id,
    saga.benefit_reversal_amount_minor,
    benefit_reversal.benefit_reversal_count,
    benefit_reversal.benefit_reversal_idempotency_count,
    benefit_reversal.benefit_reversal_amount_minor AS recorded_benefit_reversal_amount_minor,
    benefit_reversal.funding_reversal_count,
    benefit_reversal.funding_reversal_amount_minor,
    benefit_reversal.allocation_reversal_mismatch_count,
    benefit_reversal.entitlement_effect_mismatch_count,
    benefit_reversal.funding_reversal_mismatch_count,
    saga.payment_refund_transaction_id, saga.order_refund_operation_id, saga.order_return_operation_id,
    saga.order_version AS reported_order_version, saga.error_code, saga.error_message, saga.next_retry_at,
    return_events.return_accepted_recorded_at,
    inventory_return.inventory_returned_recorded_at,
    benefit_reversal.benefit_reversal_recorded_at,
    refund_events.refund_succeeded_recorded_at,
    order_current.recorded_at AS order_returned_recorded_at,
    case_events.after_sale_completed_recorded_at,
    return_events.return_accepted_recorded_at IS NOT NULL
      AND inventory_return.inventory_returned_recorded_at IS NOT NULL
      AND (saga.benefit_amount_minor = 0 OR benefit_reversal.benefit_reversal_recorded_at IS NOT NULL)
      AND refund_events.refund_succeeded_recorded_at IS NOT NULL
      AND order_current.recorded_at IS NOT NULL
      AND case_events.after_sale_completed_recorded_at IS NOT NULL
      AND return_events.return_accepted_recorded_at <= inventory_return.inventory_returned_recorded_at
      AND (saga.benefit_amount_minor = 0
        OR inventory_return.inventory_returned_recorded_at <= benefit_reversal.benefit_reversal_recorded_at)
      AND (saga.benefit_amount_minor = 0
        OR benefit_reversal.benefit_reversal_recorded_at <= refund_events.refund_succeeded_recorded_at)
      AND inventory_return.inventory_returned_recorded_at <= refund_events.refund_succeeded_recorded_at
      AND refund_events.refund_succeeded_recorded_at <= order_current.recorded_at
      AND order_current.recorded_at <= case_events.after_sale_completed_recorded_at AS recorded_order_valid,
    GREATEST(saga.recorded_at, after_sale.recorded_at, return_fulfillment.recorded_at,
             inspection.recorded_at, COALESCE(refund.recorded_at, saga.recorded_at)) AS data_freshness_at
FROM yshopping_dim.dim_canonical_after_sale_resolution_saga_current saga
JOIN yshopping_dim.dim_canonical_after_sale_current after_sale
  ON after_sale.tenant_id = saga.tenant_id AND after_sale.after_sale_id = saga.after_sale_id
 AND after_sale.after_sale_item_id = saga.after_sale_item_id
JOIN yshopping_dim.dim_canonical_return_fulfillment_current return_fulfillment
 ON return_fulfillment.tenant_id = saga.tenant_id
 AND return_fulfillment.return_fulfillment_id = saga.return_fulfillment_id
 AND return_fulfillment.after_sale_item_id = saga.after_sale_item_id
LEFT JOIN inspection
  ON inspection.tenant_id = saga.tenant_id AND inspection.inspection_id = saga.inspection_id
 AND inspection.after_sale_item_id = saga.after_sale_item_id
 AND inspection.row_num = 1
LEFT JOIN yshopping_dim.dim_canonical_after_sale_refund_current refund
  ON refund.tenant_id = saga.tenant_id AND refund.after_sale_id = saga.after_sale_id
 AND refund.after_sale_item_id = saga.after_sale_item_id
LEFT JOIN case_events
  ON case_events.tenant_id = saga.tenant_id AND case_events.after_sale_id = saga.after_sale_id
LEFT JOIN return_events
  ON return_events.tenant_id = saga.tenant_id
 AND return_events.return_fulfillment_id = saga.return_fulfillment_id
LEFT JOIN refund_events
  ON refund_events.tenant_id = refund.tenant_id AND refund_events.refund_id = refund.refund_id
LEFT JOIN inventory_return
  ON inventory_return.tenant_id = saga.tenant_id AND inventory_return.after_sale_id = saga.after_sale_id
 AND inventory_return.after_sale_item_id = saga.after_sale_item_id
LEFT JOIN yshopping_dim.dim_canonical_order_current order_current
  ON order_current.tenant_id = saga.tenant_id AND order_current.order_id = saga.order_id
LEFT JOIN yshopping_dws.dws_canonical_order_item_current order_item
  ON order_item.tenant_id = saga.tenant_id AND order_item.order_id = saga.order_id
 AND order_item.order_item_id = saga.order_item_id
LEFT JOIN yshopping_dws.dws_canonical_order_item_benefit_current order_benefit
  ON order_benefit.tenant_id = saga.tenant_id AND order_benefit.order_id = saga.order_id
 AND order_benefit.order_item_id = saga.order_item_id
LEFT JOIN yshopping_dws.dws_canonical_after_sale_benefit_reversal_current benefit_reversal
  ON benefit_reversal.tenant_id = saga.tenant_id
 AND benefit_reversal.after_sale_id = saga.after_sale_id
 AND benefit_reversal.reversal_batch_id = saga.benefit_reversal_batch_id
LEFT JOIN yshopping_dim.dim_canonical_payment_current payment
  ON payment.tenant_id = saga.tenant_id AND payment.payment_id = saga.payment_id;
