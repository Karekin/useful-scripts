CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_fulfillment_item_event AS
SELECT
    event.event_id,
    event.tenant_id,
    event.fulfillment_id,
    event.fulfillment_no,
    event.order_id,
    event.order_no,
    event.run_id,
    event.aggregate_version,
    event.current_status AS fulfillment_status,
    event.shipment_id,
    event.occurred_at,
    event.recorded_at,
    get_json_string(item.`value`, '$.fulfillment_item_id') AS fulfillment_item_id,
    get_json_string(item.`value`, '$.order_item_id') AS order_item_id,
    get_json_string(item.`value`, '$.canonical_sku_id') AS canonical_sku_id,
    CAST(get_json_string(item.`value`, '$.quantity') AS DECIMAL(24,6)) AS quantity,
    CAST(get_json_string(item.`value`, '$.variable_fulfillment_cost_minor') AS BIGINT) AS variable_fulfillment_cost_minor,
    get_json_string(item.`value`, '$.reservation_id') AS reservation_id
FROM yshopping_dwd.dwd_canonical_fulfillment_status_event event,
     LATERAL json_each(event.items) item;
