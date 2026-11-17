-- Persist evidence and retrievable result references for ambiguous-delivery reconciliation.
ALTER TABLE yj64_provider_request_reservations
    ADD COLUMN IF NOT EXISTS resolution_kind TEXT
        CHECK (resolution_kind IS NULL OR resolution_kind IN ('provider_found', 'provider_not_found')),
    ADD COLUMN IF NOT EXISTS resolution_evidence_ref TEXT,
    ADD COLUMN IF NOT EXISTS provider_result_ref TEXT,
    ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
