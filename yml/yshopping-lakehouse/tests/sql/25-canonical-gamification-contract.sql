-- Canonical Gamification first-slice DQC. Zero violations proves internal contract safety, not non-empty production evidence.
SELECT 'gamification_event_id_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, event_id
    FROM yshopping_dwd.dwd_domain_event
    WHERE source_system = 'cloudmold-gamification'
    GROUP BY tenant_id, event_id HAVING COUNT(*) <> 1
) duplicate_event;

SELECT 'gamification_unregistered_event_type' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_domain_event
WHERE source_system = 'cloudmold-gamification'
  AND event_type NOT IN (
    'gamification.game.created','gamification.virtual_currency.account_opened',
    'gamification.reward.definition_published','gamification.draw_pool.version_published',
    'gamification.task.definition_published','gamification.game.definition_published',
    'gamification.session.status_changed','gamification.round.status_changed',
    'gamification.virtual_currency.ledger_posted','gamification.reward.granted',
    'gamification.draw.completed','gamification.assist.recorded',
    'gamification.task.progress_changed','gamification.fragment.ledger_posted',
    'gamification.gift.transferred','gamification.season_series.version_published',
    'gamification.season.version_published','gamification.collectible.version_published',
    'gamification.collectible.ownership_changed','gamification.redemption.status_changed',
    'gamification.reward_claim.status_changed'
  );

SELECT 'gamification_game_definition_version_gap' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, game_id
    FROM yshopping_dim.dim_canonical_gamification_game_version_history
    GROUP BY tenant_id, game_id
    HAVING MIN(game_version) <> 1 OR COUNT(DISTINCT game_version) <> MAX(game_version)
) invalid_history;

SELECT 'gamification_game_asset_boundary_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_gamification_game_current
WHERE current_status = 'PUBLISHED'
  AND (virtual_currency_code NOT REGEXP '^GAME_COIN_[A-Z0-9_]{2,40}$'
       OR UPPER(virtual_currency_code) REGEXP '(TOKEN|COUPON|POINT|CNY|RMB|USD|MONEY)'
       OR session_ttl_seconds < 60 OR session_ttl_seconds > 86400);

SELECT 'gamification_currency_account_boundary_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_gamification_currency_account_current a
LEFT JOIN yshopping_dim.dim_canonical_gamification_game_current g
  ON g.tenant_id = a.tenant_id AND g.game_id = a.game_id
WHERE a.asset_class <> 'GAME_VIRTUAL_CURRENCY' OR a.status <> 'ACTIVE'
   OR a.owner_type NOT IN ('PLAYER','TREASURY')
   OR (a.owner_type = 'PLAYER' AND a.balance_microunits < 0)
   OR a.currency_code <> g.virtual_currency_code;

SELECT 'gamification_currency_ledger_not_double_entry' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_gamification_currency_transaction_event
WHERE asset_class <> 'GAME_VIRTUAL_CURRENCY' OR amount_microunits <= 0
   OR entry_count <> 2 OR entry_delta_sum_microunits <> 0
   OR debit_account_id = credit_account_id
   OR business_type NOT IN ('DRAW_CHARGE','REWARD_GRANT','GIFT_TRANSFER','REDEMPTION');

SELECT 'gamification_currency_ledger_account_mismatch' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_gamification_currency_transaction_event t
LEFT JOIN yshopping_dim.dim_canonical_gamification_currency_account_current debit
  ON debit.tenant_id = t.tenant_id AND debit.account_id = t.debit_account_id
LEFT JOIN yshopping_dim.dim_canonical_gamification_currency_account_current credit
  ON credit.tenant_id = t.tenant_id AND credit.account_id = t.credit_account_id
WHERE debit.account_id IS NULL OR credit.account_id IS NULL
   OR debit.game_id <> t.game_id OR credit.game_id <> t.game_id
   OR debit.currency_code <> t.currency_code OR credit.currency_code <> t.currency_code
   OR (debit.owner_type = 'PLAYER' AND t.debit_balance_after_microunits < 0);

SELECT 'gamification_currency_balance_not_ledger_derived' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_gamification_currency_account_current a
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_currency_account_event opened
  ON opened.tenant_id = a.tenant_id AND opened.account_id = a.account_id
LEFT JOIN (
    SELECT tenant_id, account_id, SUM(delta_microunits) AS ledger_delta
    FROM yshopping_dwd.dwd_canonical_gamification_currency_ledger_entry_event
    GROUP BY tenant_id, account_id
) l ON l.tenant_id = a.tenant_id AND l.account_id = a.account_id
WHERE a.balance_microunits <> opened.balance_microunits + COALESCE(l.ledger_delta, 0);

SELECT 'gamification_reward_definition_boundary_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_gamification_reward_definition_history
WHERE (reward_kind = 'CURRENCY' AND (asset_class <> 'GAME_VIRTUAL_CURRENCY'
       OR asset_code NOT REGEXP '^GAME_COIN_[A-Z0-9_]{2,40}$'
       OR UPPER(asset_code) REGEXP '(TOKEN|COUPON|POINT|CNY|RMB|USD|MONEY)'
       OR currency_amount_microunits <= 0 OR fragment_quantity IS NOT NULL))
   OR (reward_kind = 'FRAGMENT' AND (asset_class <> 'GAME_FRAGMENT'
       OR asset_code NOT REGEXP '^GAME_FRAGMENT_[A-Z0-9_]{2,40}$'
       OR fragment_quantity <= 0 OR currency_amount_microunits IS NOT NULL));

SELECT 'gamification_reward_grant_lineage_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_gamification_reward_grant_event r
LEFT JOIN yshopping_dim.dim_canonical_gamification_reward_definition_history d
  ON d.tenant_id = r.tenant_id AND d.reward_definition_id = r.reward_definition_id
 AND d.reward_version = r.reward_version
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_currency_transaction_event l
  ON l.tenant_id = r.tenant_id AND l.ledger_transaction_id = r.ledger_transaction_id
WHERE d.reward_definition_id IS NULL OR d.game_id <> r.game_id
   OR d.reward_kind <> r.reward_kind OR d.asset_class <> r.asset_class OR d.asset_code <> r.asset_code
   OR (r.reward_kind = 'CURRENCY' AND (r.currency_amount_microunits <= 0 OR r.fragment_quantity IS NOT NULL
       OR l.business_type <> 'REWARD_GRANT' OR l.business_id <> r.reward_grant_id
       OR l.amount_microunits <> r.currency_amount_microunits))
   OR (r.reward_kind = 'FRAGMENT' AND (r.fragment_quantity <= 0
       OR r.currency_amount_microunits IS NOT NULL OR r.ledger_transaction_id IS NOT NULL));

SELECT 'gamification_draw_charge_reward_lineage_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_gamification_draw_event d
LEFT JOIN yshopping_dim.dim_canonical_gamification_draw_pool_version_history p
  ON p.tenant_id = d.tenant_id AND p.draw_pool_id = d.draw_pool_id AND p.pool_version = d.draw_pool_version
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_currency_transaction_event charge
  ON charge.tenant_id = d.tenant_id AND charge.business_type = 'DRAW_CHARGE' AND charge.business_id = d.draw_request_id
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_reward_grant_event reward
  ON reward.tenant_id = d.tenant_id AND reward.reward_grant_id = d.reward_grant_id
WHERE p.draw_pool_id IS NULL OR p.game_id <> d.game_id OR p.price_microunits <> d.price_microunits
   OR d.selected_ticket < 1 OR d.selected_ticket > d.total_weight OR d.total_weight <> p.total_weight
   OR charge.ledger_transaction_id IS NULL OR charge.amount_microunits <> d.price_microunits
   OR reward.reward_grant_id IS NULL OR reward.source_type <> 'DRAW' OR reward.source_id <> d.draw_request_id
   OR reward.reward_definition_id <> d.reward_definition_id OR reward.reward_version <> d.reward_version;

SELECT 'gamification_assist_quota_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_gamification_assist_event
WHERE helper_principal_id = beneficiary_principal_id OR ordinal < 1
   OR assists_used < ordinal OR assists_used > assist_limit;

SELECT 'gamification_task_progress_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_gamification_task_progress_event p
LEFT JOIN yshopping_dim.dim_canonical_gamification_task_definition_history d
  ON d.tenant_id = p.tenant_id AND d.task_definition_id = p.task_definition_id AND d.task_version = p.task_version
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_reward_grant_event r
  ON r.tenant_id = p.tenant_id AND r.reward_grant_id = p.reward_grant_id
WHERE d.task_definition_id IS NULL OR d.game_id <> p.game_id OR d.target_units <> p.target_units
   OR p.completed_units < 0 OR p.completed_units > p.target_units
   OR (p.current_status = 'IN_PROGRESS' AND (p.completed_units >= p.target_units OR p.reward_grant_id IS NOT NULL))
   OR (p.current_status = 'COMPLETED' AND (p.completed_units <> p.target_units OR r.reward_grant_id IS NULL
       OR r.source_type <> 'TASK_PROGRESS' OR r.source_id <> p.task_progress_id));

SELECT 'gamification_fragment_reward_lineage_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_gamification_fragment_ledger_event f
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_reward_grant_event r
  ON r.tenant_id = f.tenant_id AND r.reward_grant_id = f.reward_grant_id
WHERE f.asset_class <> 'GAME_FRAGMENT' OR f.delta_quantity = 0 OR f.balance_after_quantity < 0
   OR r.reward_grant_id IS NULL OR r.reward_kind <> 'FRAGMENT'
   OR r.principal_id <> f.principal_id OR r.game_id <> f.game_id
   OR r.fragment_quantity <> f.delta_quantity OR r.asset_code <> f.fragment_code;

SELECT 'gamification_gift_ledger_lineage_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_gamification_gift_event g
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_currency_transaction_event l
  ON l.tenant_id = g.tenant_id AND l.ledger_transaction_id = g.ledger_transaction_id
WHERE g.asset_class <> 'GAME_VIRTUAL_CURRENCY' OR g.from_principal_id = g.to_principal_id
   OR g.amount_microunits <= 0 OR l.ledger_transaction_id IS NULL
   OR l.business_type <> 'GIFT_TRANSFER' OR l.business_id <> g.gift_transfer_id
   OR l.game_id <> g.game_id OR l.currency_code <> g.currency_code OR l.amount_microunits <> g.amount_microunits;

SELECT 'gamification_round_session_lineage_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_canonical_gamification_round_event r
LEFT JOIN yshopping_dim.dim_canonical_gamification_session_current s
  ON s.tenant_id = r.tenant_id AND s.session_id = r.session_id
WHERE s.session_id IS NULL OR s.game_id <> r.game_id OR s.game_version <> r.game_version
   OR s.principal_id <> r.principal_id OR r.round_number < 1
   OR (r.current_status = 'ACTIVE' AND (r.outcome IS NOT NULL OR r.score IS NOT NULL))
   OR (r.current_status = 'COMPLETED' AND (r.outcome IS NULL OR r.score < 0));

SELECT 'gamification_unproven_completion_flag' AS check_name, COUNT(*) AS violations
FROM yshopping_ads.ads_canonical_gamification_readiness
WHERE non_empty_reconciliation_verified <> false
   OR historical_backfill_verified <> false
   OR hard_delete_history_verified <> false;

SELECT 'gamification_season_definition_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_gamification_season_version_history s
LEFT JOIN yshopping_dim.dim_canonical_gamification_season_series_version_history series
  ON series.tenant_id = s.tenant_id AND series.season_series_id = s.season_series_id
 AND series.series_version = s.series_version
WHERE series.season_series_id IS NULL OR series.game_id <> s.game_id
   OR s.status <> 'PUBLISHED' OR s.ends_at <= s.starts_at;

SELECT 'gamification_collectible_balance_not_ledger_derived' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_gamification_collectible_ownership_current o
LEFT JOIN yshopping_dim.dim_canonical_gamification_collectible_version_history d
  ON d.tenant_id = o.tenant_id AND d.collectible_definition_id = o.collectible_definition_id
 AND d.collectible_version = o.collectible_version
LEFT JOIN (
    SELECT tenant_id, ownership_id, SUM(delta_quantity) AS derived_quantity
    FROM yshopping_dwd.dwd_canonical_gamification_collectible_ownership_event
    GROUP BY tenant_id, ownership_id
) ledger ON ledger.tenant_id = o.tenant_id AND ledger.ownership_id = o.ownership_id
WHERE d.collectible_definition_id IS NULL OR d.game_id <> o.game_id
   OR o.quantity < 0 OR o.quantity <> ledger.derived_quantity;

SELECT 'gamification_redemption_external_boundary_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_gamification_redemption_current r
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_collectible_ownership_event c
  ON c.tenant_id = r.tenant_id AND c.source_type = 'REDEMPTION' AND c.source_id = r.redemption_intent_id
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_currency_transaction_event l
  ON l.tenant_id = r.tenant_id AND l.ledger_transaction_id = r.source_ledger_transaction_id
LEFT JOIN yshopping_dim.dim_canonical_gamification_currency_account_current debit
  ON debit.tenant_id = l.tenant_id AND debit.account_id = l.debit_account_id
LEFT JOIN yshopping_dim.dim_canonical_gamification_currency_account_current credit
  ON credit.tenant_id = l.tenant_id AND credit.account_id = l.credit_account_id
WHERE r.adapter_code IS NULL OR r.adapter_code <> 'MALL_REDEMPTION_V1'
   OR r.contains_external_balance IS NULL OR r.contains_external_balance <> false
   OR r.current_status IS NULL OR r.current_status NOT IN ('PENDING','SUCCEEDED','REJECTED')
   OR r.source_asset_class IS NULL
   OR r.source_asset_class NOT IN ('GAME_COLLECTIBLE','GAME_VIRTUAL_CURRENCY')
   OR r.external_intent_ref IS NULL
   OR (r.source_asset_class = 'GAME_COLLECTIBLE' AND (r.collectible_definition_id IS NULL
       OR r.collectible_version IS NULL OR r.collectible_version < 1
       OR r.quantity IS NULL OR r.quantity < 1 OR r.currency_code IS NOT NULL
       OR r.amount_microunits IS NOT NULL))
   OR (r.source_asset_class = 'GAME_VIRTUAL_CURRENCY' AND (r.collectible_definition_id IS NOT NULL
       OR r.collectible_version IS NOT NULL OR r.quantity IS NOT NULL
       OR r.currency_code IS NULL OR r.currency_code NOT REGEXP '^GAME_COIN_[A-Z0-9_]{2,40}$'
       OR UPPER(r.currency_code) REGEXP '(TOKEN|COUPON|POINT|CNY|RMB|USD|MONEY)'
       OR r.amount_microunits IS NULL OR r.amount_microunits < 1))
   OR (r.current_status = 'PENDING' AND (r.external_result_ref IS NOT NULL
       OR r.source_ledger_transaction_id IS NOT NULL OR c.collectible_entry_id IS NOT NULL))
   OR (r.current_status IN ('SUCCEEDED','REJECTED') AND r.external_result_ref IS NULL)
   OR (r.current_status = 'SUCCEEDED' AND r.source_asset_class = 'GAME_COLLECTIBLE'
       AND (r.source_ledger_transaction_id IS NOT NULL OR l.ledger_transaction_id IS NOT NULL
       OR c.collectible_entry_id IS NULL
       OR c.game_id <> r.game_id OR c.principal_id <> r.principal_id
       OR c.collectible_definition_id <> r.collectible_definition_id
       OR c.collectible_version <> r.collectible_version
       OR c.delta_quantity <> -r.quantity))
   OR (r.current_status = 'SUCCEEDED' AND r.source_asset_class = 'GAME_VIRTUAL_CURRENCY'
       AND (c.collectible_entry_id IS NOT NULL OR l.ledger_transaction_id IS NULL
       OR l.business_type <> 'REDEMPTION' OR l.business_id <> r.redemption_intent_id
       OR l.game_id <> r.game_id OR l.currency_code <> r.currency_code
       OR l.amount_microunits <> r.amount_microunits
       OR debit.account_id IS NULL OR debit.owner_type <> 'PLAYER' OR debit.owner_ref <> r.principal_id
       OR credit.account_id IS NULL OR credit.owner_type <> 'TREASURY'))
   OR (r.current_status = 'REJECTED' AND (r.source_ledger_transaction_id IS NOT NULL
       OR c.collectible_entry_id IS NOT NULL OR l.ledger_transaction_id IS NOT NULL));

SELECT 'gamification_redemption_deduction_cardinality_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_gamification_redemption_current r
LEFT JOIN (
    SELECT tenant_id, source_id AS redemption_intent_id,
           COUNT(*) AS deduction_count, SUM(delta_quantity) AS deducted_quantity
    FROM yshopping_dwd.dwd_canonical_gamification_collectible_ownership_event
    WHERE source_type = 'REDEMPTION'
    GROUP BY tenant_id, source_id
) c ON c.tenant_id = r.tenant_id AND c.redemption_intent_id = r.redemption_intent_id
LEFT JOIN (
    SELECT tenant_id, ledger_transaction_id, COUNT(*) AS deduction_count
    FROM yshopping_dwd.dwd_canonical_gamification_currency_transaction_event
    WHERE business_type = 'REDEMPTION'
    GROUP BY tenant_id, ledger_transaction_id
) l ON l.tenant_id = r.tenant_id AND l.ledger_transaction_id = r.source_ledger_transaction_id
WHERE (r.current_status = 'SUCCEEDED' AND r.source_asset_class = 'GAME_COLLECTIBLE'
       AND (COALESCE(c.deduction_count, 0) <> 1 OR c.deducted_quantity <> -r.quantity
            OR COALESCE(l.deduction_count, 0) <> 0))
   OR (r.current_status = 'SUCCEEDED' AND r.source_asset_class = 'GAME_VIRTUAL_CURRENCY'
       AND (COALESCE(c.deduction_count, 0) <> 0 OR COALESCE(l.deduction_count, 0) <> 1))
   OR (r.current_status IN ('PENDING','REJECTED')
       AND (COALESCE(c.deduction_count, 0) <> 0 OR COALESCE(l.deduction_count, 0) <> 0));

SELECT 'gamification_reward_claim_lineage_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dim.dim_canonical_gamification_reward_claim_current c
LEFT JOIN yshopping_dim.dim_canonical_gamification_reward_definition_history d
  ON d.tenant_id = c.tenant_id AND d.reward_definition_id = c.reward_definition_id
 AND d.reward_version = c.reward_version
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_reward_grant_event r
  ON r.tenant_id = c.tenant_id AND r.reward_grant_id = c.reward_grant_id
WHERE d.reward_definition_id IS NULL OR d.game_id <> c.game_id
   OR (c.current_status IN ('CLAIMABLE','EXPIRED') AND c.reward_grant_id IS NOT NULL)
   OR (c.current_status IN ('CLAIMABLE','EXPIRED') AND c.claimed_at IS NOT NULL)
   OR (c.current_status = 'EXPIRED' AND c.recorded_at < c.claim_expires_at)
   OR (c.current_status = 'CLAIMED' AND (r.reward_grant_id IS NULL
       OR c.claimed_at IS NULL OR c.claimed_at > c.claim_expires_at
       OR r.game_id <> c.game_id OR r.principal_id <> c.principal_id
       OR r.reward_definition_id <> c.reward_definition_id OR r.reward_version <> c.reward_version
       OR r.source_type <> 'REWARD_CLAIM' OR r.source_id <> c.reward_claim_id));

SELECT 'gamification_leaderboard_write_event_forbidden' AS check_name, COUNT(*) AS violations
FROM yshopping_dwd.dwd_domain_event
WHERE source_system = 'cloudmold-gamification' AND event_type LIKE 'gamification.leaderboard.%';

SELECT 'gamification_currency_leaderboard_input_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_gamification_currency_leaderboard_input_current i
LEFT JOIN yshopping_dim.dim_canonical_gamification_game_current g
  ON g.tenant_id = i.tenant_id AND g.game_id = i.game_id
WHERE i.currency_code <> g.virtual_currency_code
   OR i.balance_microunits < 0
   OR i.principal_id IS NULL OR i.principal_id = ''
   OR i.as_of_time < i.data_freshness_at;

SELECT 'gamification_currency_leaderboard_key_duplicate' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, game_id, currency_code, principal_id
    FROM yshopping_dws.dws_canonical_gamification_currency_leaderboard_input_current
    GROUP BY tenant_id, game_id, currency_code, principal_id
    HAVING COUNT(*) <> 1
) duplicate_player;

SELECT 'gamification_currency_leaderboard_position_invalid' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, game_id, currency_code,
           COUNT(*) AS player_count, COUNT(DISTINCT stable_position) AS position_count,
           MIN(stable_position) AS first_position, MAX(stable_position) AS last_position
    FROM yshopping_ads.ads_canonical_gamification_currency_leaderboard_current
    GROUP BY tenant_id, game_id, currency_code
    HAVING first_position <> 1 OR last_position <> player_count OR position_count <> player_count
) invalid_partition;

SELECT 'gamification_gift_leaderboard_input_invalid' AS check_name, COUNT(*) AS violations
FROM yshopping_dws.dws_canonical_gamification_gift_leaderboard_1d
WHERE leaderboard_role NOT IN ('SENDER','RECEIVER')
   OR window_end <= window_start
   OR transfer_count <= 0 OR transfer_microunits <= 0
   OR principal_id IS NULL OR principal_id = ''
   OR first_transfer_at < window_start OR first_transfer_at >= window_end
   OR last_transfer_at < window_start OR last_transfer_at >= window_end;

SELECT 'gamification_gift_leaderboard_position_invalid' AS check_name, COUNT(*) AS violations
FROM (
    SELECT tenant_id, game_id, currency_code, leaderboard_role, window_start, window_end,
           COUNT(*) AS player_count, COUNT(DISTINCT stable_position) AS position_count,
           MIN(stable_position) AS first_position, MAX(stable_position) AS last_position
    FROM yshopping_ads.ads_canonical_gamification_gift_leaderboard_1d
    GROUP BY tenant_id, game_id, currency_code, leaderboard_role, window_start, window_end
    HAVING first_position <> 1 OR last_position <> player_count OR position_count <> player_count
) invalid_partition;
