CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_return_fulfillment_inspection_event AS
SELECT
    event_id, schema_version, tenant_id, aggregate_id AS inspection_id, aggregate_version,
    occurred_at, recorded_at, correlation_id, causation_id, idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.return_fulfillment_no') AS return_fulfillment_no,
    get_json_string(payload, '$.return_fulfillment_item_id') AS return_fulfillment_item_id,
    get_json_string(payload, '$.after_sale_id') AS after_sale_id,
    get_json_string(payload, '$.after_sale_item_id') AS after_sale_item_id,
    get_json_string(payload, '$.return_fulfillment_id') AS return_fulfillment_id,
    get_json_string(payload, '$.order_id') AS order_id,
    get_json_string(payload, '$.order_item_id') AS order_item_id,
    get_json_string(payload, '$.canonical_sku_id') AS canonical_sku_id,
    CAST(get_json_string(payload, '$.quantity') AS DECIMAL(24,6)) AS quantity,
    get_json_string(payload, '$.owner_id') AS owner_id,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.uom_code') AS uom_code,
    CAST(get_json_string(payload, '$.return_shipping_amount_minor') AS BIGINT) AS return_shipping_amount_minor,
    get_json_string(payload, '$.currency_code') AS currency_code,
    get_json_string(payload, '$.return_shipment_id') AS return_shipment_id,
    get_json_string(payload, '$.carrier_code') AS carrier_code,
    get_json_string(payload, '$.waybill_no') AS waybill_no,
    get_json_string(payload, '$.handed_over_at') AS handed_over_at,
    get_json_string(payload, '$.in_transit_at') AS in_transit_at,
    get_json_string(payload, '$.received_at') AS received_at,
    get_json_string(payload, '$.receiver_id') AS receiver_id,
    CAST(get_json_string(payload, '$.received_quantity') AS DECIMAL(24,6)) AS received_quantity,
    CAST(get_json_string(payload, '$.accepted_quantity') AS DECIMAL(24,6)) AS accepted_quantity,
    CAST(get_json_string(payload, '$.rejected_quantity') AS DECIMAL(24,6)) AS rejected_quantity,
    get_json_string(payload, '$.quality_status') AS quality_status,
    get_json_string(payload, '$.inspection_result') AS inspection_result,
    get_json_string(payload, '$.decision') AS decision,
    get_json_string(payload, '$.inspector_id') AS inspector_id,
    get_json_string(payload, '$.inspected_at') AS inspected_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'return_fulfillment.inspection.decided'
  AND schema_version = 1
  AND source_system = 'cloudmold-fulfillment';
