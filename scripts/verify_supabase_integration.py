"""Live smoke check for the YJ64 Supabase database and private artifact bucket.

Run only from a trusted server/CI environment with the three required secrets.
The test writes one deterministic, content-addressed smoke artifact and verifies
that the exact bytes can be read back. It never prints credentials.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import psycopg

from yj64_engineering_core.automation.supabase_storage import (
    SupabaseStorageArtifactStore,
)

REQUIRED_TABLES = (
    "yj64_ci_events",
    "yj64_task_queue",
    "yj64_task_checkpoints",
    "yj64_model_request_attempts",
    "yj64_provider_limit_profiles",
    "yj64_provider_request_reservations",
    "yj64_cycle_usage_budget",
    "yj64_payload_manifests",
    "yj64_payload_chunks",
    "yj64_payload_chunk_acks",
)


def main() -> int:
    database_url = os.environ.get("YJ64_DATABASE_URL", "").strip()
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    missing = [
        name for name, value in (
            ("YJ64_DATABASE_URL", database_url),
            ("SUPABASE_URL", supabase_url),
            ("SUPABASE_SERVICE_ROLE_KEY", service_role_key),
        ) if not value
    ]
    if missing:
        print("Missing required CI secrets: " + ", ".join(missing), file=sys.stderr)
        return 2

    try:
        with psycopg.connect(database_url, prepare_threshold=None) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT current_database(),
                           array_agg(to_regclass('public.' || table_name)::text)
                    FROM unnest(%s::text[]) AS required(table_name)
                    """,
                    (list(REQUIRED_TABLES),),
                )
                database_name, found_tables = cursor.fetchone()
                if not found_tables or len(found_tables) != len(REQUIRED_TABLES) or any(
                    item is None for item in found_tables
                ):
                    raise RuntimeError("one or more required YJ64 tables are missing")

        payload = json.dumps(
            {
                "protocol": "yj64-supabase-live-smoke-v1",
                "repository": "concreteballs/YJ64-Engineering-Core",
                "purpose": "private-storage-roundtrip",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected_hash = hashlib.sha256(payload).hexdigest()
        store = SupabaseStorageArtifactStore(
            supabase_url=supabase_url,
            service_role_key=service_role_key,
            bucket="yj64-private-artifacts",
        )
        artifact_ref = store.put(
            namespace="integration-smoke",
            content=payload,
            content_type="application/json",
        )
        recovered = store.get(artifact_ref)
        if recovered != payload:
            raise RuntimeError("Supabase Storage round-trip returned different bytes")
        if not artifact_ref.endswith("/" + expected_hash):
            raise RuntimeError("Supabase Storage reference does not match the payload hash")

        print("DATABASE_CONNECTIVITY=PASS")
        print("DATABASE_SCHEMA=PASS")
        print("PRIVATE_STORAGE_UPLOAD=PASS")
        print("PRIVATE_STORAGE_DOWNLOAD=PASS")
        print("ARTIFACT_SHA256=" + expected_hash)
        print("DATABASE_NAME=" + str(database_name))
        return 0
    except Exception as exc:
        # Emit a safe exception category only; never print URLs, headers or secrets.
        print("SUPABASE_LIVE_CHECK=FAIL")
        print("ERROR_TYPE=" + type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
