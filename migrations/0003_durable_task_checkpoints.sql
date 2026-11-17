-- Durable, append-only task checkpoints. Apply after 0001 and the RLS migration.
CREATE TABLE IF NOT EXISTS yj64_task_checkpoints (
    checkpoint_id BIGSERIAL PRIMARY KEY,
    queue_task_id BIGINT NOT NULL
        REFERENCES yj64_task_queue(task_id) ON DELETE RESTRICT,
    sequence BIGINT NOT NULL CHECK (sequence > 0),
    schema_version TEXT NOT NULL,
    checkpoint_hash CHAR(64) NOT NULL
        CHECK (checkpoint_hash ~ '^[0-9a-f]{64}$'),
    previous_checkpoint_hash CHAR(64)
        CHECK (previous_checkpoint_hash IS NULL OR previous_checkpoint_hash ~ '^[0-9a-f]{64}$'),
    checkpoint JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT yj64_task_checkpoints_sequence_unique UNIQUE (queue_task_id, sequence),
    CONSTRAINT yj64_task_checkpoints_hash_unique UNIQUE (queue_task_id, checkpoint_hash)
);

CREATE INDEX IF NOT EXISTS yj64_task_checkpoints_latest_idx
    ON yj64_task_checkpoints (queue_task_id, sequence DESC);

ALTER TABLE yj64_task_checkpoints ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE yj64_task_checkpoints FROM anon, authenticated;
GRANT SELECT, INSERT ON TABLE yj64_task_checkpoints TO service_role;
GRANT USAGE, SELECT ON SEQUENCE yj64_task_checkpoints_checkpoint_id_seq TO service_role;
