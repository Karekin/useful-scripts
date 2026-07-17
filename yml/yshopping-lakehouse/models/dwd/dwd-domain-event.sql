CREATE OR REPLACE VIEW yshopping_dwd.dwd_domain_event AS
SELECT
    event_id,
    event_type,
    schema_version,
    source_system,
    tenant_id,
    aggregate_type,
    aggregate_id,
    aggregate_version,
    event_sequence,
    occurred_at,
    recorded_at,
    trace_id,
    correlation_id,
    causation_id,
    idempotency_key,
    payload,
    headers,
    payload_hash,
    destination,
    status AS delivery_status,
    published_at
FROM yshopping_ods.cloudmold_event_outbox
-- Only relay-confirmed rows are business facts. PENDING(0), CLAIMED(10) and
-- DEAD(30) remain operational evidence and must not advance business readiness.
WHERE status = 20;
