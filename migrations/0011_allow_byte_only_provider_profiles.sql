-- A byte-size ceiling is a valid standalone provider request constraint.
ALTER TABLE yj64_provider_limit_profiles
    DROP CONSTRAINT IF EXISTS yj64_provider_limit_profiles_check;
ALTER TABLE yj64_provider_limit_profiles
    ADD CONSTRAINT yj64_provider_limit_profiles_has_limit
    CHECK (
        requests_per_minute IS NOT NULL
        OR tokens_per_minute IS NOT NULL
        OR max_concurrency IS NOT NULL
        OR max_input_tokens IS NOT NULL
        OR max_output_tokens IS NOT NULL
        OR max_payload_bytes IS NOT NULL
    );
