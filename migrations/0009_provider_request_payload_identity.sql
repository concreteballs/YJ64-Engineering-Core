-- Bind every provider idempotency key to the exact assembled request content.
ALTER TABLE yj64_provider_request_reservations
    ADD COLUMN IF NOT EXISTS request_payload_sha256 CHAR(64);
UPDATE yj64_provider_request_reservations
SET request_payload_sha256 = repeat('0', 64)
WHERE request_payload_sha256 IS NULL;
ALTER TABLE yj64_provider_request_reservations
    ALTER COLUMN request_payload_sha256 SET NOT NULL;
ALTER TABLE yj64_provider_request_reservations
    ADD CONSTRAINT yj64_provider_reservation_payload_hash_check
    CHECK (request_payload_sha256 ~ '^[0-9a-f]{64}$');
