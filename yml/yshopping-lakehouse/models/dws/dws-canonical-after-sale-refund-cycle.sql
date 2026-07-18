CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_after_sale_refund_cycle AS
WITH tenant_window AS (
    SELECT
        tenant_id,
        CAST(CURRENT_TIMESTAMP() AS DATETIME) AS wall_clock_at
    FROM yshopping_dwd.dwd_canonical_after_sale_refund_status_event
    GROUP BY tenant_id
), refund_events AS (
    SELECT
        event.tenant_id,
        event.refund_id,
        MAX(event.run_id) AS run_id,
        MAX(event.after_sale_id) AS after_sale_id,
        MAX(event.after_sale_no) AS after_sale_no,
        MAX(event.after_sale_type) AS after_sale_type,
        MAX(event.payment_id) AS payment_id,
        MAX(event.provider_code) AS provider_code,
        MAX(event.currency_code) AS currency_code,
        MAX(event.refunded_amount_minor) AS refunded_amount_minor,
        MIN(CASE WHEN event.current_status = 'REQUESTED' THEN event.occurred_at END) AS requested_at,
        MIN(CASE WHEN event.current_status = 'SUCCEEDED' THEN event.occurred_at END) AS succeeded_at,
        MAX(event.recorded_at) AS data_freshness_at
    FROM yshopping_dwd.dwd_canonical_after_sale_refund_status_event event
    JOIN tenant_window window
      ON window.tenant_id = event.tenant_id
    WHERE event.occurred_at <= window.wall_clock_at
    GROUP BY event.tenant_id, event.refund_id
)
SELECT
    tenant_id,
    refund_id,
    run_id,
    after_sale_id,
    after_sale_no,
    after_sale_type,
    payment_id,
    provider_code,
    currency_code,
    refunded_amount_minor,
    requested_at,
    succeeded_at,
    CAST(TIMESTAMPDIFF(SECOND, requested_at, succeeded_at) / 3600.0 AS DECIMAL(38,6))
        AS refund_cycle_hours,
    data_freshness_at
FROM refund_events
WHERE requested_at IS NOT NULL
  AND succeeded_at IS NOT NULL
  AND succeeded_at >= requested_at;
