CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_merchant_cancellation_current AS
WITH completed_saga AS (
    SELECT *
    FROM yshopping_dim.dim_canonical_order_cancellation_saga_current
    WHERE current_status = 'COMPLETED'
), item_scope AS (
    SELECT
        tenant_id,
        order_id,
        COUNT(DISTINCT shop_id) AS distinct_shop_count,
        MAX(shop_id) AS shop_id,
        COUNT(DISTINCT channel_code) AS distinct_channel_count,
        MAX(channel_code) AS channel_code,
        COUNT(DISTINCT canonical_sku_id) AS distinct_sku_count
    FROM yshopping_dws.dws_canonical_order_item_current
    GROUP BY tenant_id, order_id
)
SELECT
    saga.tenant_id,
    saga.run_id,
    saga.saga_id,
    saga.order_id,
    saga.order_no,
    saga.aggregate_version,
    saga.cancellation_mode,
    saga.previous_status,
    saga.current_status AS saga_status,
    saga.order_status_at_request,
    saga.responsibility_party,
    saga.responsibility_code,
    COALESCE(saga.counts_toward_paid_cancellation_rate, FALSE) AS counts_toward_paid_cancellation_rate,
    saga.payment_id,
    saga.payment_refund_transaction_id,
    saga.expected_fulfillment_count,
    saga.cancelled_fulfillment_count,
    saga.expected_reservation_count,
    saga.released_reservation_count,
    order_current.current_status AS order_status,
    order_current.payment_id AS order_payment_id,
    order_current.fulfillment_id AS order_fulfillment_id,
    order_current.refund_id AS order_refund_id,
    order_current.cancellation_saga_id AS order_cancellation_saga_id,
    order_current.cancellation_mode AS order_cancellation_mode,
    order_current.responsibility_party AS order_responsibility_party,
    order_current.responsibility_code AS order_responsibility_code,
    order_current.payable_amount_minor,
    order_current.currency_code,
    CASE WHEN scope.distinct_shop_count = 1 THEN scope.shop_id ELSE NULL END AS shop_id,
    CASE WHEN scope.distinct_channel_count = 1 THEN scope.channel_code ELSE NULL END AS channel_code,
    scope.distinct_shop_count,
    scope.distinct_channel_count,
    scope.distinct_sku_count,
    GREATEST(saga.recorded_at, COALESCE(order_current.recorded_at, saga.recorded_at)) AS data_freshness_at
FROM completed_saga saga
JOIN yshopping_dim.dim_canonical_order_current order_current
  ON order_current.tenant_id = saga.tenant_id
 AND order_current.order_id = saga.order_id
LEFT JOIN item_scope scope
  ON scope.tenant_id = saga.tenant_id
 AND scope.order_id = saga.order_id;
