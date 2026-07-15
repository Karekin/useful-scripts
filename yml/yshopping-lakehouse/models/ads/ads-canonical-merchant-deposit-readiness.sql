CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_merchant_deposit_readiness AS
SELECT
    deposit.*,
    CASE
        WHEN ledger_entry_count <> distinct_ledger_entry_count
          OR minimum_account_version <> 1
          OR maximum_account_version <> account_version
          OR ledger_entry_count <> account_version
          OR net_held_delta_minor <> held_amount_minor
          OR net_frozen_delta_minor <> frozen_amount_minor
          OR paid_ledger_amount_minor <> paid_amount_minor
          OR deducted_ledger_amount_minor <> deducted_amount_minor
          OR held_amount_minor <> paid_amount_minor - deducted_amount_minor
          OR frozen_amount_minor > held_amount_minor
          OR coverage_status <> CASE
               WHEN CAST(held_amount_minor AS DECIMAL(38,0)) * 5
                    >= CAST(required_amount_minor AS DECIMAL(38,0)) * 3 THEN 'SUFFICIENT'
               WHEN CAST(held_amount_minor AS DECIMAL(38,0)) * 5
                    >= CAST(required_amount_minor AS DECIMAL(38,0)) THEN 'BID_RESTRICTED'
               ELSE 'SALES_BLOCKED' END
        THEN 'INCONSISTENT'
        WHEN critical_deposit_event_id IS NOT NULL
         AND suspension_event_count = 1
         AND unpublish_saga_count = 1
         AND unpublish_saga_status = 'COMPLETED'
         AND unpublish_saga_readiness = 'RECONCILED'
         AND critical_deposit_recorded_at <= suspension_recorded_at
        THEN 'RECONCILED'
        WHEN critical_deposit_event_id IS NOT NULL THEN 'ENFORCEMENT_INCOMPLETE'
        WHEN enforcement_status = 'SHADOW' THEN 'SHADOW'
        ELSE 'RECONCILED'
    END AS readiness_status,
    CASE
        WHEN coverage_status = 'SALES_BLOCKED' THEN 'SALES_BLOCKED'
        WHEN coverage_status = 'BID_RESTRICTED' THEN 'BID_RESTRICTED'
        ELSE 'NORMAL'
    END AS risk_tier
FROM yshopping_dws.dws_canonical_merchant_deposit_current deposit;
