CREATE OR REPLACE VIEW yshopping_dwd.dwd_app_cart_item_event AS
SELECT
    event.event_id,
    event.tenant_id,
    event.cart_id,
    event.cart_version,
    event.event_sequence,
    event.occurred_at,
    event.recorded_at,
    event.buyer_principal_id,
    event.operation,
    CAST(get_json_string(line.`value`, '$.line_id') AS STRING) AS line_id,
    CAST(get_json_string(line.`value`, '$.listing_id') AS STRING) AS listing_id,
    CAST(get_json_string(line.`value`, '$.listing_offer_id') AS STRING) AS listing_offer_id,
    CAST(get_json_string(line.`value`, '$.canonical_sku_id') AS STRING) AS canonical_sku_id,
    CAST(get_json_string(line.`value`, '$.quantity') AS DECIMAL(24,6)) AS quantity,
    CAST(get_json_string(line.`value`, '$.selected') AS BOOLEAN) AS selected
FROM yshopping_dwd.dwd_app_cart_event event,
     LATERAL json_each(event.lines) line;
