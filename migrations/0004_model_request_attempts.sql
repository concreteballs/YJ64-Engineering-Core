-- Append-only, lease-bound metadata for external model requests.
-- Never store prompts, response bodies, credentials, or raw authorization headers.
CREATE TABLE IF NOT EXISTS yj64_model_request_attempts (
    attempt_id BIGSERIAL PRIMARY KEY,
    queue_task_id BIGINT NOT NULL
        REFERENCES yj64_task_queue(task_id) ON DELETE RESTRICT,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    provider_request_id TEXT,
    error_classification TEXT NOT NULL,
    http_status INTEGER CHECK (http_status IS NULL OR http_status BETWEEN 100 AND 599),
    retry_after_seconds INTEGER CHECK (retry_after_seconds IS NULL OR retry_after_seconds >= 0),
    quota_reset_at TIMESTAMPTZ,
    scheduled_retry_at TIMESTAMPTZ,
    safe_headers JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(safe_headers) = 'object'),
    error_summary TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT yj64_model_request_attempts_number_unique
        UNIQUE (queue_task_id, attempt_number)
);

CREATE UNIQUE INDEX IF NOT EXISTS yj64_model_request_attempts_request_id_unique
    ON yj64_model_request_attempts (provider, provider_request_id)
    WHERE provider_request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS yj64_model_request_attempts_task_created_idx
    ON yj64_model_request_attempts (queue_task_id, created_at DESC);

ALTER TABLE yj64_model_request_attempts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE yj64_model_request_attempts FROM anon, authenticated;
REVOKE ALL ON TABLE yj64_model_request_attempts FROM service_role;
GRANT SELECT, INSERT ON TABLE yj64_model_request_attempts TO service_role;
GRANT USAGE, SELECT ON SEQUENCE yj64_model_request_attempts_attempt_id_seq TO service_role;
