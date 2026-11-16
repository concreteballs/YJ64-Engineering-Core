-- Apply once to the Supabase/PostgreSQL project used by YJ64.
CREATE TABLE IF NOT EXISTS yj64_ci_events (
    event_id BIGSERIAL PRIMARY KEY,
    repository TEXT NOT NULL,
    run_id BIGINT NOT NULL,
    run_attempt INTEGER NOT NULL,
    workflow TEXT NOT NULL,
    conclusion TEXT NOT NULL,
    commit_sha CHAR(40) NOT NULL,
    branch TEXT NOT NULL,
    run_url TEXT NOT NULL,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT yj64_ci_events_identity UNIQUE (repository, run_id, run_attempt)
);

CREATE TABLE IF NOT EXISTS yj64_task_queue (
    task_id BIGSERIAL PRIMARY KEY,
    task_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'running', 'completed', 'failed', 'blocked', 'cancelled')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at TIMESTAMPTZ,
    lock_owner TEXT,
    last_error TEXT,
    dedupe_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS yj64_task_queue_claim_idx
    ON yj64_task_queue (state, available_at, task_id);
