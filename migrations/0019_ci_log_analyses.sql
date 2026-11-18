-- Persist structured LLM diagnostics separately from raw provider responses.
CREATE TABLE IF NOT EXISTS public.yj64_ci_log_analyses (
    analysis_id BIGSERIAL PRIMARY KEY,
    analysis_task_id BIGINT NOT NULL UNIQUE
        REFERENCES public.yj64_task_queue(task_id) ON DELETE RESTRICT,
    source_task_id BIGINT NOT NULL
        REFERENCES public.yj64_task_queue(task_id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL
        REFERENCES public.yj64_ci_events(event_id) ON DELETE RESTRICT,
    payload_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    provider_reservation_id TEXT NOT NULL,
    provider_request_id TEXT,
    provider_response_artifact_ref TEXT NOT NULL,
    analysis_artifact_ref TEXT NOT NULL,
    analysis_sha256 CHAR(64) NOT NULL
        CHECK (analysis_sha256 ~ '^[0-9a-f]{64}$'),
    analysis_status TEXT NOT NULL
        CHECK (analysis_status IN ('completed', 'invalid_response')),
    analysis_json JSONB NOT NULL,
    input_tokens BIGINT NOT NULL CHECK (input_tokens >= 0),
    output_tokens BIGINT NOT NULL CHECK (output_tokens >= 0),
    actual_cost_usd NUMERIC(18,8) NOT NULL DEFAULT 0
        CHECK (actual_cost_usd >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS yj64_ci_log_analyses_event_idx
    ON public.yj64_ci_log_analyses(event_id, created_at DESC);

ALTER TABLE public.yj64_ci_log_analyses ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.yj64_ci_log_analyses
    FROM anon, authenticated, PUBLIC;
GRANT ALL ON TABLE public.yj64_ci_log_analyses TO service_role;

REVOKE ALL ON SEQUENCE public.yj64_ci_log_analyses_analysis_id_seq
    FROM anon, authenticated, PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE public.yj64_ci_log_analyses_analysis_id_seq
    TO service_role;
