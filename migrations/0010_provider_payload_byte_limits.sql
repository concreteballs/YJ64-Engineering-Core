-- Account for provider request body-size ceilings independently of token limits.
ALTER TABLE yj64_provider_limit_profiles
    ADD COLUMN IF NOT EXISTS max_payload_bytes BIGINT
    CHECK (max_payload_bytes IS NULL OR max_payload_bytes > 0);
ALTER TABLE yj64_provider_request_reservations
    ADD COLUMN IF NOT EXISTS payload_bytes BIGINT NOT NULL DEFAULT 0
    CHECK (payload_bytes >= 0);
