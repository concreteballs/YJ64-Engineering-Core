-- Enforce response-artifact and reconciliation invariants in the database itself.
ALTER TABLE yj64_provider_request_reservations
    ADD CONSTRAINT yj64_provider_reservation_completed_has_artifact
        CHECK (state <> 'completed' OR provider_result_ref IS NOT NULL),
    ADD CONSTRAINT yj64_provider_reservation_sent_state_has_timestamp
        CHECK (state NOT IN ('sending', 'accepted', 'completed', 'failed', 'unknown')
               OR sent_at IS NOT NULL),
    ADD CONSTRAINT yj64_provider_reservation_reserved_not_sent
        CHECK (state <> 'reserved' OR sent_at IS NULL),
    ADD CONSTRAINT yj64_provider_reservation_reconciliation_evidence
        CHECK (
            resolution_kind IS NULL
            OR (resolution_evidence_ref IS NOT NULL AND resolved_at IS NOT NULL)
        ),
    ADD CONSTRAINT yj64_provider_reservation_found_has_artifact
        CHECK (resolution_kind <> 'provider_found' OR provider_result_ref IS NOT NULL),
    ADD CONSTRAINT yj64_provider_reservation_not_found_has_no_artifact
        CHECK (resolution_kind <> 'provider_not_found' OR provider_result_ref IS NULL);
