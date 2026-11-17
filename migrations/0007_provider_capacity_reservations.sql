-- Durable provider capacity profiles, request reservations and persistent task budgets.
ALTER TABLE yj64_task_queue
    ADD COLUMN IF NOT EXISTS budget_input_tokens BIGINT,
    ADD COLUMN IF NOT EXISTS budget_output_tokens BIGINT,
    ADD COLUMN IF NOT EXISTS budget_cost_usd NUMERIC(18,8),
    ADD COLUMN IF NOT EXISTS reserved_input_tokens BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reserved_output_tokens BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reserved_cost_usd NUMERIC(18,8) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS consumed_input_tokens BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS consumed_output_tokens BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS consumed_cost_usd NUMERIC(18,8) NOT NULL DEFAULT 0;

ALTER TABLE yj64_task_queue
    ADD CONSTRAINT yj64_task_queue_budget_nonnegative
    CHECK (
        (budget_input_tokens IS NULL OR budget_input_tokens >= 0)
        AND (budget_output_tokens IS NULL OR budget_output_tokens >= 0)
        AND (budget_cost_usd IS NULL OR budget_cost_usd >= 0)
        AND reserved_input_tokens >= 0 AND reserved_output_tokens >= 0
        AND reserved_cost_usd >= 0
        AND consumed_input_tokens >= 0 AND consumed_output_tokens >= 0
        AND consumed_cost_usd >= 0
    );

CREATE TABLE IF NOT EXISTS yj64_provider_limit_profiles (
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    requests_per_minute INTEGER CHECK (requests_per_minute IS NULL OR requests_per_minute > 0),
    tokens_per_minute INTEGER CHECK (tokens_per_minute IS NULL OR tokens_per_minute > 0),
    max_concurrency INTEGER CHECK (max_concurrency IS NULL OR max_concurrency > 0),
    max_input_tokens INTEGER CHECK (max_input_tokens IS NULL OR max_input_tokens > 0),
    max_output_tokens INTEGER CHECK (max_output_tokens IS NULL OR max_output_tokens > 0),
    tokens_per_minute_includes_output BOOLEAN NOT NULL DEFAULT TRUE,
    input_cost_per_million_usd NUMERIC(18,8) CHECK (input_cost_per_million_usd IS NULL OR input_cost_per_million_usd >= 0),
    output_cost_per_million_usd NUMERIC(18,8) CHECK (output_cost_per_million_usd IS NULL OR output_cost_per_million_usd >= 0),
    profile_source TEXT NOT NULL DEFAULT 'operator_config'
        CHECK (profile_source IN ('operator_config', 'provider_api', 'verified_observation')),
    observed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, model, endpoint),
    CHECK (
        requests_per_minute IS NOT NULL OR tokens_per_minute IS NOT NULL
        OR max_concurrency IS NOT NULL OR max_input_tokens IS NOT NULL
        OR max_output_tokens IS NOT NULL
    )
);

CREATE TABLE IF NOT EXISTS yj64_cycle_usage_budget (
    budget_id SMALLINT PRIMARY KEY CHECK (budget_id = 1),
    daily_token_limit BIGINT CHECK (daily_token_limit IS NULL OR daily_token_limit >= 0),
    monthly_token_limit BIGINT CHECK (monthly_token_limit IS NULL OR monthly_token_limit >= 0),
    daily_cost_limit_usd NUMERIC(18,8) CHECK (daily_cost_limit_usd IS NULL OR daily_cost_limit_usd >= 0),
    monthly_cost_limit_usd NUMERIC(18,8) CHECK (monthly_cost_limit_usd IS NULL OR monthly_cost_limit_usd >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS yj64_provider_request_reservations (
    reservation_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    queue_task_id BIGINT NOT NULL REFERENCES yj64_task_queue(task_id) ON DELETE RESTRICT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    input_tokens_estimated BIGINT NOT NULL CHECK (input_tokens_estimated >= 0),
    output_tokens_estimated BIGINT NOT NULL CHECK (output_tokens_estimated >= 0),
    estimated_cost_usd NUMERIC(18,8) NOT NULL CHECK (estimated_cost_usd >= 0),
    input_tokens_actual BIGINT CHECK (input_tokens_actual IS NULL OR input_tokens_actual >= 0),
    output_tokens_actual BIGINT CHECK (output_tokens_actual IS NULL OR output_tokens_actual >= 0),
    actual_cost_usd NUMERIC(18,8) CHECK (actual_cost_usd IS NULL OR actual_cost_usd >= 0),
    state TEXT NOT NULL CHECK (state IN ('reserved', 'sending', 'accepted', 'completed', 'failed', 'unknown', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    provider_request_id TEXT,
    last_error_classification TEXT,
    FOREIGN KEY (provider, model, endpoint)
        REFERENCES yj64_provider_limit_profiles(provider, model, endpoint)
        ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS yj64_provider_reservation_request_id_unique
    ON yj64_provider_request_reservations(provider, provider_request_id)
    WHERE provider_request_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS yj64_provider_reservation_window_idx
    ON yj64_provider_request_reservations(provider, model, endpoint, sent_at DESC)
    WHERE sent_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS yj64_provider_reservation_active_idx
    ON yj64_provider_request_reservations(provider, model, endpoint, state, expires_at)
    WHERE state IN ('reserved', 'sending', 'accepted', 'unknown');
CREATE INDEX IF NOT EXISTS yj64_provider_reservation_task_idx
    ON yj64_provider_request_reservations(queue_task_id, created_at DESC);

ALTER TABLE yj64_provider_limit_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE yj64_cycle_usage_budget ENABLE ROW LEVEL SECURITY;
ALTER TABLE yj64_provider_request_reservations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE yj64_provider_limit_profiles FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE yj64_cycle_usage_budget FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE yj64_provider_request_reservations FROM anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE yj64_provider_limit_profiles TO service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE yj64_cycle_usage_budget TO service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE yj64_provider_request_reservations TO service_role;
