-- Canonical Gamification event facts. Only cloudmold-gamification GAME_* assets are admitted.
CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_game_created_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.game_code') AS game_code,
       get_json_string(payload, '$.game_name') AS game_name,
       CAST(get_json_string(payload, '$.definition_version') AS BIGINT) AS definition_version,
       get_json_string(payload, '$.current_status') AS current_status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.game.created' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_game_definition_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.game_code') AS game_code,
       CAST(get_json_string(payload, '$.game_version') AS BIGINT) AS game_version,
       get_json_string(payload, '$.definition_sha256') AS definition_sha256,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.virtual_currency_code') AS virtual_currency_code,
       CAST(get_json_string(payload, '$.assist_daily_limit') AS BIGINT) AS assist_daily_limit,
       CAST(get_json_string(payload, '$.max_rounds_per_session') AS BIGINT) AS max_rounds_per_session,
       CAST(get_json_string(payload, '$.session_ttl_seconds') AS BIGINT) AS session_ttl_seconds
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.game.definition_published' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_currency_account_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.account_id') AS account_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.owner_type') AS owner_type,
       get_json_string(payload, '$.owner_ref') AS owner_ref,
       get_json_string(payload, '$.asset_class') AS asset_class,
       get_json_string(payload, '$.currency_code') AS currency_code,
       CAST(get_json_string(payload, '$.balance_microunits') AS BIGINT) AS balance_microunits,
       get_json_string(payload, '$.status') AS status
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.virtual_currency.account_opened' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_currency_transaction_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.ledger_transaction_id') AS ledger_transaction_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.asset_class') AS asset_class,
       get_json_string(payload, '$.currency_code') AS currency_code,
       get_json_string(payload, '$.business_type') AS business_type,
       get_json_string(payload, '$.business_id') AS business_id,
       CAST(get_json_string(payload, '$.amount_microunits') AS BIGINT) AS amount_microunits,
       CAST(get_json_string(payload, '$.entry_count') AS BIGINT) AS entry_count,
       CAST(get_json_string(payload, '$.entry_delta_sum_microunits') AS BIGINT) AS entry_delta_sum_microunits,
       get_json_string(payload, '$.debit_account_id') AS debit_account_id,
       CAST(get_json_string(payload, '$.debit_balance_after_microunits') AS BIGINT) AS debit_balance_after_microunits,
       get_json_string(payload, '$.credit_account_id') AS credit_account_id,
       CAST(get_json_string(payload, '$.credit_balance_after_microunits') AS BIGINT) AS credit_balance_after_microunits
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.virtual_currency.ledger_posted' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_currency_ledger_entry_event AS
SELECT event_id, tenant_id, ledger_transaction_id, game_id, currency_code, business_type, business_id,
       debit_account_id AS account_id, 1 AS entry_sequence, -amount_microunits AS delta_microunits,
       debit_balance_after_microunits AS balance_after_microunits, occurred_at, recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_currency_transaction_event
UNION ALL
SELECT event_id, tenant_id, ledger_transaction_id, game_id, currency_code, business_type, business_id,
       credit_account_id AS account_id, 2 AS entry_sequence, amount_microunits AS delta_microunits,
       credit_balance_after_microunits AS balance_after_microunits, occurred_at, recorded_at
FROM yshopping_dwd.dwd_canonical_gamification_currency_transaction_event;

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_reward_definition_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.reward_definition_id') AS reward_definition_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.reward_code') AS reward_code,
       CAST(get_json_string(payload, '$.reward_version') AS BIGINT) AS reward_version,
       get_json_string(payload, '$.reward_kind') AS reward_kind,
       get_json_string(payload, '$.asset_class') AS asset_class,
       get_json_string(payload, '$.asset_code') AS asset_code,
       CAST(get_json_string(payload, '$.currency_amount_microunits') AS BIGINT) AS currency_amount_microunits,
       CAST(get_json_string(payload, '$.fragment_quantity') AS BIGINT) AS fragment_quantity,
       get_json_string(payload, '$.definition_sha256') AS definition_sha256
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.reward.definition_published' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_reward_grant_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.reward_grant_id') AS reward_grant_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.reward_definition_id') AS reward_definition_id,
       CAST(get_json_string(payload, '$.reward_version') AS BIGINT) AS reward_version,
       get_json_string(payload, '$.reward_kind') AS reward_kind,
       get_json_string(payload, '$.asset_class') AS asset_class,
       get_json_string(payload, '$.asset_code') AS asset_code,
       CAST(get_json_string(payload, '$.currency_amount_microunits') AS BIGINT) AS currency_amount_microunits,
       CAST(get_json_string(payload, '$.fragment_quantity') AS BIGINT) AS fragment_quantity,
       get_json_string(payload, '$.source_type') AS source_type,
       get_json_string(payload, '$.source_id') AS source_id,
       get_json_string(payload, '$.ledger_transaction_id') AS ledger_transaction_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.reward.granted' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_draw_pool_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.draw_pool_id') AS draw_pool_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.draw_pool_code') AS draw_pool_code,
       CAST(get_json_string(payload, '$.pool_version') AS BIGINT) AS pool_version,
       get_json_string(payload, '$.status') AS status,
       CAST(get_json_string(payload, '$.price_microunits') AS BIGINT) AS price_microunits,
       CAST(get_json_string(payload, '$.total_weight') AS BIGINT) AS total_weight,
       get_json_string(payload, '$.definition_sha256') AS definition_sha256
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.draw_pool.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_draw_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.draw_request_id') AS draw_request_id,
       get_json_string(payload, '$.draw_result_id') AS draw_result_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.draw_pool_id') AS draw_pool_id,
       CAST(get_json_string(payload, '$.draw_pool_version') AS BIGINT) AS draw_pool_version,
       CAST(get_json_string(payload, '$.price_microunits') AS BIGINT) AS price_microunits,
       CAST(get_json_string(payload, '$.selected_ticket') AS BIGINT) AS selected_ticket,
       CAST(get_json_string(payload, '$.total_weight') AS BIGINT) AS total_weight,
       get_json_string(payload, '$.entropy_sha256') AS entropy_sha256,
       get_json_string(payload, '$.reward_definition_id') AS reward_definition_id,
       CAST(get_json_string(payload, '$.reward_version') AS BIGINT) AS reward_version,
       get_json_string(payload, '$.reward_grant_id') AS reward_grant_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.draw.completed' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_session_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.session_id') AS session_id,
       get_json_string(payload, '$.game_id') AS game_id,
       CAST(get_json_string(payload, '$.game_version') AS BIGINT) AS game_version,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       CAST(get_json_string(payload, '$.round_count') AS BIGINT) AS round_count,
       CAST(get_json_string(payload, '$.expires_at') AS DATETIME) AS expires_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.session.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_round_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.round_id') AS round_id,
       get_json_string(payload, '$.session_id') AS session_id,
       get_json_string(payload, '$.game_id') AS game_id,
       CAST(get_json_string(payload, '$.game_version') AS BIGINT) AS game_version,
       get_json_string(payload, '$.principal_id') AS principal_id,
       CAST(get_json_string(payload, '$.round_number') AS BIGINT) AS round_number,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.outcome') AS outcome,
       CAST(get_json_string(payload, '$.score') AS BIGINT) AS score
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.round.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_assist_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.assist_record_id') AS assist_record_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.helper_principal_id') AS helper_principal_id,
       get_json_string(payload, '$.beneficiary_principal_id') AS beneficiary_principal_id,
       CAST(get_json_string(payload, '$.quota_date') AS DATE) AS quota_date,
       CAST(get_json_string(payload, '$.ordinal') AS BIGINT) AS ordinal,
       CAST(get_json_string(payload, '$.assist_limit') AS BIGINT) AS assist_limit,
       CAST(get_json_string(payload, '$.assists_used') AS BIGINT) AS assists_used
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.assist.recorded' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_task_definition_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.task_definition_id') AS task_definition_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.task_code') AS task_code,
       CAST(get_json_string(payload, '$.task_version') AS BIGINT) AS task_version,
       CAST(get_json_string(payload, '$.target_units') AS BIGINT) AS target_units,
       get_json_string(payload, '$.reward_definition_id') AS reward_definition_id,
       CAST(get_json_string(payload, '$.reward_version') AS BIGINT) AS reward_version,
       get_json_string(payload, '$.definition_sha256') AS definition_sha256
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.task.definition_published' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_task_progress_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.task_progress_id') AS task_progress_id,
       get_json_string(payload, '$.task_definition_id') AS task_definition_id,
       CAST(get_json_string(payload, '$.task_version') AS BIGINT) AS task_version,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       CAST(get_json_string(payload, '$.completed_units') AS BIGINT) AS completed_units,
       CAST(get_json_string(payload, '$.target_units') AS BIGINT) AS target_units,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.reward_grant_id') AS reward_grant_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.task.progress_changed' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_fragment_ledger_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.fragment_entry_id') AS fragment_entry_id,
       get_json_string(payload, '$.fragment_balance_id') AS fragment_balance_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.asset_class') AS asset_class,
       get_json_string(payload, '$.fragment_code') AS fragment_code,
       CAST(get_json_string(payload, '$.delta_quantity') AS BIGINT) AS delta_quantity,
       CAST(get_json_string(payload, '$.balance_after_quantity') AS BIGINT) AS balance_after_quantity,
       get_json_string(payload, '$.reward_grant_id') AS reward_grant_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.fragment.ledger_posted' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_gift_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.gift_transfer_id') AS gift_transfer_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.asset_class') AS asset_class,
       get_json_string(payload, '$.currency_code') AS currency_code,
       get_json_string(payload, '$.from_principal_id') AS from_principal_id,
       get_json_string(payload, '$.to_principal_id') AS to_principal_id,
       CAST(get_json_string(payload, '$.amount_microunits') AS BIGINT) AS amount_microunits,
       get_json_string(payload, '$.ledger_transaction_id') AS ledger_transaction_id,
       get_json_string(payload, '$.reason_code') AS reason_code
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.gift.transferred' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_season_series_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.season_series_id') AS season_series_id,
       CAST(get_json_string(payload, '$.series_version') AS BIGINT) AS series_version,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.series_code') AS series_code,
       get_json_string(payload, '$.series_name') AS series_name,
       get_json_string(payload, '$.definition_sha256') AS definition_sha256
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.season_series.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_season_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.season_id') AS season_id,
       CAST(get_json_string(payload, '$.season_version') AS BIGINT) AS season_version,
       get_json_string(payload, '$.season_series_id') AS season_series_id,
       CAST(get_json_string(payload, '$.series_version') AS BIGINT) AS series_version,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.season_code') AS season_code,
       get_json_string(payload, '$.season_name') AS season_name,
       get_json_string(payload, '$.status') AS status,
       CAST(get_json_string(payload, '$.starts_at') AS DATETIME) AS starts_at,
       CAST(get_json_string(payload, '$.ends_at') AS DATETIME) AS ends_at,
       get_json_string(payload, '$.definition_sha256') AS definition_sha256
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.season.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_collectible_definition_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.collectible_definition_id') AS collectible_definition_id,
       CAST(get_json_string(payload, '$.collectible_version') AS BIGINT) AS collectible_version,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.collectible_code') AS collectible_code,
       get_json_string(payload, '$.collectible_kind') AS collectible_kind,
       get_json_string(payload, '$.collectible_name') AS collectible_name,
       get_json_string(payload, '$.definition_sha256') AS definition_sha256
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.collectible.version_published' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_collectible_ownership_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.collectible_entry_id') AS collectible_entry_id,
       get_json_string(payload, '$.ownership_id') AS ownership_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.collectible_definition_id') AS collectible_definition_id,
       CAST(get_json_string(payload, '$.collectible_version') AS BIGINT) AS collectible_version,
       CAST(get_json_string(payload, '$.delta_quantity') AS BIGINT) AS delta_quantity,
       CAST(get_json_string(payload, '$.quantity') AS BIGINT) AS quantity,
       get_json_string(payload, '$.source_type') AS source_type,
       get_json_string(payload, '$.source_id') AS source_id
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.collectible.ownership_changed' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_redemption_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.redemption_intent_id') AS redemption_intent_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.adapter_code') AS adapter_code,
       get_json_string(payload, '$.source_asset_class') AS source_asset_class,
       get_json_string(payload, '$.collectible_definition_id') AS collectible_definition_id,
       CAST(get_json_string(payload, '$.collectible_version') AS BIGINT) AS collectible_version,
       CAST(get_json_string(payload, '$.quantity') AS BIGINT) AS quantity,
       get_json_string(payload, '$.currency_code') AS currency_code,
       CAST(get_json_string(payload, '$.amount_microunits') AS BIGINT) AS amount_microunits,
       get_json_string(payload, '$.external_intent_ref') AS external_intent_ref,
       get_json_string(payload, '$.external_result_ref') AS external_result_ref,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.source_ledger_transaction_id') AS source_ledger_transaction_id,
       CAST(get_json_string(payload, '$.contains_external_balance') AS BOOLEAN) AS contains_external_balance
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.redemption.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';

CREATE OR REPLACE VIEW yshopping_dwd.dwd_canonical_gamification_reward_claim_event AS
SELECT event_id, tenant_id, aggregate_id, aggregate_version, occurred_at, recorded_at,
       correlation_id, causation_id, idempotency_key,
       get_json_string(payload, '$.reward_claim_id') AS reward_claim_id,
       get_json_string(payload, '$.game_id') AS game_id,
       get_json_string(payload, '$.principal_id') AS principal_id,
       get_json_string(payload, '$.reward_definition_id') AS reward_definition_id,
       CAST(get_json_string(payload, '$.reward_version') AS BIGINT) AS reward_version,
       get_json_string(payload, '$.previous_status') AS previous_status,
       get_json_string(payload, '$.current_status') AS current_status,
       get_json_string(payload, '$.reward_grant_id') AS reward_grant_id,
       get_json_string(payload, '$.source_type') AS source_type,
       get_json_string(payload, '$.source_id') AS source_id,
       CAST(get_json_string(payload, '$.claimed_at') AS DATETIME) AS claimed_at,
       CAST(get_json_string(payload, '$.claim_expires_at') AS DATETIME) AS claim_expires_at
FROM yshopping_dwd.dwd_domain_event
WHERE event_type = 'gamification.reward_claim.status_changed' AND schema_version = 1
  AND source_system = 'cloudmold-gamification';
