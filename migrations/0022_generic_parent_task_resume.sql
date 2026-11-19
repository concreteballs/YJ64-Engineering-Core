-- Generic durable child-to-parent result handoff.
-- This migration is declarative only; it is not applied to any live database.
CREATE TABLE IF NOT EXISTS public.yj64_parent_task_resume_events (
    resume_event_id BIGSERIAL PRIMARY KEY,
    parent_task_id BIGINT NOT NULL REFERENCES public.yj64_task_queue(task_id) ON DELETE RESTRICT,
    child_task_id BIGINT NOT NULL UNIQUE REFERENCES public.yj64_task_queue(task_id) ON DELETE RESTRICT,
    protocol_version TEXT NOT NULL CHECK (length(protocol_version) BETWEEN 1 AND 128),
    correlation_key TEXT NOT NULL CHECK (length(correlation_key) BETWEEN 1 AND 256),
    result_artifact_ref TEXT NOT NULL CHECK (length(result_artifact_ref) BETWEEN 1 AND 1024),
    result_sha256 CHAR(64) NOT NULL CHECK (result_sha256 ~ '^[0-9a-f]{64}$'),
    result_status TEXT NOT NULL CHECK (result_status IN ('completed', 'blocked', 'failed', 'cancelled')),
    event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    consumed_at TIMESTAMPTZ,
    CONSTRAINT yj64_parent_resume_parent_correlation_unique
        UNIQUE (parent_task_id, correlation_key)
);

CREATE INDEX IF NOT EXISTS yj64_parent_resume_pending_idx
    ON public.yj64_parent_task_resume_events(parent_task_id, created_at)
    WHERE consumed_at IS NULL;

ALTER TABLE public.yj64_parent_task_resume_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.yj64_parent_task_resume_events FROM anon, authenticated, PUBLIC;
GRANT ALL ON TABLE public.yj64_parent_task_resume_events TO service_role;
REVOKE ALL ON SEQUENCE public.yj64_parent_task_resume_events_resume_event_id_seq
    FROM anon, authenticated, PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE public.yj64_parent_task_resume_events_resume_event_id_seq
    TO service_role;
