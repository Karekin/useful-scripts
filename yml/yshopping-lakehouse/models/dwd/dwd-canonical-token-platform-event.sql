-- Token Platform first slice. Credential material, prompts, email and login IP are excluded by contract.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_token_model_offering_event AS
SELECT event_id, tenant_id, aggregate_id AS offering_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.offering_code') AS offering_code,
       get_json_string(payload, '$.provider_code') AS provider_code,
       get_json_string(payload, '$.model_code') AS model_code,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'token_platform.model_offering.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-token-platform';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_token_access_credential_event AS
SELECT event_id, tenant_id, aggregate_id AS credential_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.offering_id') AS offering_id,
       get_json_string(payload, '$.credential_fingerprint') AS credential_fingerprint,
       CAST(get_json_string(payload, '$.key_version') AS BIGINT) AS key_version,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.expires_at') AS DATETIME) AS expires_at,
       get_json_string(payload, '$.operation') AS operation
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'token_platform.access_credential.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-token-platform';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_token_quota_ledger_event AS
SELECT event_id, tenant_id, aggregate_id AS account_id, aggregate_version, occurred_at AS event_occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.ledger_entry_id') AS ledger_entry_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.entry_type') AS entry_type,
       CAST(get_json_string(payload, '$.signed_delta_microunits') AS BIGINT) AS signed_delta_microunits,
       CAST(get_json_string(payload, '$.balance_after_microunits') AS BIGINT) AS balance_after_microunits,
       get_json_string(payload, '$.reference_type') AS reference_type,
       get_json_string(payload, '$.reference_id') AS reference_id,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'token_platform.quota.ledger_posted' AND schema_version = 1
  AND source_system = 'cloudmold-token-platform';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_token_invocation_usage_event AS
SELECT event_id, tenant_id, aggregate_id AS usage_id, aggregate_version, occurred_at AS event_occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.request_id') AS request_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.credential_id') AS credential_id,
       get_json_string(payload, '$.offering_id') AS offering_id,
       get_json_string(payload, '$.provider_code') AS provider_code,
       get_json_string(payload, '$.model_code') AS model_code,
       get_json_string(payload, '$.result_status') AS result_status,
       CAST(get_json_string(payload, '$.input_tokens') AS BIGINT) AS input_tokens,
       CAST(get_json_string(payload, '$.cached_input_tokens') AS BIGINT) AS cached_input_tokens,
       CAST(get_json_string(payload, '$.output_tokens') AS BIGINT) AS output_tokens,
       CAST(get_json_string(payload, '$.total_tokens') AS BIGINT) AS total_tokens,
       CAST(get_json_string(payload, '$.duration_millis') AS BIGINT) AS duration_millis,
       CAST(get_json_string(payload, '$.quota_cost_microunits') AS BIGINT) AS quota_cost_microunits,
       get_json_string(payload, '$.pricing_version_id') AS pricing_version_id,
       get_json_string(payload, '$.ledger_entry_id') AS ledger_entry_id,
       get_json_string(payload, '$.error_code') AS error_code,
       CAST(get_json_string(payload, '$.occurred_at') AS DATETIME) AS occurred_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'token_platform.invocation.usage_recorded' AND schema_version = 1
  AND source_system = 'cloudmold-token-platform';
