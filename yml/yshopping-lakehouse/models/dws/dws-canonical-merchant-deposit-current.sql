CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_merchant_deposit_current AS
WITH ledger_rollup AS (
    SELECT tenant_id, account_id,
           COUNT(*) AS ledger_entry_count,
           COUNT(DISTINCT ledger_entry_id) AS distinct_ledger_entry_count,
           MIN(account_version) AS minimum_account_version,
           MAX(account_version) AS maximum_account_version,
           SUM(held_delta_minor) AS net_held_delta_minor,
           SUM(frozen_delta_minor) AS net_frozen_delta_minor,
           SUM(CASE WHEN entry_type = 'PAID' THEN amount_minor ELSE 0 END) AS paid_ledger_amount_minor,
           SUM(CASE WHEN entry_type = 'DEDUCTED' THEN amount_minor ELSE 0 END) AS deducted_ledger_amount_minor,
           MIN(recorded_at) AS first_ledger_recorded_at,
           MAX(recorded_at) AS last_ledger_recorded_at
    FROM yshopping_dwd.dwd_canonical_merchant_deposit_ledger_event
    GROUP BY tenant_id, account_id
), critical_ranked AS (
    SELECT event.*,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, account_id
               ORDER BY account_version DESC, recorded_at DESC, event_id DESC
           ) AS critical_rank
    FROM yshopping_dwd.dwd_canonical_merchant_deposit_ledger_event event
    WHERE current_enforcement_status = 'ENFORCED'
      AND current_coverage_status = 'SALES_BLOCKED'
      AND COALESCE(previous_coverage_status, '') <> 'SALES_BLOCKED'
), critical AS (
    SELECT * FROM critical_ranked WHERE critical_rank = 1
), suspension AS (
    SELECT deposit.tenant_id, deposit.account_id,
           COUNT(status.event_id) AS suspension_event_count,
           MIN(status.event_id) AS suspension_event_id,
           MIN(status.aggregate_version) AS suspension_merchant_version,
           MIN(status.recorded_at) AS suspension_recorded_at
    FROM critical deposit
    LEFT JOIN yshopping_dwd.dwd_canonical_merchant_entity_status_event status
      ON status.tenant_id = deposit.tenant_id
     AND status.causation_id = deposit.event_id
     AND status.entity_type = 'MERCHANT'
     AND status.merchant_id = deposit.merchant_id
     AND status.current_status = 'SUSPENDED'
    GROUP BY deposit.tenant_id, deposit.account_id
), enforcement_saga AS (
    SELECT suspension.tenant_id, suspension.account_id,
           COUNT(saga.saga_id) AS unpublish_saga_count,
           MIN(saga.saga_id) AS unpublish_saga_id,
           MIN(saga.current_status) AS unpublish_saga_status,
           MIN(CASE
             WHEN saga.current_status = 'COMPLETED'
              AND saga.source_event_matches = TRUE
              AND saga.active_step = 'NONE'
              AND saga.unpublished_listing_count + saga.skipped_listing_count = saga.expected_listing_count
              AND saga.actual_unpublished_listing_count = saga.unpublished_listing_count
             THEN 'RECONCILED'
             ELSE 'INCOMPLETE' END) AS unpublish_saga_readiness,
           MIN(saga.expected_listing_count) AS expected_listing_count,
           MIN(saga.actual_unpublished_listing_count) AS actual_unpublished_listing_count
    FROM suspension
    LEFT JOIN yshopping_dws.dws_canonical_listing_unpublish_saga_current saga
      ON saga.tenant_id = suspension.tenant_id
     AND saga.source_event_id = suspension.suspension_event_id
     AND saga.source_entity_type = 'MERCHANT'
    GROUP BY suspension.tenant_id, suspension.account_id
)
SELECT
    account.*,
    ledger.ledger_entry_count,
    ledger.distinct_ledger_entry_count,
    ledger.minimum_account_version,
    ledger.maximum_account_version,
    ledger.net_held_delta_minor,
    ledger.net_frozen_delta_minor,
    ledger.paid_ledger_amount_minor,
    ledger.deducted_ledger_amount_minor,
    critical.event_id AS critical_deposit_event_id,
    critical.account_version AS critical_deposit_account_version,
    critical.recorded_at AS critical_deposit_recorded_at,
    COALESCE(suspension.suspension_event_count, 0) AS suspension_event_count,
    suspension.suspension_event_id,
    suspension.suspension_merchant_version,
    suspension.suspension_recorded_at,
    COALESCE(saga.unpublish_saga_count, 0) AS unpublish_saga_count,
    saga.unpublish_saga_id,
    saga.unpublish_saga_status,
    saga.unpublish_saga_readiness,
    COALESCE(saga.expected_listing_count, 0) AS expected_listing_count,
    COALESCE(saga.actual_unpublished_listing_count, 0) AS actual_unpublished_listing_count,
    GREATEST(account.recorded_at, ledger.last_ledger_recorded_at,
             COALESCE(critical.recorded_at, account.recorded_at),
             COALESCE(suspension.suspension_recorded_at, account.recorded_at)) AS data_freshness_at
FROM yshopping_dim.dim_canonical_merchant_deposit_account_current account
JOIN ledger_rollup ledger
  ON ledger.tenant_id = account.tenant_id AND ledger.account_id = account.account_id
LEFT JOIN critical
  ON critical.tenant_id = account.tenant_id AND critical.account_id = account.account_id
LEFT JOIN suspension
  ON suspension.tenant_id = account.tenant_id AND suspension.account_id = account.account_id
LEFT JOIN enforcement_saga saga
  ON saga.tenant_id = account.tenant_id AND saga.account_id = account.account_id;
