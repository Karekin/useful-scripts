CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_order_cancellation_saga_reservation_event AS
SELECT
    event.event_id,
    event.schema_version,
    event.tenant_id,
    event.saga_id,
    event.run_id,
    event.order_id,
    event.order_no,
    event.cancellation_mode,
    event.aggregate_version,
    event.current_status AS saga_status,
    event.occurred_at,
    event.recorded_at,
    get_json_string(reservation.`value`, '$.order_item_id') AS order_item_id,
    get_json_string(reservation.`value`, '$.reservation_id') AS reservation_id,
    CAST(get_json_string(reservation.`value`, '$.quantity') AS DECIMAL(24,6)) AS quantity
FROM yshopping_dwd.dwd_canonical_order_cancellation_saga_event event,
     LATERAL json_each(event.reservations) reservation;
