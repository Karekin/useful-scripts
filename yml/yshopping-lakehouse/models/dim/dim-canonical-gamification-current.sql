-- Versioned definitions retain full event history. Mutable read models are rebuilt from immutable events.
CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_game_version_history AS
SELECT event_id, tenant_id, game_id, game_code, game_version, definition_sha256,
       previous_status, current_status, virtual_currency_code, assist_daily_limit,
       max_rounds_per_session, session_ttl_seconds, occurred_at AS valid_from, recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_game_definition_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_game_version_current AS
SELECT event_id, tenant_id, game_id, game_code, game_version, definition_sha256,
       previous_status, current_status, virtual_currency_code, assist_daily_limit,
       max_rounds_per_session, session_ttl_seconds, valid_from, recorded_at
FROM (
    SELECT h.*, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, game_id
        ORDER BY game_version DESC, recorded_at DESC, event_id DESC
    ) AS rn
    FROM yshopping_dim.dim_canonical_gamification_game_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_game_current AS
SELECT c.event_id AS created_event_id, c.tenant_id, c.game_id, c.game_code, c.game_name,
       COALESCE(v.game_version, c.definition_version) AS current_version,
       COALESCE(v.current_status, c.current_status) AS current_status,
       v.definition_sha256, v.virtual_currency_code, v.assist_daily_limit,
       v.max_rounds_per_session, v.session_ttl_seconds,
       c.occurred_at AS created_at, v.valid_from AS published_at
FROM yshopping_dwd.dwd_canonical_gamification_game_created_event c
LEFT JOIN yshopping_dim.dim_canonical_gamification_game_version_current v
  ON v.tenant_id = c.tenant_id AND v.game_id = c.game_id;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_reward_definition_history AS
SELECT event_id, tenant_id, reward_definition_id, game_id, reward_code, reward_version,
       reward_kind, asset_class, asset_code, currency_amount_microunits, fragment_quantity,
       definition_sha256, occurred_at AS valid_from, recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_reward_definition_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_reward_definition_current AS
SELECT event_id, tenant_id, reward_definition_id, game_id, reward_code, reward_version,
       reward_kind, asset_class, asset_code, currency_amount_microunits, fragment_quantity,
       definition_sha256, valid_from, recorded_at
FROM (
    SELECT h.*, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, reward_definition_id
        ORDER BY reward_version DESC, recorded_at DESC, event_id DESC
    ) AS rn
    FROM yshopping_dim.dim_canonical_gamification_reward_definition_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_draw_pool_version_history AS
SELECT event_id, tenant_id, draw_pool_id, game_id, draw_pool_code, pool_version,
       status, price_microunits, total_weight, definition_sha256,
       occurred_at AS valid_from, recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_draw_pool_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_draw_pool_current AS
SELECT event_id, tenant_id, draw_pool_id, game_id, draw_pool_code, pool_version,
       status, price_microunits, total_weight, definition_sha256, valid_from, recorded_at
FROM (
    SELECT h.*, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, draw_pool_id
        ORDER BY pool_version DESC, recorded_at DESC, event_id DESC
    ) AS rn
    FROM yshopping_dim.dim_canonical_gamification_draw_pool_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_task_definition_history AS
SELECT event_id, tenant_id, task_definition_id, game_id, task_code, task_version,
       target_units, reward_definition_id, reward_version, definition_sha256,
       occurred_at AS valid_from, recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_task_definition_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_task_definition_current AS
SELECT event_id, tenant_id, task_definition_id, game_id, task_code, task_version,
       target_units, reward_definition_id, reward_version, definition_sha256, valid_from, recorded_at
FROM (
    SELECT h.*, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, task_definition_id
        ORDER BY task_version DESC, recorded_at DESC, event_id DESC
    ) AS rn
    FROM yshopping_dim.dim_canonical_gamification_task_definition_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_session_current AS
SELECT event_id, tenant_id, session_id, game_id, game_version, principal_id,
       current_status, round_count, expires_at, occurred_at, recorded_at
FROM (
    SELECT e.*, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, session_id
        ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
    ) AS rn
    FROM yshopping_dwd.dwd_canonical_gamification_session_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_round_current AS
SELECT event_id, tenant_id, round_id, session_id, game_id, game_version, principal_id,
       round_number, current_status, outcome, score, occurred_at, recorded_at
FROM (
    SELECT e.*, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, round_id
        ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
    ) AS rn
    FROM yshopping_dwd.dwd_canonical_gamification_round_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_task_progress_current AS
SELECT event_id, tenant_id, task_progress_id, task_definition_id, task_version,
       game_id, principal_id, completed_units, target_units, current_status,
       reward_grant_id, occurred_at, recorded_at
FROM (
    SELECT e.*, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, task_progress_id
        ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
    ) AS rn
    FROM yshopping_dwd.dwd_canonical_gamification_task_progress_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_fragment_balance_current AS
SELECT event_id, tenant_id, fragment_balance_id, game_id, principal_id, asset_class,
       fragment_code, balance_after_quantity AS quantity, aggregate_version,
       occurred_at, recorded_at
FROM (
    SELECT e.*, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, fragment_balance_id
        ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC
    ) AS rn
    FROM yshopping_dwd.dwd_canonical_gamification_fragment_ledger_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_currency_account_current AS
SELECT a.event_id AS opened_event_id, a.tenant_id, a.account_id, a.game_id, a.owner_type,
       a.owner_ref, a.asset_class, a.currency_code, a.status,
       b.balance_microunits, b.balance_observed_at, b.balance_recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_currency_account_event a
JOIN (
    SELECT tenant_id, account_id, balance_microunits, balance_observed_at, balance_recorded_at
    FROM (
        SELECT balances.*, ROW_NUMBER() OVER (
            PARTITION BY tenant_id, account_id
            ORDER BY balance_recorded_at DESC, balance_observed_at DESC, balance_event_id DESC
        ) AS rn
        FROM (
            SELECT tenant_id, account_id, balance_microunits,
                   occurred_at AS balance_observed_at, recorded_at AS balance_recorded_at,
                   event_id AS balance_event_id
            FROM yshopping_dwd.dwd_canonical_gamification_currency_account_event
            UNION ALL
            SELECT tenant_id, account_id, balance_after_microunits AS balance_microunits,
                   occurred_at AS balance_observed_at, recorded_at AS balance_recorded_at,
                   event_id AS balance_event_id
            FROM yshopping_dwd.dwd_canonical_gamification_currency_ledger_entry_event
        ) balances
    ) ranked WHERE rn = 1
) b ON b.tenant_id = a.tenant_id AND b.account_id = a.account_id;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_season_series_version_history AS
SELECT event_id, tenant_id, season_series_id, series_version, game_id, series_code, series_name,
       definition_sha256, occurred_at AS valid_from, recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_season_series_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_season_series_current AS
SELECT event_id, tenant_id, season_series_id, series_version, game_id, series_code, series_name,
       definition_sha256, valid_from, recorded_at
FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, season_series_id
        ORDER BY series_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_gamification_season_series_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_season_version_history AS
SELECT event_id, tenant_id, season_id, season_version, season_series_id, series_version,
       game_id, season_code, season_name, status, starts_at, ends_at, definition_sha256,
       occurred_at AS valid_from, recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_season_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_season_current AS
SELECT event_id, tenant_id, season_id, season_version, season_series_id, series_version,
       game_id, season_code, season_name, status, starts_at, ends_at, definition_sha256,
       valid_from, recorded_at
FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, season_id
        ORDER BY season_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_gamification_season_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_collectible_version_history AS
SELECT event_id, tenant_id, collectible_definition_id, collectible_version, game_id,
       collectible_code, collectible_kind, collectible_name, definition_sha256,
       occurred_at AS valid_from, recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_collectible_definition_event;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_collectible_current AS
SELECT event_id, tenant_id, collectible_definition_id, collectible_version, game_id,
       collectible_code, collectible_kind, collectible_name, definition_sha256, valid_from, recorded_at
FROM (
    SELECT h.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, collectible_definition_id
        ORDER BY collectible_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dim.dim_canonical_gamification_collectible_version_history h
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_collectible_ownership_current AS
SELECT event_id, tenant_id, ownership_id, game_id, principal_id, collectible_definition_id,
       collectible_version, quantity, aggregate_version, occurred_at, recorded_at
FROM (
    SELECT e.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, ownership_id
        ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_gamification_collectible_ownership_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_redemption_current AS
SELECT event_id, tenant_id, redemption_intent_id, game_id, principal_id, adapter_code,
       source_asset_class, collectible_definition_id, collectible_version, quantity,
       currency_code, amount_microunits, external_intent_ref, external_result_ref,
       current_status, source_ledger_transaction_id, contains_external_balance,
       aggregate_version, occurred_at, recorded_at
FROM (
    SELECT e.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, redemption_intent_id
        ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_gamification_redemption_event e
) ranked WHERE rn = 1;

CREATE OR REPLACE VIEW yshopping_dim.dim_canonical_gamification_reward_claim_current AS
SELECT event_id, tenant_id, reward_claim_id, game_id, principal_id, reward_definition_id,
       reward_version, current_status, reward_grant_id, source_type, source_id,
       claimed_at, claim_expires_at,
       aggregate_version, occurred_at, recorded_at
FROM (
    SELECT e.*, ROW_NUMBER() OVER (PARTITION BY tenant_id, reward_claim_id
        ORDER BY aggregate_version DESC, recorded_at DESC, event_id DESC) AS rn
    FROM yshopping_dwd.dwd_canonical_gamification_reward_claim_event e
) ranked WHERE rn = 1;
