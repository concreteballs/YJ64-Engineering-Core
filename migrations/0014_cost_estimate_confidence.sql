-- Distinguish a genuinely zero-cost estimate from unknown provider pricing.
ALTER TABLE yj64_provider_request_reservations
    ADD COLUMN IF NOT EXISTS cost_estimate_known BOOLEAN NOT NULL DEFAULT FALSE;
