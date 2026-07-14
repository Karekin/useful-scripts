CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_after_sale_readiness AS
SELECT resolution.*,
       CASE
         WHEN payload_after_sale_id <> after_sale_id
           OR payload_saga_id <> saga_id OR payload_refund_id <> after_sale_id
           OR case_after_sale_item_id <> after_sale_item_id
           OR return_after_sale_item_id <> after_sale_item_id
           OR inspection_after_sale_item_id <> after_sale_item_id
           OR refund_after_sale_item_id <> after_sale_item_id
           OR original_order_sku_id IS NULL OR original_order_sku_id <> canonical_sku_id
           OR original_order_quantity <> requested_quantity
           OR original_order_line_amount_minor <> approved_amount_minor
           OR original_listing_id <> listing_id OR original_offer_id <> offer_id
           OR requested_quantity <= 0
           OR received_quantity <> accepted_quantity + rejected_quantity
           OR accepted_quantity > received_quantity
           OR inventory_return_event_count > 1
           OR inventory_return_idempotency_count > 1
           OR refund_idempotency_count <> refund_event_count
           OR after_sale_idempotency_count <> after_sale_event_count
           OR return_fulfillment_idempotency_count <> return_fulfillment_event_count
           OR inventory_return_idempotency_count <> inventory_return_event_count
           OR refund_entitlement_amount_minor > approved_amount_minor
           OR refunded_amount_minor > approved_amount_minor
           OR refund_currency_code <> currency_code
           OR return_shipping_currency_code <> currency_code
           OR provider_code <> 'INTERNAL_TEST'
           OR reported_return_shipment_id <> return_shipment_id
           OR reported_canonical_sku_id <> canonical_sku_id
           OR reported_quantity <> requested_quantity
           OR reported_accepted_quantity <> accepted_quantity
           OR reported_returned_quantity <> inventory_return_quantity
           OR reported_uom_code <> return_uom_code
           OR reported_approved_amount_minor <> approved_amount_minor
           OR reported_refunded_amount_minor <> refunded_amount_minor
           OR reported_currency_code <> currency_code
           OR resolution_saga_id <> saga_id
         THEN 'INCONSISTENT'
         WHEN saga_status = 'COMPLETED'
           AND saga_version = 10 AND saga_event_count = 10
           AND after_sale_status = 'COMPLETED' AND after_sale_event_count = 4
           AND return_fulfillment_status = 'INSPECTION_ACCEPTED' AND return_fulfillment_event_count = 5
           AND inspection_result = 'ACCEPTED' AND rejected_quantity = 0
           AND requested_quantity = accepted_quantity
           AND accepted_quantity = inventory_return_quantity
           AND refund_status = 'SUCCEEDED' AND refund_event_count = 2
           AND approved_amount_minor = refunded_amount_minor
           AND refunded_amount_minor = payment_refunded_amount_minor
           AND payment_status = 'REFUNDED' AND order_status = 'RETURNED'
           AND reported_order_version = current_order_version
           AND inventory_ledger_transaction_id IS NOT NULL
           AND inventory_operation_id IS NOT NULL
           AND payment_refund_transaction_id = refund_transaction_id
           AND order_refund_operation_id IS NOT NULL AND order_return_operation_id IS NOT NULL
           AND get_json_bool(checkpoints, '$.inventory_returned') = TRUE
           AND get_json_bool(checkpoints, '$.payment_refunded') = TRUE
           AND get_json_bool(checkpoints, '$.order_refund_confirmed') = TRUE
           AND get_json_bool(checkpoints, '$.order_returned') = TRUE
           AND recorded_order_valid = TRUE
         THEN 'RECONCILED'
         WHEN saga_status = 'COMPLETED' THEN 'INCONSISTENT'
         WHEN saga_status = 'MANUAL_REVIEW' THEN 'RECOVERY_REQUIRED'
         WHEN saga_status = 'RETRY_SCHEDULED' THEN 'RECOVERY_PENDING'
         ELSE 'IN_PROGRESS'
       END AS readiness_status,
       CASE
         WHEN saga_status = 'COMPLETED' AND (retry_event_count > 0 OR manual_review_event_count > 0)
           THEN 'RECOVERED'
         WHEN saga_status = 'MANUAL_REVIEW' THEN 'REQUIRED'
         WHEN saga_status = 'RETRY_SCHEDULED' THEN 'PENDING'
         ELSE 'NOT_REQUIRED'
       END AS recovery_status
FROM yshopping_dws.dws_canonical_after_sale_resolution_current resolution;
