CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_after_sale_status_event AS
SELECT
    event_id, schema_version, tenant_id, aggregate_id AS after_sale_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.after_sale_id') AS payload_after_sale_id,
    get_json_string(payload, '$.after_sale_no') AS after_sale_no,
    get_json_string(payload, '$.after_sale_type') AS after_sale_type,
    get_json_string(payload, '$.reason_code') AS reason_code,
    get_json_string(payload, '$.responsibility') AS responsibility,
    get_json_string(payload, '$.reason') AS reason,
    get_json_string(payload, '$.after_sale_item_id') AS after_sale_item_id,
    get_json_string(payload, '$.order_id') AS order_id,
    get_json_string(payload, '$.order_item_id') AS order_item_id,
    get_json_string(payload, '$.buyer_id') AS buyer_id,
    get_json_string(payload, '$.canonical_sku_id') AS canonical_sku_id,
    CAST(get_json_string(payload, '$.quantity') AS DECIMAL(24,6)) AS quantity,
    get_json_string(payload, '$.listing_id') AS listing_id,
    get_json_string(payload, '$.listing_offer_id') AS listing_offer_id,
    CAST(get_json_string(payload, '$.approved_amount_minor') AS BIGINT) AS approved_amount_minor,
    get_json_string(payload, '$.currency_code') AS currency_code,
    get_json_string(payload, '$.payment_id') AS payment_id,
    get_json_string(payload, '$.forward_fulfillment_id') AS forward_fulfillment_id,
    get_json_string(payload, '$.forward_shipment_id') AS forward_shipment_id,
    get_json_string(payload, '$.return_fulfillment_id') AS return_fulfillment_id,
    get_json_string(payload, '$.return_shipment_id') AS return_shipment_id,
    get_json_string(payload, '$.inspection_id') AS inspection_id,
    get_json_string(payload, '$.resolution_saga_id') AS resolution_saga_id,
    get_json_string(payload, '$.refund_status') AS refund_status,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'after_sale.status.changed'
  AND schema_version = 1
  AND source_system = 'cloudmold-aftersales';
