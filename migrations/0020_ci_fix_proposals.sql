-- Durable, review-gated repair plans derived from validated CI analyses.
CREATE TABLE IF NOT EXISTS public.yj64_ci_fix_proposals (
    proposal_id BIGSERIAL PRIMARY KEY,
    proposal_task_id BIGINT NOT NULL UNIQUE
        REFERENCES public.yj64_task_queue(task_id) ON DELETE RESTRICT,
    analysis_task_id BIGINT NOT NULL UNIQUE
        REFERENCES public.yj64_task_queue(task_id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL
        REFERENCES public.yj64_ci_events(event_id) ON DELETE RESTRICT,
    proposal_status TEXT NOT NULL
        CHECK (proposal_status IN ('awaiting_review', 'needs_more_evidence', 'approved', 'rejected', 'implemented')),
    proposal_json JSONB NOT NULL,
    proposal_artifact_ref TEXT NOT NULL,
    proposal_sha256 CHAR(64) NOT NULL
        CHECK (proposal_sha256 ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewer TEXT,
    review_note TEXT
);

DO $
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'yj64_ci_fix_proposals_review_gate_check'
    ) THEN
        ALTER TABLE public.yj64_ci_fix_proposals
            ADD CONSTRAINT yj64_ci_fix_proposals_review_gate_check
            CHECK (
                proposal_json->>'proposal_status' = proposal_status
                AND proposal_json->'implementation'->>'auto_apply' = 'false'
                AND proposal_json->'implementation'->>'human_approval_required' = 'true'
                AND proposal_json->'implementation'->>'patch_ready' = 'false'
            );
    END IF;
END $;

CREATE INDEX IF NOT EXISTS yj64_ci_fix_proposals_status_idx
    ON public.yj64_ci_fix_proposals(proposal_status, created_at DESC);

ALTER TABLE public.yj64_ci_fix_proposals ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.yj64_ci_fix_proposals
    FROM anon, authenticated, PUBLIC;
GRANT ALL ON TABLE public.yj64_ci_fix_proposals TO service_role;

REVOKE ALL ON SEQUENCE public.yj64_ci_fix_proposals_proposal_id_seq
    FROM anon, authenticated, PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE public.yj64_ci_fix_proposals_proposal_id_seq
    TO service_role;
