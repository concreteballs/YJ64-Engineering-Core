-- Model profiles can share provider-account quotas across multiple models.
ALTER TABLE yj64_provider_limit_profiles
    ADD COLUMN IF NOT EXISTS capacity_scope TEXT,
    ADD COLUMN IF NOT EXISTS valid_until TIMESTAMPTZ;
UPDATE yj64_provider_limit_profiles
SET capacity_scope = provider || ':' || model || ':' || endpoint
WHERE capacity_scope IS NULL OR capacity_scope = '';
ALTER TABLE yj64_provider_limit_profiles
    ALTER COLUMN capacity_scope SET NOT NULL;

ALTER TABLE yj64_provider_request_reservations
    ADD COLUMN IF NOT EXISTS capacity_scope TEXT;
UPDATE yj64_provider_request_reservations AS reservation
SET capacity_scope = profile.capacity_scope
FROM yj64_provider_limit_profiles AS profile
WHERE profile.provider = reservation.provider
  AND profile.model = reservation.model
  AND profile.endpoint = reservation.endpoint
  AND reservation.capacity_scope IS NULL;
ALTER TABLE yj64_provider_request_reservations
    ALTER COLUMN capacity_scope SET NOT NULL;

CREATE INDEX IF NOT EXISTS yj64_provider_reservation_scope_window_idx
    ON yj64_provider_request_reservations(capacity_scope, sent_at DESC)
    WHERE sent_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS yj64_provider_reservation_scope_active_idx
    ON yj64_provider_request_reservations(capacity_scope, state, expires_at)
    WHERE state IN ('reserved', 'sending', 'accepted', 'unknown');
