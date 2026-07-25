CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_order_current AS
WITH history AS (
    SELECT
        tenant_id,
        order_id,
        MAX(address_ref) AS address_ref,
        MAX(address_snapshot_version) AS address_snapshot_version,
        MAX(destination_region_code) AS destination_region_code,
        MAX(cancellation_saga_id) AS cancellation_saga_id,
        MAX(pre_cancellation_status) AS pre_cancellation_status,
        MAX(cancellation_mode) AS cancellation_mode,
        MAX(responsibility_party) AS responsibility_party,
        MAX(responsibility_code) AS responsibility_code
    FROM yshopping_dwd.dwd_canonical_order_status_event
    GROUP BY tenant_id, order_id
), latest AS (
    SELECT event.*,
           COUNT(*) OVER (PARTITION BY tenant_id, order_id) AS order_event_count,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, order_id
               ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
           ) AS row_num
    FROM yshopping_dwd.dwd_canonical_order_status_event event
)
SELECT
    latest.event_id, latest.schema_version, latest.tenant_id, latest.order_id, latest.order_no,
    latest.run_id, latest.buyer_id, latest.aggregate_version,
    COALESCE(latest.address_ref, history.address_ref) AS address_ref,
    COALESCE(latest.address_snapshot_version, history.address_snapshot_version) AS address_snapshot_version,
    COALESCE(latest.destination_region_code, history.destination_region_code) AS destination_region_code,
    latest.previous_status, latest.current_status, latest.product_amount_minor,
    latest.shipping_amount_minor, latest.discount_amount_minor, latest.payable_amount_minor,
    latest.currency_code, latest.payment_id,
    COALESCE(latest.cancellation_saga_id, history.cancellation_saga_id) AS cancellation_saga_id,
    COALESCE(latest.pre_cancellation_status, history.pre_cancellation_status) AS pre_cancellation_status,
    COALESCE(latest.cancellation_mode, history.cancellation_mode) AS cancellation_mode,
    COALESCE(latest.responsibility_party, history.responsibility_party) AS responsibility_party,
    COALESCE(latest.responsibility_code, history.responsibility_code) AS responsibility_code,
    latest.step_ordinal, latest.fulfillment_id, latest.shipment_id, latest.refund_id,
    latest.reason, latest.correlation_id, latest.occurred_at, latest.recorded_at,
    latest.order_event_count
FROM latest
JOIN history
  ON history.tenant_id = latest.tenant_id AND history.order_id = latest.order_id
WHERE latest.row_num = 1;
