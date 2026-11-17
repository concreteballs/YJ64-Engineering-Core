-- Link a provider response/error ledger entry to its durable request reservation.
ALTER TABLE yj64_model_request_attempts
    ADD COLUMN IF NOT EXISTS reservation_id TEXT
    REFERENCES yj64_provider_request_reservations(reservation_id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS yj64_model_request_attempts_reservation_idx
    ON yj64_model_request_attempts(reservation_id)
    WHERE reservation_id IS NOT NULL;
