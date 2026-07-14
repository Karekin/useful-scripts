SELECT 'domain_event_id_unique' AS check_name, COUNT(*) AS violations
FROM (
  SELECT event_id FROM yshopping_dwd.dwd_domain_event GROUP BY event_id HAVING COUNT(*) > 1
) duplicate_event
UNION ALL
SELECT 'domain_event_aggregate_sequence_unique', COUNT(*)
FROM (
  SELECT tenant_id, aggregate_type, aggregate_id, aggregate_version, event_sequence
  FROM yshopping_dwd.dwd_domain_event
  GROUP BY tenant_id, aggregate_type, aggregate_id, aggregate_version, event_sequence
  HAVING COUNT(*) > 1
) duplicate_sequence
UNION ALL
SELECT 'domain_event_required_fields', COUNT(*)
FROM yshopping_dwd.dwd_domain_event
WHERE event_id IS NULL OR event_type IS NULL OR schema_version IS NULL OR source_system IS NULL OR tenant_id IS NULL
   OR aggregate_type IS NULL OR aggregate_id IS NULL OR aggregate_version IS NULL
   OR idempotency_key IS NULL OR payload IS NULL OR LENGTH(payload_hash) <> 64;
