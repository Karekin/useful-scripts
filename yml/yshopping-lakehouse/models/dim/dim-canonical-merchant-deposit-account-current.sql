CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_merchant_deposit_account_current AS
SELECT
    event_id, tenant_id, account_id, account_version, merchant_id, currency,
    required_after_minor AS required_amount_minor,
    held_after_minor AS held_amount_minor,
    frozen_after_minor AS frozen_amount_minor,
    held_after_minor - frozen_after_minor AS available_amount_minor,
    paid_after_minor AS paid_amount_minor,
    deducted_after_minor AS deducted_amount_minor,
    current_coverage_status AS coverage_status,
    current_enforcement_status AS enforcement_status,
    policy_version, ledger_entry_id, entry_type, amount_minor, business_reference,
    reason_code, evidence_ref, occurred_at, recorded_at, correlation_id, causation_id, run_id
FROM (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, account_id
               ORDER BY account_version DESC, recorded_at DESC, event_id DESC
           ) AS account_version_rank
    FROM yshopping_dwd.dwd_canonical_merchant_deposit_ledger_event event
) latest
WHERE account_version_rank = 1;
