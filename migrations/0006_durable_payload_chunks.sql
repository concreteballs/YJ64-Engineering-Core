-- Durable payload manifests, immutable chunks and idempotent transport acknowledgements.
CREATE TABLE IF NOT EXISTS yj64_payload_manifests (
    payload_id TEXT PRIMARY KEY,
    queue_task_id BIGINT NOT NULL
        REFERENCES yj64_task_queue(task_id) ON DELETE RESTRICT,
    protocol_version INTEGER NOT NULL CHECK (protocol_version = 1),
    total_chunks INTEGER NOT NULL CHECK (total_chunks > 0),
    total_sha256 CHAR(64) NOT NULL CHECK (total_sha256 ~ '^[0-9a-f]{64}$'),
    manifest JSONB NOT NULL CHECK (jsonb_typeof(manifest) = 'object'),
    state TEXT NOT NULL DEFAULT 'receiving'
        CHECK (state IN ('receiving', 'ready_for_model', 'blocked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (queue_task_id, payload_id)
);

CREATE TABLE IF NOT EXISTS yj64_payload_chunks (
    payload_id TEXT NOT NULL
        REFERENCES yj64_payload_manifests(payload_id) ON DELETE RESTRICT,
    chunk_id CHAR(64) NOT NULL CHECK (chunk_id ~ '^[0-9a-f]{64}$'),
    chunk_index INTEGER NOT NULL CHECK (chunk_index > 0),
    chunk_sha256 CHAR(64) NOT NULL CHECK (chunk_sha256 ~ '^[0-9a-f]{64}$'),
    content TEXT NOT NULL,
    estimated_tokens INTEGER NOT NULL CHECK (estimated_tokens >= 0),
    character_count INTEGER NOT NULL CHECK (character_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (payload_id, chunk_id),
    UNIQUE (payload_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS yj64_payload_chunk_acks (
    payload_id TEXT NOT NULL,
    chunk_id CHAR(64) NOT NULL,
    acknowledged_sha256 CHAR(64) NOT NULL
        CHECK (acknowledged_sha256 ~ '^[0-9a-f]{64}$'),
    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (payload_id, chunk_id),
    FOREIGN KEY (payload_id, chunk_id)
        REFERENCES yj64_payload_chunks(payload_id, chunk_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS yj64_payload_manifests_task_idx
    ON yj64_payload_manifests (queue_task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS yj64_payload_chunks_order_idx
    ON yj64_payload_chunks (payload_id, chunk_index);

ALTER TABLE yj64_payload_manifests ENABLE ROW LEVEL SECURITY;
ALTER TABLE yj64_payload_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE yj64_payload_chunk_acks ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE yj64_payload_manifests FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE yj64_payload_chunks FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE yj64_payload_chunk_acks FROM anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE yj64_payload_manifests TO service_role;
GRANT SELECT, INSERT ON TABLE yj64_payload_chunks TO service_role;
GRANT SELECT, INSERT ON TABLE yj64_payload_chunk_acks TO service_role;
