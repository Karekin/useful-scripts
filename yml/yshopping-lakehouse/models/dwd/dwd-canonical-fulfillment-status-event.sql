CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_fulfillment_status_event AS
SELECT
    event_id,
    schema_version,
    tenant_id,
    aggregate_id AS fulfillment_id,
    aggregate_version,
    occurred_at,
    recorded_at,
    correlation_id,
    causation_id,
    idempotency_key,
    get_json_string(payload, '$.run_id') AS run_id,
    get_json_string(payload, '$.fulfillment_no') AS fulfillment_no,
    get_json_string(payload, '$.order_id') AS order_id,
    get_json_string(payload, '$.order_no') AS order_no,
    get_json_string(payload, '$.seller_id') AS seller_id,
    get_json_string(payload, '$.warehouse_id') AS warehouse_id,
    get_json_string(payload, '$.delivery_promise_version_ref') AS delivery_promise_version_ref,
    get_json_string(payload, '$.promised_delivery_at') AS promised_delivery_at,
    get_json_string(payload, '$.promise_frozen_at') AS promise_frozen_at,
    get_json_string(payload, '$.previous_status') AS previous_status,
    get_json_string(payload, '$.current_status') AS current_status,
    get_json_string(payload, '$.shipment_id') AS shipment_id,
    get_json_string(payload, '$.carrier_code') AS carrier_code,
    get_json_string(payload, '$.waybill_no') AS waybill_no,
    get_json_string(payload, '$.shipped_at') AS shipped_at,
    get_json_string(payload, '$.in_transit_at') AS in_transit_at,
    get_json_string(payload, '$.delivered_at') AS delivered_at,
    get_json_string(payload, '$.reason') AS reason,
    get_json_string(payload, '$.cancellation_saga_id') AS cancellation_saga_id,
    CAST(get_json_string(payload, '$.step_ordinal') AS INT) AS step_ordinal,
    json_query(payload, '$.items') AS items
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'fulfillment.status.changed'
  AND schema_version IN (1, 2, 3)
  AND source_system = 'cloudmold-fulfillment';
