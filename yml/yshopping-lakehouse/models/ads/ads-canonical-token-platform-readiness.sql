CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_token_platform_readiness AS
SELECT u.tenant_id,
       COUNT(*) AS usage_count,
       SUM(u.total_tokens) AS total_tokens,
       SUM(u.quota_cost_microunits) AS quota_cost_microunits,
       SUM(CASE WHEN l.ledger_entry_id IS NULL THEN 1 ELSE 0 END) AS usage_without_ledger_count,
       SUM(CASE WHEN c.credential_id IS NULL OR c.current_status <> 'ACTIVE' THEN 1 ELSE 0 END) AS invalid_credential_usage_count,
       SUM(CASE WHEN o.offering_id IS NULL OR o.current_status <> 'ACTIVE' THEN 1 ELSE 0 END) AS invalid_offering_usage_count,
       CASE
         WHEN SUM(CASE WHEN l.ledger_entry_id IS NULL OR c.credential_id IS NULL OR c.current_status <> 'ACTIVE' OR o.offering_id IS NULL OR o.current_status <> 'ACTIVE' THEN 1 ELSE 0 END) > 0 THEN 'INCONSISTENT'
         ELSE 'FIRST_SLICE_RECONCILED'
       END AS readiness_status
FROM yshopping_dwd.dwd_canonical_token_invocation_usage_event u
LEFT JOIN yshopping_dwd.dwd_canonical_token_quota_ledger_event l
  ON l.tenant_id = u.tenant_id AND l.ledger_entry_id = u.ledger_entry_id
LEFT JOIN yshopping_dim.dim_canonical_token_access_credential_current c
  ON c.tenant_id = u.tenant_id AND c.credential_id = u.credential_id
LEFT JOIN yshopping_dim.dim_canonical_token_model_offering_current o
  ON o.tenant_id = u.tenant_id AND o.offering_id = u.offering_id
GROUP BY u.tenant_id;
