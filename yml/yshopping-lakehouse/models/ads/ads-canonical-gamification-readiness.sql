CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_gamification_readiness AS
WITH activity_rows AS (
    SELECT tenant_id, game_id, 1 AS session_event_count, 0 AS round_event_count, 0 AS draw_count,
           0 AS reward_grant_count, 0 AS assist_count, 0 AS task_progress_event_count,
           0 AS fragment_ledger_count, 0 AS gift_count, recorded_at AS freshness_at
    FROM yshopping_dwd.dwd_canonical_gamification_session_event
    UNION ALL SELECT tenant_id, game_id, 0, 1, 0, 0, 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_round_event
    UNION ALL SELECT tenant_id, game_id, 0, 0, 1, 0, 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_draw_event
    UNION ALL SELECT tenant_id, game_id, 0, 0, 0, 1, 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_reward_grant_event
    UNION ALL SELECT tenant_id, game_id, 0, 0, 0, 0, 1, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_assist_event
    UNION ALL SELECT tenant_id, game_id, 0, 0, 0, 0, 0, 1, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_task_progress_event
    UNION ALL SELECT tenant_id, game_id, 0, 0, 0, 0, 0, 0, 1, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_fragment_ledger_event
    UNION ALL SELECT tenant_id, game_id, 0, 0, 0, 0, 0, 0, 0, 1, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_gift_event
), activity AS (
    SELECT tenant_id, game_id, SUM(session_event_count) AS session_event_count,
           SUM(round_event_count) AS round_event_count, SUM(draw_count) AS draw_count,
           SUM(reward_grant_count) AS reward_grant_count, SUM(assist_count) AS assist_count,
           SUM(task_progress_event_count) AS task_progress_event_count,
           SUM(fragment_ledger_count) AS fragment_ledger_count, SUM(gift_count) AS gift_count,
           MAX(freshness_at) AS activity_freshness_at
    FROM activity_rows GROUP BY tenant_id, game_id
), extended_activity AS (
    SELECT tenant_id, game_id,
           SUM(season_count) AS season_count,
           SUM(collectible_event_count) AS collectible_event_count,
           SUM(redemption_event_count) AS redemption_event_count,
           SUM(reward_claim_event_count) AS reward_claim_event_count,
           MAX(freshness_at) AS extended_freshness_at
    FROM (
        SELECT tenant_id, game_id, 1 AS season_count, 0 AS collectible_event_count,
               0 AS redemption_event_count, 0 AS reward_claim_event_count, recorded_at AS freshness_at
        FROM yshopping_dwd.dwd_canonical_gamification_season_event
        UNION ALL SELECT tenant_id, game_id, 0, 1, 0, 0, recorded_at
        FROM yshopping_dwd.dwd_canonical_gamification_collectible_ownership_event
        UNION ALL SELECT tenant_id, game_id, 0, 0, 1, 0, recorded_at
        FROM yshopping_dwd.dwd_canonical_gamification_redemption_event
        UNION ALL SELECT tenant_id, game_id, 0, 0, 0, 1, recorded_at
        FROM yshopping_dwd.dwd_canonical_gamification_reward_claim_event
    ) extended_rows
    GROUP BY tenant_id, game_id
), integrity_rows AS (
    SELECT g.tenant_id, g.game_id, COUNT(*) AS violation_count
    FROM yshopping_dim.dim_canonical_gamification_game_current g
    WHERE (g.current_status = 'DRAFT' AND g.current_version <> 0)
       OR (g.current_status = 'PUBLISHED' AND (g.current_version < 1
           OR g.virtual_currency_code NOT REGEXP '^GAME_COIN_[A-Z0-9_]{2,40}$'
           OR UPPER(g.virtual_currency_code) REGEXP '(TOKEN|COUPON|POINT|CNY|RMB|USD|MONEY)'
           OR g.assist_daily_limit < 0 OR g.assist_daily_limit > 100
           OR g.max_rounds_per_session < 1 OR g.max_rounds_per_session > 1000
           OR g.session_ttl_seconds < 60 OR g.session_ttl_seconds > 86400))
    GROUP BY g.tenant_id, g.game_id
    UNION ALL
    SELECT tenant_id, game_id,
           IF(MIN(game_version) = 1 AND COUNT(DISTINCT game_version) = MAX(game_version), 0, 1)
    FROM yshopping_dim.dim_canonical_gamification_game_version_history
    GROUP BY tenant_id, game_id
    UNION ALL
    SELECT a.tenant_id, a.game_id, COUNT(*)
    FROM yshopping_dim.dim_canonical_gamification_currency_account_current a
    LEFT JOIN yshopping_dim.dim_canonical_gamification_game_current g
      ON g.tenant_id = a.tenant_id AND g.game_id = a.game_id
    WHERE a.asset_class <> 'GAME_VIRTUAL_CURRENCY' OR a.status <> 'ACTIVE'
       OR a.owner_type NOT IN ('PLAYER', 'TREASURY')
       OR (a.owner_type = 'PLAYER' AND a.balance_microunits < 0)
       OR a.currency_code <> g.virtual_currency_code
    GROUP BY a.tenant_id, a.game_id
    UNION ALL
    SELECT t.tenant_id, t.game_id, COUNT(*)
    FROM yshopping_dwd.dwd_canonical_gamification_currency_transaction_event t
    LEFT JOIN yshopping_dim.dim_canonical_gamification_currency_account_current debit
      ON debit.tenant_id = t.tenant_id AND debit.account_id = t.debit_account_id
    LEFT JOIN yshopping_dim.dim_canonical_gamification_currency_account_current credit
      ON credit.tenant_id = t.tenant_id AND credit.account_id = t.credit_account_id
    WHERE t.asset_class <> 'GAME_VIRTUAL_CURRENCY' OR t.amount_microunits <= 0
       OR t.entry_count <> 2 OR t.entry_delta_sum_microunits <> 0
       OR t.debit_account_id = t.credit_account_id
       OR debit.account_id IS NULL OR credit.account_id IS NULL
       OR debit.game_id <> t.game_id OR credit.game_id <> t.game_id
       OR debit.currency_code <> t.currency_code OR credit.currency_code <> t.currency_code
       OR (debit.owner_type = 'PLAYER' AND t.debit_balance_after_microunits < 0)
    GROUP BY t.tenant_id, t.game_id
    UNION ALL
    SELECT a.tenant_id, a.game_id, COUNT(*)
    FROM yshopping_dim.dim_canonical_gamification_currency_account_current a
    LEFT JOIN (
        SELECT tenant_id, account_id, SUM(delta_microunits) AS ledger_delta
        FROM yshopping_dwd.dwd_canonical_gamification_currency_ledger_entry_event
        GROUP BY tenant_id, account_id
    ) l ON l.tenant_id = a.tenant_id AND l.account_id = a.account_id
    LEFT JOIN yshopping_dwd.dwd_canonical_gamification_currency_account_event opened
      ON opened.tenant_id = a.tenant_id AND opened.account_id = a.account_id
    WHERE a.balance_microunits <> opened.balance_microunits + COALESCE(l.ledger_delta, 0)
    GROUP BY a.tenant_id, a.game_id
    UNION ALL
    SELECT r.tenant_id, r.game_id, COUNT(*)
    FROM yshopping_dwd.dwd_canonical_gamification_reward_grant_event r
    LEFT JOIN yshopping_dim.dim_canonical_gamification_reward_definition_history d
      ON d.tenant_id = r.tenant_id AND d.reward_definition_id = r.reward_definition_id
     AND d.reward_version = r.reward_version
    LEFT JOIN yshopping_dwd.dwd_canonical_gamification_currency_transaction_event l
      ON l.tenant_id = r.tenant_id AND l.ledger_transaction_id = r.ledger_transaction_id
    WHERE d.reward_definition_id IS NULL OR d.game_id <> r.game_id
       OR d.reward_kind <> r.reward_kind OR d.asset_class <> r.asset_class OR d.asset_code <> r.asset_code
       OR (r.reward_kind = 'CURRENCY' AND (r.currency_amount_microunits <= 0 OR r.fragment_quantity IS NOT NULL
           OR l.ledger_transaction_id IS NULL OR l.business_type <> 'REWARD_GRANT'
           OR l.business_id <> r.reward_grant_id OR l.amount_microunits <> r.currency_amount_microunits))
       OR (r.reward_kind = 'FRAGMENT' AND (r.fragment_quantity <= 0 OR r.currency_amount_microunits IS NOT NULL
           OR r.ledger_transaction_id IS NOT NULL))
    GROUP BY r.tenant_id, r.game_id
    UNION ALL
    SELECT d.tenant_id, d.game_id, COUNT(*)
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
       OR reward.reward_definition_id <> d.reward_definition_id OR reward.reward_version <> d.reward_version
    GROUP BY d.tenant_id, d.game_id
    UNION ALL
    SELECT a.tenant_id, a.game_id, COUNT(*)
    FROM yshopping_dwd.dwd_canonical_gamification_assist_event a
    WHERE a.helper_principal_id = a.beneficiary_principal_id OR a.ordinal < 1
       OR a.assists_used < a.ordinal OR a.assists_used > a.assist_limit
    GROUP BY a.tenant_id, a.game_id
    UNION ALL
    SELECT p.tenant_id, p.game_id, COUNT(*)
    FROM yshopping_dwd.dwd_canonical_gamification_task_progress_event p
    LEFT JOIN yshopping_dim.dim_canonical_gamification_task_definition_history d
      ON d.tenant_id = p.tenant_id AND d.task_definition_id = p.task_definition_id
     AND d.task_version = p.task_version
    LEFT JOIN yshopping_dwd.dwd_canonical_gamification_reward_grant_event r
      ON r.tenant_id = p.tenant_id AND r.reward_grant_id = p.reward_grant_id
    WHERE d.task_definition_id IS NULL OR d.game_id <> p.game_id OR d.target_units <> p.target_units
       OR p.completed_units < 0 OR p.completed_units > p.target_units
       OR (p.current_status = 'IN_PROGRESS' AND (p.completed_units >= p.target_units OR p.reward_grant_id IS NOT NULL))
       OR (p.current_status = 'COMPLETED' AND (p.completed_units <> p.target_units OR r.reward_grant_id IS NULL
           OR r.source_type <> 'TASK_PROGRESS' OR r.source_id <> p.task_progress_id))
    GROUP BY p.tenant_id, p.game_id
    UNION ALL
    SELECT f.tenant_id, f.game_id, COUNT(*)
    FROM yshopping_dwd.dwd_canonical_gamification_fragment_ledger_event f
    LEFT JOIN yshopping_dwd.dwd_canonical_gamification_reward_grant_event r
      ON r.tenant_id = f.tenant_id AND r.reward_grant_id = f.reward_grant_id
    WHERE f.asset_class <> 'GAME_FRAGMENT' OR f.delta_quantity = 0 OR f.balance_after_quantity < 0
       OR r.reward_grant_id IS NULL OR r.reward_kind <> 'FRAGMENT'
       OR r.principal_id <> f.principal_id OR r.game_id <> f.game_id
       OR r.fragment_quantity <> f.delta_quantity OR r.asset_code <> f.fragment_code
    GROUP BY f.tenant_id, f.game_id
    UNION ALL
    SELECT g.tenant_id, g.game_id, COUNT(*)
    FROM yshopping_dwd.dwd_canonical_gamification_gift_event g
    LEFT JOIN yshopping_dwd.dwd_canonical_gamification_currency_transaction_event l
      ON l.tenant_id = g.tenant_id AND l.ledger_transaction_id = g.ledger_transaction_id
    WHERE g.asset_class <> 'GAME_VIRTUAL_CURRENCY' OR g.from_principal_id = g.to_principal_id
       OR g.amount_microunits <= 0 OR l.ledger_transaction_id IS NULL
       OR l.business_type <> 'GIFT_TRANSFER' OR l.business_id <> g.gift_transfer_id
       OR l.game_id <> g.game_id OR l.currency_code <> g.currency_code
       OR l.amount_microunits <> g.amount_microunits
    GROUP BY g.tenant_id, g.game_id
    UNION ALL
    SELECT r.tenant_id, r.game_id, COUNT(*)
    FROM yshopping_dwd.dwd_canonical_gamification_round_event r
    LEFT JOIN yshopping_dim.dim_canonical_gamification_session_current s
      ON s.tenant_id = r.tenant_id AND s.session_id = r.session_id
    WHERE s.session_id IS NULL OR s.game_id <> r.game_id OR s.game_version <> r.game_version
       OR s.principal_id <> r.principal_id OR r.round_number < 1
       OR (r.current_status = 'ACTIVE' AND (r.outcome IS NOT NULL OR r.score IS NOT NULL))
       OR (r.current_status = 'COMPLETED' AND (r.outcome IS NULL OR r.score < 0))
    GROUP BY r.tenant_id, r.game_id
    UNION ALL
    SELECT h.tenant_id, h.game_id,
           IF(MIN(h.series_version) = 1 AND COUNT(DISTINCT h.series_version) = MAX(h.series_version), 0, 1)
    FROM yshopping_dim.dim_canonical_gamification_season_series_version_history h
    GROUP BY h.tenant_id, h.game_id, h.season_series_id
    UNION ALL
    SELECT s.tenant_id, s.game_id, COUNT(*)
    FROM yshopping_dim.dim_canonical_gamification_season_version_history s
    LEFT JOIN yshopping_dim.dim_canonical_gamification_season_series_version_history series
      ON series.tenant_id = s.tenant_id AND series.season_series_id = s.season_series_id
     AND series.series_version = s.series_version
    WHERE series.season_series_id IS NULL OR series.game_id <> s.game_id
       OR s.status <> 'PUBLISHED' OR s.ends_at <= s.starts_at
    GROUP BY s.tenant_id, s.game_id
    UNION ALL
    SELECT h.tenant_id, h.game_id,
           IF(MIN(h.collectible_version) = 1 AND COUNT(DISTINCT h.collectible_version) = MAX(h.collectible_version), 0, 1)
    FROM yshopping_dim.dim_canonical_gamification_collectible_version_history h
    GROUP BY h.tenant_id, h.game_id, h.collectible_definition_id
    UNION ALL
    SELECT o.tenant_id, o.game_id, COUNT(*)
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
       OR o.quantity < 0 OR o.quantity <> ledger.derived_quantity
    GROUP BY o.tenant_id, o.game_id
    UNION ALL
    SELECT r.tenant_id, r.game_id, COUNT(*)
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
           OR c.collectible_entry_id IS NOT NULL OR l.ledger_transaction_id IS NOT NULL))
    GROUP BY r.tenant_id, r.game_id
    UNION ALL
    SELECT r.tenant_id, r.game_id, COUNT(*)
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
           AND (COALESCE(c.deduction_count, 0) <> 0 OR COALESCE(l.deduction_count, 0) <> 0))
    GROUP BY r.tenant_id, r.game_id
    UNION ALL
    SELECT c.tenant_id, c.game_id, COUNT(*)
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
           OR r.source_type <> 'REWARD_CLAIM' OR r.source_id <> c.reward_claim_id))
    GROUP BY c.tenant_id, c.game_id
), integrity AS (
    SELECT tenant_id, game_id, SUM(violation_count) AS integrity_violation_count
    FROM integrity_rows GROUP BY tenant_id, game_id
)
SELECT g.tenant_id, g.game_id, g.game_code, g.game_name, g.current_version,
       g.current_status, g.virtual_currency_code,
       COALESCE(a.session_event_count, 0) AS session_event_count,
       COALESCE(a.round_event_count, 0) AS round_event_count,
       COALESCE(a.draw_count, 0) AS draw_count,
       COALESCE(a.reward_grant_count, 0) AS reward_grant_count,
       COALESCE(a.assist_count, 0) AS assist_count,
       COALESCE(a.task_progress_event_count, 0) AS task_progress_event_count,
       COALESCE(a.fragment_ledger_count, 0) AS fragment_ledger_count,
       COALESCE(a.gift_count, 0) AS gift_count,
       COALESCE(x.season_count, 0) AS season_count,
       COALESCE(x.collectible_event_count, 0) AS collectible_event_count,
       COALESCE(x.redemption_event_count, 0) AS redemption_event_count,
       COALESCE(x.reward_claim_event_count, 0) AS reward_claim_event_count,
       COALESCE(i.integrity_violation_count, 0) AS integrity_violation_count,
       CASE
         WHEN COALESCE(i.integrity_violation_count, 0) > 0 THEN 'INCONSISTENT'
         WHEN COALESCE(a.session_event_count, 0) + COALESCE(a.round_event_count, 0)
            + COALESCE(a.draw_count, 0) + COALESCE(a.reward_grant_count, 0)
            + COALESCE(a.assist_count, 0) + COALESCE(a.task_progress_event_count, 0)
            + COALESCE(a.fragment_ledger_count, 0) + COALESCE(a.gift_count, 0)
            + COALESCE(x.collectible_event_count, 0) + COALESCE(x.redemption_event_count, 0)
            + COALESCE(x.reward_claim_event_count, 0) = 0
           THEN 'DEFINITION_ONLY'
         ELSE 'GAMIFICATION_FIRST_SLICE_READY'
       END AS readiness_status,
       false AS non_empty_reconciliation_verified,
       false AS historical_backfill_verified,
       false AS hard_delete_history_verified,
       GREATEST(COALESCE(a.activity_freshness_at, '1970-01-01 00:00:00'),
                COALESCE(x.extended_freshness_at, '1970-01-01 00:00:00')) AS data_freshness_at
FROM yshopping_dim.dim_canonical_gamification_game_current g
LEFT JOIN activity a ON a.tenant_id = g.tenant_id AND a.game_id = g.game_id
LEFT JOIN extended_activity x ON x.tenant_id = g.tenant_id AND x.game_id = g.game_id
LEFT JOIN integrity i ON i.tenant_id = g.tenant_id AND i.game_id = g.game_id;

-- Current 金币榜: semantic rank preserves equal balances while stable_position makes
-- every published row deterministic through principal_id. No OLTP leaderboard is written.
CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_gamification_currency_leaderboard_current AS
SELECT tenant_id, game_id, currency_code, principal_id, account_id,
       'CURRENT' AS window_type, CAST(NULL AS DATETIME) AS window_start,
       as_of_time AS window_end, as_of_time,
       balance_microunits,
       DENSE_RANK() OVER (
           PARTITION BY tenant_id, game_id, currency_code
           ORDER BY balance_microunits DESC
       ) AS balance_rank,
       ROW_NUMBER() OVER (
           PARTITION BY tenant_id, game_id, currency_code
           ORDER BY balance_microunits DESC, principal_id ASC
       ) AS stable_position,
       data_freshness_at
FROM yshopping_dws.dws_canonical_gamification_currency_leaderboard_input_current;

-- Daily 礼物榜: SENDER and RECEIVER are independent rankings over auditable gift facts.
-- principal_id is the final tie-break after amount and transfer count.
CREATE OR REPLACE VIEW yshopping_ads.ads_canonical_gamification_gift_leaderboard_1d AS
SELECT tenant_id, game_id, currency_code, leaderboard_role, principal_id,
       'DAY' AS window_type, window_start, window_end,
       MAX(data_freshness_at) OVER (
           PARTITION BY tenant_id, game_id, currency_code, leaderboard_role, window_start, window_end
       ) AS as_of_time,
       transfer_count, transfer_microunits,
       DENSE_RANK() OVER (
           PARTITION BY tenant_id, game_id, currency_code, leaderboard_role, window_start, window_end
           ORDER BY transfer_microunits DESC, transfer_count DESC
       ) AS gift_rank,
       ROW_NUMBER() OVER (
           PARTITION BY tenant_id, game_id, currency_code, leaderboard_role, window_start, window_end
           ORDER BY transfer_microunits DESC, transfer_count DESC, principal_id ASC
       ) AS stable_position,
       first_transfer_at, last_transfer_at, data_freshness_at
FROM yshopping_dws.dws_canonical_gamification_gift_leaderboard_1d;
