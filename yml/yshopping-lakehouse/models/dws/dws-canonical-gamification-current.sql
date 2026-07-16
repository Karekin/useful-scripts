CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_gamification_currency_balance_current AS
SELECT tenant_id, game_id, currency_code, account_id, owner_type, owner_ref,
       asset_class, status, balance_microunits, balance_observed_at, balance_recorded_at
FROM yshopping_dim.dim_canonical_gamification_currency_account_current;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_gamification_player_game_1d AS
WITH player_activity AS (
    SELECT tenant_id, game_id, principal_id, CAST(recorded_at AS DATE) AS business_date,
           1 AS session_open_count, 0 AS round_completed_count, 0 AS win_count, 0 AS score_total,
           0 AS draw_count, 0 AS reward_grant_count, 0 AS currency_delta_microunits,
           0 AS fragment_delta_quantity, 0 AS assists_given_count, 0 AS assists_received_count,
           0 AS task_completed_count, 0 AS gift_sent_count, 0 AS gift_received_count,
           0 AS gift_sent_microunits, 0 AS gift_received_microunits, recorded_at AS freshness_at
    FROM yshopping_dwd.dwd_canonical_gamification_session_event WHERE previous_status IS NULL
    UNION ALL
    SELECT tenant_id, game_id, principal_id, CAST(recorded_at AS DATE),
           0, IF(current_status = 'COMPLETED', 1, 0), IF(outcome = 'WIN', 1, 0), COALESCE(score, 0),
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_round_event WHERE current_status = 'COMPLETED'
    UNION ALL
    SELECT tenant_id, game_id, principal_id, CAST(recorded_at AS DATE),
           0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_draw_event
    UNION ALL
    SELECT tenant_id, game_id, principal_id, CAST(recorded_at AS DATE),
           0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_reward_grant_event
    UNION ALL
    SELECT e.tenant_id, e.game_id, a.owner_ref, CAST(e.recorded_at AS DATE),
           0, 0, 0, 0, 0, 0, e.delta_microunits, 0, 0, 0, 0, 0, 0, 0, 0, e.recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_currency_ledger_entry_event e
    JOIN yshopping_dim.dim_canonical_gamification_currency_account_current a
      ON a.tenant_id = e.tenant_id AND a.account_id = e.account_id AND a.owner_type = 'PLAYER'
    UNION ALL
    SELECT tenant_id, game_id, principal_id, CAST(recorded_at AS DATE),
           0, 0, 0, 0, 0, 0, 0, delta_quantity, 0, 0, 0, 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_fragment_ledger_event
    UNION ALL
    SELECT tenant_id, game_id, helper_principal_id, CAST(recorded_at AS DATE),
           0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_assist_event
    UNION ALL
    SELECT tenant_id, game_id, beneficiary_principal_id, CAST(recorded_at AS DATE),
           0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_assist_event
    UNION ALL
    SELECT tenant_id, game_id, principal_id, CAST(recorded_at AS DATE),
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, IF(current_status = 'COMPLETED', 1, 0), 0, 0, 0, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_task_progress_event
    UNION ALL
    SELECT tenant_id, game_id, from_principal_id, CAST(recorded_at AS DATE),
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, amount_microunits, 0, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_gift_event
    UNION ALL
    SELECT tenant_id, game_id, to_principal_id, CAST(recorded_at AS DATE),
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, amount_microunits, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_gift_event
)
SELECT tenant_id, game_id, principal_id, business_date,
       SUM(session_open_count) AS session_open_count,
       SUM(round_completed_count) AS round_completed_count,
       SUM(win_count) AS win_count, SUM(score_total) AS score_total,
       SUM(draw_count) AS draw_count, SUM(reward_grant_count) AS reward_grant_count,
       SUM(currency_delta_microunits) AS currency_delta_microunits,
       SUM(fragment_delta_quantity) AS fragment_delta_quantity,
       SUM(assists_given_count) AS assists_given_count,
       SUM(assists_received_count) AS assists_received_count,
       SUM(task_completed_count) AS task_completed_count,
       SUM(gift_sent_count) AS gift_sent_count, SUM(gift_received_count) AS gift_received_count,
       SUM(gift_sent_microunits) AS gift_sent_microunits,
       SUM(gift_received_microunits) AS gift_received_microunits,
       MAX(freshness_at) AS data_freshness_at
FROM player_activity
GROUP BY tenant_id, game_id, principal_id, business_date;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_gamification_economy_current AS
WITH transaction_summary AS (
    SELECT tenant_id, game_id, currency_code, COUNT(*) AS transaction_count,
           SUM(amount_microunits) AS transferred_microunits,
           SUM(entry_count) AS ledger_entry_count,
           SUM(entry_delta_sum_microunits) AS ledger_delta_sum_microunits,
           SUM(IF(business_type = 'DRAW_CHARGE', 1, 0)) AS draw_charge_count,
           SUM(IF(business_type = 'DRAW_CHARGE', amount_microunits, 0)) AS draw_charge_microunits,
           SUM(IF(business_type = 'REWARD_GRANT', 1, 0)) AS currency_reward_transaction_count,
           SUM(IF(business_type = 'REWARD_GRANT', amount_microunits, 0)) AS currency_reward_microunits,
           SUM(IF(business_type = 'GIFT_TRANSFER', 1, 0)) AS gift_transaction_count,
           SUM(IF(business_type = 'GIFT_TRANSFER', amount_microunits, 0)) AS gift_microunits,
           SUM(IF(business_type = 'REDEMPTION', 1, 0)) AS redemption_transaction_count,
           SUM(IF(business_type = 'REDEMPTION', amount_microunits, 0)) AS redemption_microunits,
           MAX(recorded_at) AS ledger_freshness_at
    FROM yshopping_dwd.dwd_canonical_gamification_currency_transaction_event
    GROUP BY tenant_id, game_id, currency_code
), account_summary AS (
    SELECT tenant_id, game_id, currency_code, COUNT(*) AS account_count,
           SUM(IF(owner_type = 'PLAYER', 1, 0)) AS player_account_count,
           SUM(IF(owner_type = 'PLAYER', balance_microunits, 0)) AS player_balance_microunits,
           SUM(IF(owner_type = 'TREASURY', balance_microunits, 0)) AS treasury_balance_microunits,
           SUM(balance_microunits) AS total_balance_microunits,
           MAX(balance_recorded_at) AS balance_freshness_at
    FROM yshopping_dim.dim_canonical_gamification_currency_account_current
    GROUP BY tenant_id, game_id, currency_code
), economy_key AS (
    SELECT tenant_id, game_id, currency_code FROM transaction_summary
    UNION
    SELECT tenant_id, game_id, currency_code FROM account_summary
)
SELECT k.tenant_id, k.game_id, k.currency_code,
       COALESCE(a.account_count, 0) AS account_count,
       COALESCE(a.player_account_count, 0) AS player_account_count,
       COALESCE(a.player_balance_microunits, 0) AS player_balance_microunits,
       COALESCE(a.treasury_balance_microunits, 0) AS treasury_balance_microunits,
       COALESCE(a.total_balance_microunits, 0) AS total_balance_microunits,
       COALESCE(t.transaction_count, 0) AS transaction_count,
       COALESCE(t.transferred_microunits, 0) AS transferred_microunits,
       COALESCE(t.ledger_entry_count, 0) AS ledger_entry_count,
       COALESCE(t.ledger_delta_sum_microunits, 0) AS ledger_delta_sum_microunits,
       COALESCE(t.draw_charge_count, 0) AS draw_charge_count,
       COALESCE(t.draw_charge_microunits, 0) AS draw_charge_microunits,
       COALESCE(t.currency_reward_transaction_count, 0) AS currency_reward_transaction_count,
       COALESCE(t.currency_reward_microunits, 0) AS currency_reward_microunits,
       COALESCE(t.gift_transaction_count, 0) AS gift_transaction_count,
       COALESCE(t.gift_microunits, 0) AS gift_microunits,
       COALESCE(t.redemption_transaction_count, 0) AS redemption_transaction_count,
       COALESCE(t.redemption_microunits, 0) AS redemption_microunits,
       GREATEST(COALESCE(a.balance_freshness_at, '1970-01-01 00:00:00'),
                COALESCE(t.ledger_freshness_at, '1970-01-01 00:00:00')) AS data_freshness_at
FROM economy_key k
LEFT JOIN account_summary a ON a.tenant_id = k.tenant_id AND a.game_id = k.game_id AND a.currency_code = k.currency_code
LEFT JOIN transaction_summary t ON t.tenant_id = k.tenant_id AND t.game_id = k.game_id AND t.currency_code = k.currency_code;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_gamification_collectible_balance_current AS
SELECT o.tenant_id, o.game_id, o.principal_id, o.ownership_id,
       o.collectible_definition_id, o.collectible_version,
       d.collectible_code, d.collectible_kind, d.collectible_name, o.quantity,
       o.occurred_at AS balance_observed_at, o.recorded_at AS balance_recorded_at
FROM yshopping_dim.dim_canonical_gamification_collectible_ownership_current o
LEFT JOIN yshopping_dim.dim_canonical_gamification_collectible_version_history d
  ON d.tenant_id = o.tenant_id
 AND d.collectible_definition_id = o.collectible_definition_id
 AND d.collectible_version = o.collectible_version;

CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_gamification_reward_delivery_current AS
SELECT c.tenant_id, c.game_id, c.principal_id, c.reward_claim_id,
       c.reward_definition_id, c.reward_version, c.current_status AS claim_status,
       c.reward_grant_id, c.source_type, c.source_id, c.claimed_at, c.claim_expires_at,
       r.reward_kind, r.asset_class, r.asset_code,
       r.currency_amount_microunits, r.fragment_quantity,
       c.recorded_at AS claim_freshness_at
FROM yshopping_dim.dim_canonical_gamification_reward_claim_current c
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_reward_grant_event r
  ON r.tenant_id = c.tenant_id AND r.reward_grant_id = c.reward_grant_id;

-- The redemption read model exposes only game-side source debits and opaque Mall adapter
-- evidence. It deliberately contains no external balance, external amount or settlement value.
CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_gamification_redemption_current AS
SELECT r.tenant_id, r.game_id, r.principal_id, r.redemption_intent_id,
       r.adapter_code, r.source_asset_class,
       r.collectible_definition_id, r.collectible_version, r.quantity,
       r.currency_code, r.amount_microunits,
       r.external_intent_ref, r.external_result_ref, r.current_status,
       r.source_ledger_transaction_id,
       c.collectible_entry_id AS source_collectible_entry_id,
       l.business_type AS source_ledger_business_type,
       l.business_id AS source_ledger_business_id,
       debit.owner_type AS source_debit_owner_type,
       debit.owner_ref AS source_debit_owner_ref,
       credit.owner_type AS source_credit_owner_type,
       r.contains_external_balance,
       r.occurred_at, r.recorded_at AS data_freshness_at
FROM yshopping_dim.dim_canonical_gamification_redemption_current r
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_collectible_ownership_event c
  ON c.tenant_id = r.tenant_id
 AND c.source_type = 'REDEMPTION'
 AND c.source_id = r.redemption_intent_id
LEFT JOIN yshopping_dwd.dwd_canonical_gamification_currency_transaction_event l
  ON l.tenant_id = r.tenant_id
 AND l.ledger_transaction_id = r.source_ledger_transaction_id
LEFT JOIN yshopping_dim.dim_canonical_gamification_currency_account_current debit
  ON debit.tenant_id = l.tenant_id AND debit.account_id = l.debit_account_id
LEFT JOIN yshopping_dim.dim_canonical_gamification_currency_account_current credit
  ON credit.tenant_id = l.tenant_id AND credit.account_id = l.credit_account_id;

-- Reproducible input for the legacy 金币榜. The ledger/account model remains the SoR;
-- this view only exposes one current player balance per tenant/game/currency/player.
CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_gamification_currency_leaderboard_input_current AS
SELECT a.tenant_id, a.game_id, a.currency_code, a.owner_ref AS principal_id,
       a.account_id, a.balance_microunits,
       MAX(a.balance_recorded_at) OVER (
           PARTITION BY a.tenant_id, a.game_id, a.currency_code
       ) AS as_of_time,
       a.balance_recorded_at AS data_freshness_at
FROM yshopping_dim.dim_canonical_gamification_currency_account_current a
WHERE a.owner_type = 'PLAYER'
  AND a.status = 'ACTIVE'
  AND a.asset_class = 'GAME_VIRTUAL_CURRENCY';

-- Reproducible daily input for the legacy 礼物榜. Direction is explicit, and every
-- contribution comes from an immutable, DQC-validated GiftTransfer event.
CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_gamification_gift_leaderboard_1d AS
SELECT tenant_id, game_id, currency_code, leaderboard_role, principal_id,
       window_start, DATE_ADD(window_start, INTERVAL 1 DAY) AS window_end,
       COUNT(*) AS transfer_count,
       SUM(amount_microunits) AS transfer_microunits,
       MIN(occurred_at) AS first_transfer_at,
       MAX(occurred_at) AS last_transfer_at,
       MAX(recorded_at) AS data_freshness_at
FROM (
    SELECT tenant_id, game_id, currency_code, 'SENDER' AS leaderboard_role,
           from_principal_id AS principal_id, CAST(occurred_at AS DATE) AS window_start,
           amount_microunits, occurred_at, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_gift_event
    UNION ALL
    SELECT tenant_id, game_id, currency_code, 'RECEIVER' AS leaderboard_role,
           to_principal_id AS principal_id, CAST(occurred_at AS DATE) AS window_start,
           amount_microunits, occurred_at, recorded_at
    FROM yshopping_dwd.dwd_canonical_gamification_gift_event
) gift_direction
GROUP BY tenant_id, game_id, currency_code, leaderboard_role, principal_id, window_start;

-- Leaderboard is a lakehouse-derived read model; no leaderboard write authority exists in OLTP.
CREATE OR REPLACE VIEW yshopping_dws.dws_canonical_gamification_season_leaderboard_current AS
SELECT tenant_id, game_id, season_id, season_version, principal_id,
       completed_round_count, win_count, score_total,
       RANK() OVER (PARTITION BY tenant_id, season_id, season_version
                    ORDER BY score_total DESC, win_count DESC, principal_id ASC) AS score_rank,
       data_freshness_at
FROM (
    SELECT s.tenant_id, s.game_id, s.season_id, s.season_version, r.principal_id,
           COUNT(*) AS completed_round_count,
           SUM(IF(r.outcome = 'WIN', 1, 0)) AS win_count,
           SUM(COALESCE(r.score, 0)) AS score_total,
           MAX(r.recorded_at) AS data_freshness_at
    FROM yshopping_dim.dim_canonical_gamification_season_current s
    JOIN yshopping_dwd.dwd_canonical_gamification_round_event r
      ON r.tenant_id = s.tenant_id AND r.game_id = s.game_id
     AND r.current_status = 'COMPLETED'
     AND r.occurred_at >= s.starts_at AND r.occurred_at < s.ends_at
    GROUP BY s.tenant_id, s.game_id, s.season_id, s.season_version, r.principal_id
) rank_source;
