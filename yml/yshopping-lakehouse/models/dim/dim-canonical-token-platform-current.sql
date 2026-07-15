CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_token_model_offering_current AS
SELECT event_id, tenant_id, offering_id, aggregate_version, occurred_at, recorded_at, offering_code,
       provider_code, model_code, previous_status, current_status, operation, offering_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, offering_id) AS offering_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, offering_id ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_token_model_offering_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_token_access_credential_current AS
SELECT event_id, tenant_id, credential_id, aggregate_version, occurred_at, recorded_at, principal_id, offering_id,
       credential_fingerprint, key_version, previous_status, current_status, expires_at, operation, credential_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, credential_id) AS credential_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, credential_id ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_token_access_credential_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_token_quota_account_current AS
SELECT event_id, tenant_id, account_id, aggregate_version, recorded_at, ledger_entry_id, principal_id,
       entry_type, signed_delta_microunits, balance_after_microunits, reference_type, reference_id, occurred_at, ledger_event_count
FROM (
    SELECT e.*, COUNT(*) OVER (PARTITION BY tenant_id, account_id) AS ledger_event_count,
           ROW_NUMBER() OVER (PARTITION BY tenant_id, account_id ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_token_quota_ledger_event e
) ranked WHERE rn = 1;
