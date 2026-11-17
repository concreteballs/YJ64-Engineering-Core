-- Persistent task deadlines and per-task/global provider request-count budgets.
ALTER TABLE yj64_task_queue
    ADD COLUMN IF NOT EXISTS deadline_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS max_provider_requests INTEGER,
    ADD COLUMN IF NOT EXISTS provider_requests_reserved INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS provider_requests_consumed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE yj64_task_queue
    ADD CONSTRAINT yj64_task_queue_request_budget_nonnegative
    CHECK (
        (max_provider_requests IS NULL OR max_provider_requests >= 0)
        AND provider_requests_reserved >= 0
        AND provider_requests_consumed >= 0
    );

ALTER TABLE yj64_cycle_usage_budget
    ADD COLUMN IF NOT EXISTS daily_request_limit BIGINT
        CHECK (daily_request_limit IS NULL OR daily_request_limit >= 0),
    ADD COLUMN IF NOT EXISTS monthly_request_limit BIGINT
        CHECK (monthly_request_limit IS NULL OR monthly_request_limit >= 0);
