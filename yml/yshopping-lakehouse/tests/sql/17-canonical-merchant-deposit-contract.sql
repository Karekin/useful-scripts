SELECT 'canonical_merchant_deposit_event_id_unique' AS check_name, COUNT(*) AS violations
FROM (
  SELECT event_id
  FROM yshopping_dwd.dwd_canonical_merchant_deposit_ledger_event
  GROUP BY event_id HAVING COUNT(*) > 1
) duplicate_event;

SELECT 'canonical_merchant_deposit_ledger_entry_unique', COUNT(*)
FROM (
  SELECT tenant_id, ledger_entry_id
  FROM yshopping_dwd.dwd_canonical_merchant_deposit_ledger_event
  GROUP BY tenant_id, ledger_entry_id HAVING COUNT(*) > 1
) duplicate_entry;

SELECT 'canonical_merchant_deposit_version_continuity', COUNT(*)
FROM (
  SELECT tenant_id, account_id, COUNT(*) AS event_count,
         MIN(account_version) AS min_version, MAX(account_version) AS max_version
  FROM yshopping_dwd.dwd_canonical_merchant_deposit_ledger_event
  GROUP BY tenant_id, account_id
  HAVING min_version <> 1 OR event_count <> max_version
) broken_history;

SELECT 'canonical_merchant_deposit_payload_identity', COUNT(*)
FROM yshopping_dwd.dwd_canonical_merchant_deposit_ledger_event
WHERE account_id <> payload_account_id
   OR currency NOT REGEXP '^[A-Z]{3}$'
   OR amount_minor < 0;

SELECT 'canonical_merchant_deposit_ledger_arithmetic', COUNT(*)
FROM yshopping_dwd.dwd_canonical_merchant_deposit_ledger_event
WHERE held_after_minor <> held_before_minor + held_delta_minor
   OR frozen_after_minor <> frozen_before_minor + frozen_delta_minor
   OR frozen_after_minor > held_after_minor
   OR held_after_minor <> paid_after_minor - deducted_after_minor;

SELECT 'canonical_merchant_deposit_current_conservation', COUNT(*)
FROM yshopping_dim.dim_canonical_merchant_deposit_account_current
WHERE held_amount_minor <> paid_amount_minor - deducted_amount_minor
   OR frozen_amount_minor > held_amount_minor
   OR available_amount_minor <> held_amount_minor - frozen_amount_minor;

SELECT 'canonical_merchant_deposit_threshold', COUNT(*)
FROM yshopping_dim.dim_canonical_merchant_deposit_account_current
WHERE coverage_status <> CASE
  WHEN CAST(held_amount_minor AS DECIMAL(38,0))*5
       >= CAST(required_amount_minor AS DECIMAL(38,0))*3 THEN 'SUFFICIENT'
  WHEN CAST(held_amount_minor AS DECIMAL(38,0))*5
       >= CAST(required_amount_minor AS DECIMAL(38,0)) THEN 'BID_RESTRICTED'
  ELSE 'SALES_BLOCKED' END;

SELECT 'canonical_merchant_deposit_exact_suspension_lineage', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_deposit_current
WHERE critical_deposit_event_id IS NOT NULL AND suspension_event_count <> 1;

SELECT 'canonical_merchant_deposit_exact_unpublish_saga', COUNT(*)
FROM yshopping_dws.dws_canonical_merchant_deposit_current
WHERE critical_deposit_event_id IS NOT NULL
  AND (unpublish_saga_count <> 1 OR unpublish_saga_readiness <> 'RECONCILED');

SELECT 'canonical_merchant_deposit_terminal_readiness', COUNT(*)
FROM yshopping_ads.ads_canonical_merchant_deposit_readiness
WHERE readiness_status IN ('INCONSISTENT', 'ENFORCEMENT_INCOMPLETE');

SELECT 'canonical_merchant_deposit_pii_isolation', COUNT(*)
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'merchant.deposit.ledger_posted'
  AND (get_json_string(payload, '$.bank_account_no') IS NOT NULL
    OR get_json_string(payload, '$.contact_mobile') IS NOT NULL
    OR get_json_string(payload, '$.id_card') IS NOT NULL
    OR get_json_string(payload, '$.voucher_url') IS NOT NULL
    OR get_json_string(payload, '$.payment_credential') IS NOT NULL);
