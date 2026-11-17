"""PostgreSQL persistence and leased task queue for the YJ64 cycle."""

from __future__ import annotations

import json
from typing import Callable


class PostgresCycleStore:
    """Persist CI events and operate an idempotent PostgreSQL task queue.

    The schema is managed by the checked-in SQL migration. This class never
    creates tables implicitly and never executes repository code.
    """

    def __init__(self, database_url: str, connect_factory: Callable | None = None):
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("database_url is required")
        self.database_url = database_url
        self._connect_factory = connect_factory

    def _connect(self):
        if self._connect_factory is not None:
            return self._connect_factory(self.database_url)
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is not installed") from exc
        # Supabase transaction-pooler connections must not rely on session-scoped
        # prepared statements. Disable psycopg auto-prepare for pooler compatibility.
        return psycopg.connect(self.database_url, prepare_threshold=None)

    def record_ci_event(self, event: dict) -> dict:
        required = (
            "repository", "run_id", "run_attempt", "workflow", "conclusion",
            "commit_sha", "branch", "run_url",
        )
        if any(key not in event for key in required):
            raise ValueError("CI event is missing required fields")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO yj64_ci_events
                        (repository, run_id, run_attempt, workflow, conclusion,
                         commit_sha, branch, run_url, payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (repository, run_id, run_attempt) DO NOTHING
                    RETURNING event_id
                    """,
                    (
                        event["repository"], event["run_id"], event["run_attempt"],
                        event["workflow"], event["conclusion"], event["commit_sha"],
                        event["branch"], event["run_url"],
                        json.dumps(event, separators=(",", ":")),
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    return {
                        "accepted": True,
                        "duplicate": True,
                        "event_id": None,
                        "task_enqueued": False,
                    }

                event_id = inserted[0]
                dedupe_key = (
                    f"ci-event:{event['repository']}:{event['run_id']}:"
                    f"{event['run_attempt']}"
                )
                cursor.execute(
                    """
                    INSERT INTO yj64_task_queue (task_type, payload, dedupe_key)
                    VALUES ('process_ci_event', %s::jsonb, %s)
                    ON CONFLICT (dedupe_key) DO NOTHING
                    """,
                    (json.dumps({"event_id": event_id}), dedupe_key),
                )
                return {
                    "accepted": True,
                    "duplicate": False,
                    "event_id": event_id,
                    "task_enqueued": True,
                }

    def claim_next_task(self, worker_id: str, lease_seconds: int = 300) -> dict | None:
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(lease_seconds, int) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                # A request that may have reached the provider is not safe to replay
                # merely because the worker lease expired. Quarantine it first.
                cursor.execute(
                    """
                    UPDATE yj64_provider_request_reservations AS reservation
                    SET state = 'unknown',
                        last_error_classification = COALESCE(
                            last_error_classification, 'worker_lease_expired'
                        )
                    FROM yj64_task_queue AS task
                    WHERE reservation.queue_task_id = task.task_id
                      AND task.state = 'running'
                      AND task.locked_at < now() - (%s * interval '1 second')
                      AND reservation.state IN ('sending', 'accepted')
                    """,
                    (lease_seconds,),
                )
                cursor.execute(
                    """
                    UPDATE yj64_task_queue AS task
                    SET state = 'blocked', blocked_reason = 'request_outcome_unknown',
                        lock_owner = NULL, locked_at = NULL,
                        last_error = 'Worker lease expired after provider send; reconcile before retry',
                        updated_at = now()
                    WHERE task.state = 'running'
                      AND task.locked_at < now() - (%s * interval '1 second')
                      AND EXISTS (
                          SELECT 1 FROM yj64_provider_request_reservations AS reservation
                          WHERE reservation.queue_task_id = task.task_id
                            AND reservation.state = 'unknown'
                      )
                    """,
                    (lease_seconds,),
                )
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET state = 'failed',
                        lock_owner = NULL,
                        locked_at = NULL,
                        last_error = COALESCE(last_error, 'Worker lease expired after final attempt'),
                        updated_at = now()
                    WHERE state = 'running'
                      AND attempts >= max_attempts
                      AND locked_at < now() - (%s * interval '1 second')
                    """,
                    (lease_seconds,),
                )
                cursor.execute(
                    """
                    WITH candidate AS (
                        SELECT task_id
                        FROM yj64_task_queue
                        WHERE attempts < max_attempts
                          AND (
                              (state = 'pending' AND available_at <= now())
                              OR
                              (state = 'running' AND locked_at < now() - (%s * interval '1 second'))
                          )
                        ORDER BY available_at, task_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE yj64_task_queue AS task
                    SET state = 'running',
                        attempts = task.attempts + 1,
                        locked_at = now(),
                        lock_owner = %s,
                        updated_at = now()
                    FROM candidate
                    WHERE task.task_id = candidate.task_id
                    RETURNING task.task_id, task.task_type, task.payload,
                              task.attempts, task.max_attempts,
                              (SELECT checkpoint FROM yj64_task_checkpoints
                               WHERE queue_task_id = task.task_id
                               ORDER BY sequence DESC LIMIT 1)
                    """,
                    (lease_seconds, worker_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                checkpoint = row[5]
                if isinstance(checkpoint, str):
                    checkpoint = json.loads(checkpoint)
                if checkpoint is not None:
                    from .checkpoints import verify_checkpoint
                    verify_checkpoint(checkpoint)
                return {
                    "task_id": row[0],
                    "task_type": row[1],
                    "payload": row[2],
                    "attempts": row[3],
                    "max_attempts": row[4],
                    "worker_id": worker_id,
                    "checkpoint": checkpoint,
                }

    def renew_task_lease(
        self, task_id: int, worker_id: str, lease_seconds: int = 300,
    ) -> bool:
        """Renew a lease only while it is still owned and has not already expired."""
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET locked_at = now(), updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    """,
                    (task_id, worker_id, lease_seconds),
                )
                return cursor.rowcount == 1

    def claim_next_reconciliation_task(
        self, worker_id: str, lease_seconds: int = 300,
    ) -> dict | None:
        """Lease a blocked task only for checking ambiguous provider delivery."""
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH candidate AS (
                        SELECT task.task_id
                        FROM yj64_task_queue AS task
                        WHERE task.state = 'blocked'
                          AND task.blocked_reason = 'request_outcome_unknown'
                          AND EXISTS (
                              SELECT 1 FROM yj64_provider_request_reservations AS reservation
                              WHERE reservation.queue_task_id = task.task_id
                                AND reservation.state = 'unknown'
                          )
                        ORDER BY task.updated_at, task.task_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE yj64_task_queue AS task
                    SET state = 'running', locked_at = now(), lock_owner = %s,
                        updated_at = now()
                    FROM candidate
                    WHERE task.task_id = candidate.task_id
                    RETURNING task.task_id, task.task_type, task.payload,
                              task.attempts, task.max_attempts,
                              (SELECT checkpoint FROM yj64_task_checkpoints
                               WHERE queue_task_id = task.task_id
                               ORDER BY sequence DESC LIMIT 1)
                    """,
                    (worker_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                checkpoint = row[5]
                if isinstance(checkpoint, str):
                    checkpoint = json.loads(checkpoint)
                if checkpoint is not None:
                    from .checkpoints import verify_checkpoint
                    verify_checkpoint(checkpoint)
                return {
                    "task_id": row[0], "task_type": row[1], "payload": row[2],
                    "attempts": row[3], "max_attempts": row[4],
                    "worker_id": worker_id, "checkpoint": checkpoint,
                    "reconciliation_only": True,
                }

    def list_unknown_provider_requests(
        self, queue_task_id: int, worker_id: str, lease_seconds: int = 300,
    ) -> list[dict]:
        """Return safe request metadata for provider-side lookup; never return prompts or keys."""
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    """,
                    (queue_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("reconciliation requires the current task lease")
                cursor.execute(
                    """
                    SELECT reservation_id, idempotency_key, provider, model, endpoint,
                           request_payload_sha256, provider_request_id, sent_at,
                           input_tokens_estimated, output_tokens_estimated,
                           last_error_classification
                    FROM yj64_provider_request_reservations
                    WHERE queue_task_id = %s AND state = 'unknown'
                    ORDER BY sent_at, reservation_id
                    """,
                    (queue_task_id,),
                )
                columns = (
                    "reservation_id", "idempotency_key", "provider", "model",
                    "endpoint", "payload_sha256", "provider_request_id", "sent_at",
                    "input_tokens_estimated", "output_tokens_estimated",
                    "last_error_classification",
                )
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def list_recovered_provider_results(
        self, queue_task_id: int, worker_id: str, lease_seconds: int = 300,
    ) -> list[dict]:
        """Expose only artifact references for provider results recovered during reconciliation."""
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    """,
                    (queue_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("result lookup requires the current task lease")
                cursor.execute(
                    """
                    SELECT reservation_id, provider, model, request_payload_sha256,
                           provider_request_id, provider_result_ref, resolution_evidence_ref
                    FROM yj64_provider_request_reservations
                    WHERE queue_task_id = %s AND state = 'completed'
                      AND resolution_kind = 'provider_found'
                      AND provider_result_ref IS NOT NULL
                    ORDER BY created_at, reservation_id
                    """,
                    (queue_task_id,),
                )
                columns = (
                    "reservation_id", "provider", "model", "payload_sha256",
                    "provider_request_id", "provider_result_ref", "evidence_ref",
                )
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def resolve_unknown_provider_request(
        self, queue_task_id: int, worker_id: str, reservation_id: str,
        *, outcome: str, evidence_ref: str, provider_result_ref: str | None = None,
        input_tokens_actual: int | None = None, output_tokens_actual: int | None = None,
        actual_cost_usd=None, provider_request_id: str | None = None,
        lease_seconds: int = 300,
    ) -> dict:
        """Resolve an ambiguous send only with explicit provider/human evidence."""
        from decimal import Decimal, InvalidOperation

        if outcome not in {"provider_found", "provider_not_found"}:
            raise ValueError("outcome must be provider_found or provider_not_found")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip() or len(evidence_ref) > 1024:
            raise ValueError("evidence_ref is required and must be at most 1024 characters")
        if "?" in evidence_ref or "#" in evidence_ref:
            raise ValueError("evidence_ref must be an opaque reference, not a signed URL")
        if outcome == "provider_found" and (
            not isinstance(provider_result_ref, str) or not provider_result_ref.strip()
            or len(provider_result_ref) > 1024
        ):
            raise ValueError("provider_found requires a durable provider_result_ref")
        if provider_result_ref is not None and (
            "?" in provider_result_ref or "#" in provider_result_ref
        ):
            raise ValueError("provider_result_ref must be an opaque artifact reference, not a signed URL")
        if outcome == "provider_not_found" and provider_result_ref is not None:
            raise ValueError("provider_not_found cannot have a provider_result_ref")
        for name, value in (
            ("input_tokens_actual", input_tokens_actual),
            ("output_tokens_actual", output_tokens_actual),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        cost = None
        if actual_cost_usd is not None:
            try:
                cost = Decimal(str(actual_cost_usd))
            except (InvalidOperation, ValueError):
                raise ValueError("actual_cost_usd must be a non-negative decimal")
            if not cost.is_finite() or cost < 0:
                raise ValueError("actual_cost_usd must be a non-negative decimal")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (queue_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("request reconciliation requires the current task lease")
                cursor.execute(
                    """
                    SELECT input_tokens_estimated, output_tokens_estimated,
                           estimated_cost_usd, cost_estimate_known, state
                    FROM yj64_provider_request_reservations
                    WHERE reservation_id = %s AND queue_task_id = %s
                    FOR UPDATE
                    """,
                    (reservation_id, queue_task_id),
                )
                reservation = cursor.fetchone()
                if reservation is None:
                    raise KeyError("provider reservation does not exist")
                if reservation[4] != "unknown":
                    raise RuntimeError("only unknown provider requests can be reconciled")
                if outcome == "provider_not_found":
                    actual_input = 0
                    actual_output = 0
                    final_cost = Decimal("0")
                    final_state = "failed"
                else:
                    actual_input = reservation[0] if input_tokens_actual is None else input_tokens_actual
                    actual_output = reservation[1] if output_tokens_actual is None else output_tokens_actual
                    final_cost = (
                        (reservation[2] if reservation[3] else None)
                        if cost is None else cost
                    )
                    final_state = "completed"
                cursor.execute(
                    """
                    UPDATE yj64_provider_request_reservations
                    SET state = %s, input_tokens_actual = %s,
                        output_tokens_actual = %s, actual_cost_usd = %s,
                        provider_request_id = COALESCE(%s, provider_request_id),
                        resolution_kind = %s, resolution_evidence_ref = %s,
                        provider_result_ref = %s, resolved_at = now(),
                        finished_at = now(), expires_at = NULL
                    WHERE reservation_id = %s
                    """,
                    (
                        final_state, actual_input, actual_output, final_cost,
                        provider_request_id, outcome, evidence_ref,
                        provider_result_ref, reservation_id,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET reserved_input_tokens = GREATEST(0, reserved_input_tokens - %s),
                        reserved_output_tokens = GREATEST(0, reserved_output_tokens - %s),
                        reserved_cost_usd = GREATEST(0, reserved_cost_usd - %s),
                        consumed_input_tokens = consumed_input_tokens + %s,
                        consumed_output_tokens = consumed_output_tokens + %s,
                        consumed_cost_usd = consumed_cost_usd + %s,
                        updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                    """,
                    (
                        reservation[0], reservation[1], reservation[2],
                        actual_input, actual_output, final_cost or 0,
                        queue_task_id, worker_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("task lease was lost while resolving provider usage")
                cursor.execute(
                    """
                    SELECT count(*) FROM yj64_provider_request_reservations
                    WHERE queue_task_id = %s AND state = 'unknown'
                    """,
                    (queue_task_id,),
                )
                remaining_unknown = cursor.fetchone()[0]
                if remaining_unknown == 0:
                    cursor.execute(
                        """
                        UPDATE yj64_task_queue
                        SET state = 'pending', available_at = now(),
                            blocked_reason = NULL, locked_at = NULL, lock_owner = NULL,
                            last_error = 'Ambiguous provider delivery reconciled; resume from durable result/evidence',
                            updated_at = now()
                        WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                        """,
                        (queue_task_id, worker_id),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError("task lease was lost while resuming reconciled task")
                return {
                    "reservation_state": final_state,
                    "remaining_unknown_requests": remaining_unknown,
                    "task_resumed": remaining_unknown == 0,
                    "provider_result_ref": provider_result_ref,
                }

    def complete_task(self, task_id: int, worker_id: str) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET state = 'completed', locked_at = NULL, lock_owner = NULL,
                        updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM yj64_provider_request_reservations AS reservation
                          WHERE reservation.queue_task_id = yj64_task_queue.task_id
                            AND reservation.state IN ('reserved', 'sending', 'accepted', 'unknown')
                      )
                    """,
                    (task_id, worker_id),
                )
                return cursor.rowcount == 1

    def fail_task(
        self, task_id: int, worker_id: str, error: str, retry_delay_seconds: int = 60
    ) -> str | None:
        if not isinstance(retry_delay_seconds, int) or not 0 <= retry_delay_seconds <= 86400:
            raise ValueError("retry_delay_seconds must be between 0 and 86400")
        safe_error = str(error)[:2000]
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET state = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'pending' END,
                        available_at = CASE
                            WHEN attempts >= max_attempts THEN available_at
                            ELSE now() + (%s * interval '1 second')
                        END,
                        locked_at = NULL, lock_owner = NULL, last_error = %s,
                        updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                    RETURNING state
                    """,
                    (retry_delay_seconds, safe_error, task_id, worker_id),
                )
                row = cursor.fetchone()
                return row[0] if row else None

    def block_task(self, task_id: int, worker_id: str, reason: str) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET state = 'blocked', locked_at = NULL, lock_owner = NULL,
                        last_error = %s, updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                    """,
                    (str(reason)[:2000], task_id, worker_id),
                )
                return cursor.rowcount == 1

    def save_checkpoint(
        self, queue_task_id: int, worker_id: str, checkpoint: dict,
        lease_seconds: int = 300,
    ) -> bool:
        """Persist a verified, sequential checkpoint only under a live task lease."""
        from .checkpoints import verify_checkpoint

        if not isinstance(queue_task_id, int) or isinstance(queue_task_id, bool) or queue_task_id < 1:
            raise ValueError("queue_task_id must be a positive integer")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        verify_checkpoint(checkpoint)
        if not isinstance(checkpoint, dict):
            raise ValueError("checkpoint must be an object")
        payload = json.dumps(checkpoint, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running'
                      AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (queue_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot checkpoint without a live task lease")
                cursor.execute(
                    """
                    SELECT checkpoint_hash FROM yj64_task_checkpoints
                    WHERE queue_task_id = %s AND sequence = %s
                    """,
                    (queue_task_id, checkpoint["sequence"]),
                )
                existing_sequence = cursor.fetchone()
                if existing_sequence is not None:
                    if existing_sequence[0].strip() == checkpoint["checkpoint_hash"]:
                        return False
                    raise ValueError("checkpoint sequence already exists with different content")
                cursor.execute(
                    """
                    SELECT sequence, checkpoint_hash FROM yj64_task_checkpoints
                    WHERE queue_task_id = %s
                    ORDER BY sequence DESC LIMIT 1
                    FOR UPDATE
                    """,
                    (queue_task_id,),
                )
                latest = cursor.fetchone()
                if latest is None:
                    expected_sequence, expected_previous_hash = 1, None
                else:
                    expected_sequence = latest[0] + 1
                    expected_previous_hash = latest[1].strip()
                if checkpoint["sequence"] != expected_sequence:
                    raise ValueError("checkpoint sequence must immediately follow the latest checkpoint")
                if checkpoint["previous_checkpoint_hash"] != expected_previous_hash:
                    raise ValueError("checkpoint previous hash does not match the latest checkpoint")
                cursor.execute(
                    """
                    INSERT INTO yj64_task_checkpoints
                        (queue_task_id, sequence, schema_version, checkpoint_hash,
                         previous_checkpoint_hash, checkpoint)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING checkpoint_id
                    """,
                    (
                        queue_task_id, checkpoint["sequence"], checkpoint["schema_version"],
                        checkpoint["checkpoint_hash"], checkpoint["previous_checkpoint_hash"],
                        payload,
                    ),
                )
                return cursor.fetchone() is not None

    def load_latest_checkpoint(self, queue_task_id: int) -> dict | None:
        """Load and integrity-check the newest checkpoint for a queue task."""
        from .checkpoints import verify_checkpoint

        if not isinstance(queue_task_id, int) or isinstance(queue_task_id, bool) or queue_task_id < 1:
            raise ValueError("queue_task_id must be a positive integer")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT checkpoint FROM yj64_task_checkpoints
                    WHERE queue_task_id = %s
                    ORDER BY sequence DESC
                    LIMIT 1
                    """,
                    (queue_task_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                checkpoint = row[0]
                if isinstance(checkpoint, str):
                    checkpoint = json.loads(checkpoint)
                verify_checkpoint(checkpoint)
                return checkpoint


    def defer_task_for_capacity(
        self, task_id: int, worker_id: str, retry_at,
        reason: str, lease_seconds: int = 300,
    ) -> bool:
        """Release a task lease and durably schedule a later capacity recheck."""
        from datetime import datetime

        if not isinstance(retry_at, datetime) or retry_at.tzinfo is None:
            raise ValueError("retry_at must be a timezone-aware datetime")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason is required")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET state = CASE
                            WHEN capacity_deferrals + 1 >= max_capacity_deferrals THEN 'blocked'
                            ELSE 'pending'
                        END,
                        available_at = GREATEST(%s, now()),
                        attempts = GREATEST(0, attempts - 1),
                        capacity_deferrals = capacity_deferrals + 1,
                        blocked_reason = CASE
                            WHEN capacity_deferrals + 1 >= max_capacity_deferrals
                            THEN 'capacity_deferral_budget_exhausted'
                            ELSE NULL
                        END,
                        locked_at = NULL, lock_owner = NULL,
                        last_error = %s, updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                      AND capacity_deferrals < max_capacity_deferrals
                    """,
                    (retry_at, reason[:1000], task_id, worker_id, lease_seconds),
                )
                return cursor.rowcount == 1

    def run_recovery_maintenance(self, limit: int = 100) -> dict:
        """Run bounded durable recovery work; safe to invoke repeatedly."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        quota_tasks = self.recover_due_quota_tasks(limit=limit)
        expired_reservations = self.expire_unsent_provider_reservations(limit=limit)
        return {
            "quota_tasks_requeued": quota_tasks,
            "unsent_reservations_expired": expired_reservations,
        }

    def recover_due_quota_tasks(self, limit: int = 100) -> list[int]:
        """Requeue only quota-blocked tasks whose known reset time has arrived.

        Tasks without a reset timestamp remain blocked. Other blocked reasons
        are never touched. Exhausted task retry budgets become terminal failures.
        """
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET state = 'failed', blocked_reason = 'retry_budget_exhausted',
                        last_error = COALESCE(last_error, 'Quota reset reached after final attempt'),
                        updated_at = now()
                    WHERE state = 'blocked'
                      AND blocked_reason = 'quota_exhausted'
                      AND quota_reset_at IS NOT NULL
                      AND quota_reset_at <= now()
                      AND attempts >= max_attempts
                    """
                )
                cursor.execute(
                    """
                    WITH due AS (
                        SELECT task_id
                        FROM yj64_task_queue
                        WHERE state = 'blocked'
                          AND blocked_reason = 'quota_exhausted'
                          AND quota_reset_at IS NOT NULL
                          AND quota_reset_at <= now()
                          AND attempts < max_attempts
                        ORDER BY quota_reset_at, task_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                    )
                    UPDATE yj64_task_queue AS task
                    SET state = 'pending', available_at = now(),
                        blocked_reason = NULL, quota_reset_at = NULL,
                        locked_at = NULL, lock_owner = NULL, updated_at = now()
                    FROM due
                    WHERE task.task_id = due.task_id
                    RETURNING task.task_id
                    """,
                    (limit,),
                )
                return [row[0] for row in cursor.fetchall()]

    def save_payload_manifest(
        self, queue_task_id: int, worker_id: str, manifest: dict, chunks: list[dict],
        lease_seconds: int = 300,
    ) -> dict:
        """Persist a complete, hash-verified manifest and its immutable chunks."""
        from .payload_chunks import assemble_payload

        if not isinstance(queue_task_id, int) or isinstance(queue_task_id, bool) or queue_task_id < 1:
            raise ValueError("queue_task_id must be a positive integer")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        if not isinstance(manifest, dict) or not isinstance(chunks, list):
            raise ValueError("manifest and chunks are required")
        payload_id = manifest.get("payload_id")
        if not isinstance(payload_id, str) or not payload_id.strip():
            raise ValueError("manifest payload_id is required")
        chunk_map = {item.get("chunk_id"): item.get("content") for item in chunks if isinstance(item, dict)}
        if len(chunk_map) != len(chunks):
            raise ValueError("chunks contain invalid or duplicate chunk IDs")
        assemble_payload(manifest, chunk_map)
        manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False)

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running'
                      AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (queue_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot persist payload without a live task lease")
                cursor.execute(
                    """
                    INSERT INTO yj64_payload_manifests
                        (payload_id, queue_task_id, protocol_version, total_chunks,
                         total_sha256, manifest, state)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, 'receiving')
                    ON CONFLICT (payload_id) DO NOTHING
                    RETURNING payload_id
                    """,
                    (
                        payload_id, queue_task_id, manifest["protocol_version"],
                        manifest["total_chunks"], manifest["total_sha256"], manifest_json,
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    cursor.execute(
                        """
                        SELECT queue_task_id, total_sha256, manifest
                        FROM yj64_payload_manifests
                        WHERE payload_id = %s
                        FOR UPDATE
                        """,
                        (payload_id,),
                    )
                    existing = cursor.fetchone()
                    existing_manifest = existing[2] if existing else None
                    if isinstance(existing_manifest, str):
                        existing_manifest = json.loads(existing_manifest)
                    if (
                        existing is None or existing[0] != queue_task_id
                        or str(existing[1]).strip() != manifest["total_sha256"]
                        or existing_manifest != manifest
                    ):
                        raise ValueError("payload_id already exists with conflicting manifest")

                for chunk in chunks:
                    cursor.execute(
                        """
                        INSERT INTO yj64_payload_chunks
                            (payload_id, chunk_id, chunk_index, chunk_sha256,
                             content, estimated_tokens, character_count)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            payload_id, chunk["chunk_id"], chunk["chunk_index"],
                            chunk["chunk_sha256"], chunk["content"],
                            chunk["estimated_tokens"], len(chunk["content"]),
                        ),
                    )
                    cursor.execute(
                        """
                        SELECT chunk_index, chunk_sha256, content
                        FROM yj64_payload_chunks
                        WHERE payload_id = %s AND chunk_id = %s
                        """,
                        (payload_id, chunk["chunk_id"]),
                    )
                    stored = cursor.fetchone()
                    if (
                        stored is None or stored[0] != chunk["chunk_index"]
                        or str(stored[1]).strip() != chunk["chunk_sha256"]
                        or stored[2] != chunk["content"]
                    ):
                        raise ValueError("stored chunk conflicts with immutable payload content")

                return {
                    "persisted": True,
                    "payload_id": payload_id,
                    "total_chunks": manifest["total_chunks"],
                    "duplicate_manifest": inserted is None,
                }

    def acknowledge_payload_chunk(self, payload_id: str, acknowledgement: dict) -> dict:
        """Persist an idempotent acknowledgement only when it matches stored content."""
        from .payload_chunks import validate_chunk_ack

        if not isinstance(payload_id, str) or not payload_id.strip():
            raise ValueError("payload_id is required")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT manifest FROM yj64_payload_manifests WHERE payload_id = %s FOR UPDATE",
                    (payload_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise KeyError("payload manifest does not exist")
                manifest = row[0]
                if isinstance(manifest, str):
                    manifest = json.loads(manifest)
                ack = validate_chunk_ack(manifest, acknowledgement)
                cursor.execute(
                    """
                    SELECT chunk_sha256 FROM yj64_payload_chunks
                    WHERE payload_id = %s AND chunk_id = %s
                    """,
                    (payload_id, ack["chunk_id"]),
                )
                stored = cursor.fetchone()
                if stored is None or str(stored[0]).strip() != ack["chunk_sha256"]:
                    raise ValueError("acknowledged chunk is not present in durable storage")
                cursor.execute(
                    """
                    INSERT INTO yj64_payload_chunk_acks
                        (payload_id, chunk_id, acknowledged_sha256)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (payload_id, chunk_id) DO NOTHING
                    RETURNING chunk_id
                    """,
                    (payload_id, ack["chunk_id"], ack["chunk_sha256"]),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    cursor.execute(
                        """
                        SELECT acknowledged_sha256 FROM yj64_payload_chunk_acks
                        WHERE payload_id = %s AND chunk_id = %s
                        """,
                        (payload_id, ack["chunk_id"]),
                    )
                    previous = cursor.fetchone()
                    if previous is None or str(previous[0]).strip() != ack["chunk_sha256"]:
                        raise ValueError("duplicate acknowledgement conflicts with stored hash")
                return {**ack, "duplicate": inserted is None}

    def assemble_payload_for_model(
        self, queue_task_id: int, worker_id: str, payload_id: str,
        *, require_acknowledgements: bool = False, lease_seconds: int = 300,
    ) -> dict:
        """Reassemble from durable storage and mark ready only after full hash verification.

        Stateless model endpoints use require_acknowledgements=False: the
        orchestrator assembles the complete payload locally before one request.
        Continuity-capable chunk transports can require every remote ACK first.
        """
        from .payload_chunks import assemble_payload

        if not isinstance(queue_task_id, int) or isinstance(queue_task_id, bool) or queue_task_id < 1:
            raise ValueError("queue_task_id must be a positive integer")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(payload_id, str) or not payload_id.strip():
            raise ValueError("payload_id is required")
        if not isinstance(require_acknowledgements, bool):
            raise ValueError("require_acknowledgements must be boolean")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running'
                      AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (queue_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot finalize payload without a live task lease")
                cursor.execute(
                    """
                    SELECT manifest FROM yj64_payload_manifests
                    WHERE payload_id = %s AND queue_task_id = %s
                    FOR UPDATE
                    """,
                    (payload_id, queue_task_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise KeyError("payload manifest does not exist for this task")
                manifest = row[0]
                if isinstance(manifest, str):
                    manifest = json.loads(manifest)
                cursor.execute(
                    """
                    SELECT chunk_id, content FROM yj64_payload_chunks
                    WHERE payload_id = %s ORDER BY chunk_index
                    """,
                    (payload_id,),
                )
                chunks_by_id = {chunk_id: chunk_content for chunk_id, chunk_content in cursor.fetchall()}
                if require_acknowledgements:
                    cursor.execute(
                        "SELECT chunk_id FROM yj64_payload_chunk_acks WHERE payload_id = %s",
                        (payload_id,),
                    )
                    acknowledged = {item[0] for item in cursor.fetchall()}
                    expected = {item["chunk_id"] for item in manifest["chunks"]}
                    if acknowledged != expected:
                        raise RuntimeError("cannot FINALIZE before every chunk is acknowledged")
                assembled = assemble_payload(manifest, chunks_by_id)
                cursor.execute(
                    """
                    UPDATE yj64_payload_manifests
                    SET state = 'ready_for_model', updated_at = now()
                    WHERE payload_id = %s AND queue_task_id = %s
                    """,
                    (payload_id, queue_task_id),
                )
                return {
                    "ready_for_model": True,
                    "payload_id": payload_id,
                    "total_sha256": manifest["total_sha256"],
                    "content": assembled,
                }

    def set_task_usage_budget(
        self, task_id: int, *, input_token_limit: int | None = None,
        output_token_limit: int | None = None, cost_limit_usd=None,
        max_provider_requests: int | None = None, deadline_at=None,
    ) -> bool:
        """Configure task budgets before the first attempt or any reservation."""
        from decimal import Decimal, InvalidOperation

        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id < 1:
            raise ValueError("task_id must be a positive integer")
        for name, value in (
            ("input_token_limit", input_token_limit),
            ("output_token_limit", output_token_limit),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if max_provider_requests is not None and (
            not isinstance(max_provider_requests, int) or isinstance(max_provider_requests, bool)
            or max_provider_requests < 0
        ):
            raise ValueError("max_provider_requests must be a non-negative integer or None")
        if deadline_at is not None and (
            not hasattr(deadline_at, "tzinfo") or deadline_at.tzinfo is None
        ):
            raise ValueError("deadline_at must be timezone-aware")
        cost = None
        if cost_limit_usd is not None:
            try:
                cost = Decimal(str(cost_limit_usd))
            except (InvalidOperation, ValueError):
                raise ValueError("cost_limit_usd must be a non-negative decimal or None")
            if not cost.is_finite() or cost < 0:
                raise ValueError("cost_limit_usd must be a non-negative decimal or None")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET budget_input_tokens = %s, budget_output_tokens = %s,
                        budget_cost_usd = %s, max_provider_requests = %s,
                        deadline_at = %s, updated_at = now()
                    WHERE task_id = %s AND state = 'pending' AND attempts = 0
                      AND reserved_input_tokens = 0 AND reserved_output_tokens = 0
                      AND reserved_cost_usd = 0 AND consumed_input_tokens = 0
                      AND consumed_output_tokens = 0 AND consumed_cost_usd = 0
                    """,
                    (input_token_limit, output_token_limit, cost, max_provider_requests, deadline_at, task_id),
                )
                return cursor.rowcount == 1

    def get_task_usage(self, task_id: int) -> dict | None:
        """Read configured, reserved and consumed task budgets without exposing prompts."""
        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id < 1:
            raise ValueError("task_id must be a positive integer")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT budget_input_tokens, budget_output_tokens, budget_cost_usd,
                           reserved_input_tokens, reserved_output_tokens, reserved_cost_usd,
                           consumed_input_tokens, consumed_output_tokens, consumed_cost_usd,
                           max_provider_requests, provider_requests_reserved,
                           provider_requests_consumed, deadline_at
                    FROM yj64_task_queue WHERE task_id = %s
                    """,
                    (task_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return {
                    "limits": {"input_tokens": row[0], "output_tokens": row[1], "cost_usd": str(row[2]) if row[2] is not None else None},
                    "reserved": {"input_tokens": row[3], "output_tokens": row[4], "cost_usd": str(row[5])},
                    "consumed": {"input_tokens": row[6], "output_tokens": row[7], "cost_usd": str(row[8])},
                    "request_budget": {
                        "max": row[9], "reserved": row[10], "consumed": row[11],
                        "deadline_at": row[12].isoformat() if row[12] is not None else None,
                    },
                }

    def get_cycle_usage(self) -> dict:
        """Report daily/monthly global usage and configured ceilings in database time."""
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT daily_token_limit, monthly_token_limit,
                           daily_cost_limit_usd, monthly_cost_limit_usd,
                           daily_request_limit, monthly_request_limit
                    FROM yj64_cycle_usage_budget WHERE budget_id = 1
                    """
                )
                limits = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN created_at >= date_trunc('day', now())
                            AND state <> 'expired'
                            THEN COALESCE(input_tokens_actual, input_tokens_estimated)
                               + COALESCE(output_tokens_actual, output_tokens_estimated)
                            ELSE 0 END), 0),
                        COALESCE(SUM(CASE WHEN created_at >= date_trunc('month', now())
                            AND state <> 'expired'
                            THEN COALESCE(input_tokens_actual, input_tokens_estimated)
                               + COALESCE(output_tokens_actual, output_tokens_estimated)
                            ELSE 0 END), 0),
                        COALESCE(SUM(CASE WHEN created_at >= date_trunc('day', now())
                            AND state <> 'expired'
                            THEN COALESCE(actual_cost_usd, estimated_cost_usd)
                            ELSE 0 END), 0),
                        COALESCE(SUM(CASE WHEN created_at >= date_trunc('month', now())
                            AND state <> 'expired'
                            THEN COALESCE(actual_cost_usd, estimated_cost_usd)
                            ELSE 0 END), 0),
                        COUNT(*) FILTER (WHERE created_at >= date_trunc('day', now())
                            AND state <> 'expired' AND actual_cost_usd IS NULL AND NOT cost_estimate_known),
                        COUNT(*) FILTER (WHERE created_at >= date_trunc('month', now())
                            AND state <> 'expired' AND actual_cost_usd IS NULL AND NOT cost_estimate_known),
                        COUNT(*) FILTER (WHERE created_at >= date_trunc('day', now())
                            AND state <> 'expired'),
                        COUNT(*) FILTER (WHERE created_at >= date_trunc('month', now())
                            AND state <> 'expired')
                    FROM yj64_provider_request_reservations
                    """
                )
                usage = cursor.fetchone()
                return {
                    "limits": None if limits is None else {
                        "daily_tokens": limits[0], "monthly_tokens": limits[1],
                        "daily_cost_usd": str(limits[2]) if limits[2] is not None else None,
                        "monthly_cost_usd": str(limits[3]) if limits[3] is not None else None,
                        "daily_requests": limits[4], "monthly_requests": limits[5],
                    },
                    "usage": {
                        "daily_tokens": usage[0], "monthly_tokens": usage[1],
                        "daily_cost_usd": str(usage[2]), "monthly_cost_usd": str(usage[3]),
                        "daily_unknown_cost_requests": usage[4],
                        "monthly_unknown_cost_requests": usage[5],
                        "cost_estimate_complete": usage[4] == 0 and usage[5] == 0,
                        "daily_requests": usage[6], "monthly_requests": usage[7],
                    },
                    "time_basis": "database_timezone",
                }

    def set_provider_limit_profile(
        self, profile, *, capacity_scope: str | None = None,
        profile_source: str = "operator_config", valid_until=None,
    ) -> None:
        """Persist a provider profile; capacity_scope shares account-wide limits across models."""
        from .provider_budget import ProviderLimitProfile

        if not isinstance(profile, ProviderLimitProfile):
            raise ValueError("profile must be a ProviderLimitProfile")
        if not any((
            profile.requests_per_minute, profile.tokens_per_minute,
            profile.max_concurrency, profile.max_input_tokens,
            profile.max_output_tokens, profile.max_payload_bytes,
        )):
            raise ValueError("at least one provider capacity limit must be known")
        if capacity_scope is None:
            capacity_scope = f"{profile.provider}:{profile.model}:{profile.endpoint}"
        if not isinstance(capacity_scope, str) or not capacity_scope.strip():
            raise ValueError("capacity_scope must be a non-empty string")
        if profile_source not in {"operator_config", "provider_api", "verified_observation"}:
            raise ValueError("unsupported profile_source")
        if profile_source != "operator_config" and valid_until is None:
            raise ValueError("provider-derived profiles require valid_until")
        if valid_until is not None and (
            not hasattr(valid_until, "tzinfo") or valid_until.tzinfo is None
        ):
            raise ValueError("valid_until must be timezone-aware")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT capacity_scope FROM yj64_provider_limit_profiles
                    WHERE provider = %s AND model = %s AND endpoint = %s
                    FOR UPDATE
                    """,
                    (profile.provider, profile.model, profile.endpoint),
                )
                existing_profile = cursor.fetchone()
                old_scope = existing_profile[0] if existing_profile else None
                for scope in sorted({capacity_scope, old_scope} - {None}):
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))", (scope,)
                    )
                if old_scope is not None and old_scope != capacity_scope:
                    cursor.execute(
                        """
                        SELECT 1 FROM yj64_provider_request_reservations
                        WHERE capacity_scope = %s
                          AND (sent_at >= now() - interval '60 seconds'
                               OR state IN ('reserved', 'sending', 'accepted', 'unknown'))
                        LIMIT 1
                        """,
                        (old_scope,),
                    )
                    if cursor.fetchone() is not None:
                        raise RuntimeError(
                            "cannot change quota scope while recent or active reservations exist"
                        )
                cursor.execute(
                    """
                    INSERT INTO yj64_provider_limit_profiles
                        (provider, model, endpoint, requests_per_minute,
                         tokens_per_minute, max_concurrency, max_input_tokens,
                         max_output_tokens, max_payload_bytes, tokens_per_minute_includes_output,
                         input_cost_per_million_usd, output_cost_per_million_usd,
                         profile_source, observed_at, valid_until, capacity_scope, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, now(), %s, %s, now())
                    ON CONFLICT (provider, model, endpoint) DO UPDATE SET
                        requests_per_minute = EXCLUDED.requests_per_minute,
                        tokens_per_minute = EXCLUDED.tokens_per_minute,
                        max_concurrency = EXCLUDED.max_concurrency,
                        max_input_tokens = EXCLUDED.max_input_tokens,
                        max_output_tokens = EXCLUDED.max_output_tokens,
                        max_payload_bytes = EXCLUDED.max_payload_bytes,
                        tokens_per_minute_includes_output = EXCLUDED.tokens_per_minute_includes_output,
                        input_cost_per_million_usd = EXCLUDED.input_cost_per_million_usd,
                        output_cost_per_million_usd = EXCLUDED.output_cost_per_million_usd,
                        profile_source = EXCLUDED.profile_source,
                        observed_at = now(), valid_until = EXCLUDED.valid_until,
                        capacity_scope = EXCLUDED.capacity_scope, updated_at = now()
                    """,
                    (
                        profile.provider, profile.model, profile.endpoint,
                        profile.requests_per_minute, profile.tokens_per_minute,
                        profile.max_concurrency, profile.max_input_tokens,
                        profile.max_output_tokens, profile.max_payload_bytes,
                        profile.tokens_per_minute_includes_output,
                        profile.input_cost_per_million_usd,
                        profile.output_cost_per_million_usd,
                        profile_source, valid_until, capacity_scope,
                    ),
                )

    def set_cycle_usage_budget(
        self, *, daily_token_limit: int | None = None,
        monthly_token_limit: int | None = None,
        daily_cost_limit_usd=None, monthly_cost_limit_usd=None,
        daily_request_limit: int | None = None,
        monthly_request_limit: int | None = None,
    ) -> None:
        """Set durable global usage ceilings; None means that dimension is uncapped."""
        from decimal import Decimal, InvalidOperation

        for name, value in (
            ("daily_token_limit", daily_token_limit),
            ("monthly_token_limit", monthly_token_limit),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        for name, value in (
            ("daily_request_limit", daily_request_limit),
            ("monthly_request_limit", monthly_request_limit),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        costs = []
        for name, value in (
            ("daily_cost_limit_usd", daily_cost_limit_usd),
            ("monthly_cost_limit_usd", monthly_cost_limit_usd),
        ):
            if value is None:
                costs.append(None)
                continue
            try:
                parsed = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise ValueError(f"{name} must be a non-negative decimal or None")
            if not parsed.is_finite() or parsed < 0:
                raise ValueError(f"{name} must be a non-negative decimal or None")
            costs.append(parsed)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO yj64_cycle_usage_budget
                        (budget_id, daily_token_limit, monthly_token_limit,
                         daily_cost_limit_usd, monthly_cost_limit_usd,
                         daily_request_limit, monthly_request_limit, updated_at)
                    VALUES (1, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (budget_id) DO UPDATE SET
                        daily_token_limit = EXCLUDED.daily_token_limit,
                        monthly_token_limit = EXCLUDED.monthly_token_limit,
                        daily_cost_limit_usd = EXCLUDED.daily_cost_limit_usd,
                        monthly_cost_limit_usd = EXCLUDED.monthly_cost_limit_usd,
                        daily_request_limit = EXCLUDED.daily_request_limit,
                        monthly_request_limit = EXCLUDED.monthly_request_limit,
                        updated_at = now()
                    """,
                    (daily_token_limit, monthly_token_limit, costs[0], costs[1],
                     daily_request_limit, monthly_request_limit),
                )

    def reserve_provider_capacity(
        self, queue_task_id: int, worker_id: str, idempotency_key: str,
        *, provider: str, model: str, endpoint: str, payload_sha256: str,
        input_tokens: int, output_tokens: int, payload_bytes: int,
        lease_seconds: int = 300, reservation_ttl_seconds: int = 300,
    ) -> dict:
        """Atomically check budgets/limits and reserve one provider request.

        The provider profile row serializes reservations for one model/endpoint;
        the singleton global budget row serializes spend/token ceilings across
        providers. No profile means fail closed. Idempotency prevents duplicate
        reservations after worker restarts.
        """
        from decimal import Decimal
        from uuid import uuid4
        from .provider_budget import ProviderLimitProfile, plan_provider_capacity

        if not isinstance(queue_task_id, int) or isinstance(queue_task_id, bool) or queue_task_id < 1:
            raise ValueError("queue_task_id must be a positive integer")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if any(not isinstance(v, str) or not v.strip() for v in (provider, model, endpoint)):
            raise ValueError("provider, model and endpoint are required")
        import re
        if not isinstance(payload_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", payload_sha256):
            raise ValueError("payload_sha256 must be a lowercase SHA-256 hex digest")
        for name, value in (
            ("input_tokens", input_tokens), ("output_tokens", output_tokens),
            ("payload_bytes", payload_bytes),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        if not isinstance(reservation_ttl_seconds, int) or isinstance(reservation_ttl_seconds, bool) or not 1 <= reservation_ttl_seconds <= 3600:
            raise ValueError("reservation_ttl_seconds must be between 1 and 3600")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT state, lock_owner, locked_at,
                           budget_input_tokens, budget_output_tokens, budget_cost_usd,
                           reserved_input_tokens, reserved_output_tokens, reserved_cost_usd,
                           consumed_input_tokens, consumed_output_tokens, consumed_cost_usd,
                           deadline_at, max_provider_requests,
                           provider_requests_reserved, provider_requests_consumed
                    FROM yj64_task_queue
                    WHERE task_id = %s
                    FOR UPDATE
                    """,
                    (queue_task_id,),
                )
                task = cursor.fetchone()
                if task is None or task[0] != "running" or task[1] != worker_id:
                    raise RuntimeError("provider capacity requires the current task lease")
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    ("idempotency:" + idempotency_key,),
                )
                cursor.execute(
                    """
                    SELECT reservation_id, state, queue_task_id, provider, model, endpoint,
                           request_payload_sha256
                    FROM yj64_provider_request_reservations
                    WHERE idempotency_key = %s
                    """,
                    (idempotency_key,),
                )
                previous = cursor.fetchone()
                if previous is not None:
                    if previous[2:6] != (queue_task_id, provider, model, endpoint):
                        raise ValueError("idempotency_key is already bound to a different task or provider request")
                    if str(previous[6]).strip() != payload_sha256:
                        raise ValueError("idempotency_key cannot be reused with different request content")
                    return {
                        "reserved": previous[1] == "reserved",
                        "duplicate": True,
                        "reservation_id": previous[0],
                        "state": previous[1],
                    }

                cursor.execute(
                    """
                    SELECT requests_per_minute, tokens_per_minute, max_concurrency,
                           max_input_tokens, max_output_tokens, max_payload_bytes,
                           tokens_per_minute_includes_output,
                           input_cost_per_million_usd, output_cost_per_million_usd,
                           capacity_scope, profile_source, valid_until
                    FROM yj64_provider_limit_profiles
                    WHERE provider = %s AND model = %s AND endpoint = %s
                    FOR UPDATE
                    """,
                    (provider, model, endpoint),
                )
                limits = cursor.fetchone()
                if limits is None:
                    return {
                        "reserved": False, "duplicate": False,
                        "action": "hold_for_review",
                        "reason": "No verified provider limit profile is configured",
                    }
                profile = ProviderLimitProfile(
                    provider, model, endpoint,
                    requests_per_minute=limits[0], tokens_per_minute=limits[1],
                    max_concurrency=limits[2], max_input_tokens=limits[3],
                    max_output_tokens=limits[4], max_payload_bytes=limits[5],
                    tokens_per_minute_includes_output=limits[6],
                    input_cost_per_million_usd=float(limits[7]) if limits[7] is not None else None,
                    output_cost_per_million_usd=float(limits[8]) if limits[8] is not None else None,
                )
                capacity_scope, profile_source, valid_until = limits[9], limits[10], limits[11]
                cursor.execute("SELECT now()")
                database_now = cursor.fetchone()[0]
                if profile_source != "operator_config" and (
                    valid_until is None or valid_until <= database_now
                ):
                    return {
                        "reserved": False, "duplicate": False,
                        "action": "hold_for_review",
                        "reason": "Provider limit profile is stale; refresh it before sending",
                    }
                if task[12] is not None and task[12] <= database_now:
                    return {
                        "reserved": False, "duplicate": False,
                        "action": "task_deadline_exceeded",
                        "reason": "Task deadline has elapsed; no further provider requests are allowed",
                    }
                if task[13] is not None and task[14] + task[15] >= task[13]:
                    return {
                        "reserved": False, "duplicate": False,
                        "action": "task_budget_exhausted",
                        "reason": "Task provider-request budget is exhausted",
                    }
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (capacity_scope,))
                cursor.execute(
                    """
                    SELECT created_at, input_tokens_estimated, output_tokens_estimated,
                           state, expires_at, sent_at
                    FROM yj64_provider_request_reservations
                    WHERE capacity_scope = %s
                      AND (
                          sent_at >= %s - interval '60 seconds'
                          OR state IN ('reserved', 'sending', 'accepted', 'unknown')
                      )
                    """,
                    (capacity_scope, database_now),
                )
                reservations = []
                for row in cursor.fetchall():
                    token_count = row[1] + (row[2] if profile.tokens_per_minute_includes_output else 0)
                    reservations.append({
                        "created_at": row[0], "estimated_tokens": token_count,
                        "state": row[3], "expires_at": row[4], "sent_at": row[5],
                    })
                capacity = plan_provider_capacity(
                    profile, input_tokens=input_tokens, output_tokens=output_tokens,
                    payload_bytes=payload_bytes, reservations=reservations, now=database_now,
                )
                if not capacity.allowed:
                    return {
                        "reserved": False, "duplicate": False,
                        "action": capacity.action, "retry_at": capacity.retry_at,
                        "reason": capacity.reason,
                    }

                if profile.input_cost_per_million_usd is None or profile.output_cost_per_million_usd is None:
                    estimated_cost = None
                else:
                    estimated_cost = (
                        Decimal(input_tokens) * Decimal(str(profile.input_cost_per_million_usd))
                        + Decimal(output_tokens) * Decimal(str(profile.output_cost_per_million_usd))
                    ) / Decimal(1_000_000)

                budget_input, budget_output, budget_cost = task[3], task[4], task[5]
                reserved_input, reserved_output, reserved_cost = task[6], task[7], Decimal(str(task[8]))
                consumed_input, consumed_output, consumed_cost = task[9], task[10], Decimal(str(task[11]))
                if budget_input is not None and consumed_input + reserved_input + input_tokens > budget_input:
                    return {"reserved": False, "action": "task_budget_exhausted", "reason": "Task input-token budget would be exceeded"}
                if budget_output is not None and consumed_output + reserved_output + output_tokens > budget_output:
                    return {"reserved": False, "action": "task_budget_exhausted", "reason": "Task output-token budget would be exceeded"}
                if budget_cost is not None:
                    if estimated_cost is None:
                        return {"reserved": False, "action": "hold_for_review", "reason": "Task cost budget is set but provider pricing is unknown"}
                    if consumed_cost + reserved_cost + estimated_cost > Decimal(str(budget_cost)):
                        return {"reserved": False, "action": "task_budget_exhausted", "reason": "Task cost budget would be exceeded"}

                cursor.execute(
                    """
                    SELECT daily_token_limit, monthly_token_limit,
                           daily_cost_limit_usd, monthly_cost_limit_usd,
                           daily_request_limit, monthly_request_limit
                    FROM yj64_cycle_usage_budget WHERE budget_id = 1 FOR UPDATE
                    """
                )
                global_budget = cursor.fetchone()
                if global_budget is not None:
                    cursor.execute(
                        "SELECT date_trunc('day', now()) + interval '1 day', date_trunc('month', now()) + interval '1 month'"
                    )
                    daily_reset_at, monthly_reset_at = cursor.fetchone()
                    cursor.execute(
                        """
                        SELECT
                            COALESCE(SUM(COALESCE(input_tokens_actual, input_tokens_estimated)
                                      + COALESCE(output_tokens_actual, output_tokens_estimated)), 0),
                            COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd)), 0),
                            COUNT(*) FILTER (WHERE actual_cost_usd IS NULL AND NOT cost_estimate_known),
                            COUNT(*) FILTER (WHERE state <> 'expired')
                        FROM yj64_provider_request_reservations
                        WHERE state <> 'expired'
                          AND created_at >= date_trunc('day', now())
                        """
                    )
                    daily = cursor.fetchone()
                    cursor.execute(
                        """
                        SELECT
                            COALESCE(SUM(COALESCE(input_tokens_actual, input_tokens_estimated)
                                      + COALESCE(output_tokens_actual, output_tokens_estimated)), 0),
                            COALESCE(SUM(COALESCE(actual_cost_usd, estimated_cost_usd)), 0),
                            COUNT(*) FILTER (WHERE actual_cost_usd IS NULL AND NOT cost_estimate_known),
                            COUNT(*) FILTER (WHERE state <> 'expired')
                        FROM yj64_provider_request_reservations
                        WHERE state <> 'expired'
                          AND created_at >= date_trunc('month', now())
                        """
                    )
                    monthly = cursor.fetchone()
                    requested_tokens = input_tokens + output_tokens
                    if global_budget[4] is not None and daily[3] + 1 > global_budget[4]:
                        return {"reserved": False, "action": "schedule_retry", "retry_at": daily_reset_at, "reason": "Global daily provider-request budget reached"}
                    if global_budget[5] is not None and monthly[3] + 1 > global_budget[5]:
                        return {"reserved": False, "action": "schedule_retry", "retry_at": monthly_reset_at, "reason": "Global monthly provider-request budget reached"}
                    if global_budget[0] is not None and daily[0] + requested_tokens > global_budget[0]:
                        return {"reserved": False, "action": "schedule_retry", "retry_at": daily_reset_at, "reason": "Global daily token budget reached; retry after the database-day reset"}
                    if global_budget[1] is not None and monthly[0] + requested_tokens > global_budget[1]:
                        return {"reserved": False, "action": "schedule_retry", "retry_at": monthly_reset_at, "reason": "Global monthly token budget reached; retry after the database-month reset"}
                    if global_budget[2] is not None:
                        if daily[2] > 0:
                            return {"reserved": False, "action": "hold_for_review", "reason": "Daily usage contains requests with unknown cost; reconcile before enforcing a cost ceiling"}
                        if estimated_cost is None:
                            return {"reserved": False, "action": "hold_for_review", "reason": "Global cost budget is set but provider pricing is unknown"}
                        if Decimal(str(daily[1])) + estimated_cost > Decimal(str(global_budget[2])):
                            return {"reserved": False, "action": "schedule_retry", "retry_at": daily_reset_at, "reason": "Global daily cost budget reached; retry after the database-day reset"}
                    if global_budget[3] is not None:
                        if monthly[2] > 0:
                            return {"reserved": False, "action": "hold_for_review", "reason": "Monthly usage contains requests with unknown cost; reconcile before enforcing a cost ceiling"}
                        if estimated_cost is None:
                            return {"reserved": False, "action": "hold_for_review", "reason": "Global cost budget is set but provider pricing is unknown"}
                        if Decimal(str(monthly[1])) + estimated_cost > Decimal(str(global_budget[3])):
                            return {"reserved": False, "action": "schedule_retry", "retry_at": monthly_reset_at, "reason": "Global monthly cost budget reached; retry after the database-month reset"}

                reservation_id = str(uuid4())
                cursor.execute(
                    """
                    INSERT INTO yj64_provider_request_reservations
                        (reservation_id, idempotency_key, queue_task_id, provider, model,
                         endpoint, capacity_scope, request_payload_sha256, payload_bytes,
                         input_tokens_estimated, output_tokens_estimated,
                         estimated_cost_usd, cost_estimate_known, state, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'reserved',
                            now() + (%s * interval '1 second'))
                    """,
                    (
                        reservation_id, idempotency_key, queue_task_id, provider, model,
                        endpoint, capacity_scope, payload_sha256, payload_bytes,
                        input_tokens, output_tokens, estimated_cost or Decimal("0"),
                        estimated_cost is not None, reservation_ttl_seconds,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET reserved_input_tokens = reserved_input_tokens + %s,
                        reserved_output_tokens = reserved_output_tokens + %s,
                        reserved_cost_usd = reserved_cost_usd + %s,
                        provider_requests_reserved = provider_requests_reserved + 1,
                        updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                    """,
                    (
                        input_tokens, output_tokens, estimated_cost or Decimal("0"),
                        queue_task_id, worker_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("task lease was lost while reserving provider capacity")
                return {
                    "reserved": True, "duplicate": False,
                    "reservation_id": reservation_id,
                    "idempotency_key": idempotency_key,
                    "estimated_cost_usd": str(estimated_cost) if estimated_cost is not None else None,
                    "state": "reserved",
                }

    def mark_provider_request_sending(
        self, queue_task_id: int, worker_id: str, reservation_id: str,
        lease_seconds: int = 300,
    ) -> bool:
        """Mark the point after which a timeout may mean the provider received it."""
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (queue_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot send provider request without a live task lease")
                cursor.execute(
                    """
                    SELECT state FROM yj64_provider_request_reservations
                    WHERE reservation_id = %s AND queue_task_id = %s
                    FOR UPDATE
                    """,
                    (reservation_id, queue_task_id),
                )
                reservation = cursor.fetchone()
                if reservation is None:
                    return False
                if reservation[0] == "sending":
                    return True
                if reservation[0] != "reserved":
                    return False
                cursor.execute(
                    """
                    UPDATE yj64_provider_request_reservations
                    SET state = 'sending', sent_at = COALESCE(sent_at, now()), expires_at = NULL
                    WHERE reservation_id = %s AND queue_task_id = %s
                      AND state = 'reserved' AND (expires_at IS NULL OR expires_at > now())
                    RETURNING state
                    """,
                    (reservation_id, queue_task_id),
                )
                if cursor.fetchone() is None:
                    return False
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET provider_requests_reserved = GREATEST(0, provider_requests_reserved - 1),
                        provider_requests_consumed = provider_requests_consumed + 1,
                        updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                    """,
                    (queue_task_id, worker_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("task lease was lost while consuming provider request budget")
                return True

    def finish_provider_request(
        self, queue_task_id: int, worker_id: str, reservation_id: str,
        *, outcome: str, input_tokens_actual: int | None = None,
        output_tokens_actual: int | None = None, actual_cost_usd=None,
        provider_request_id: str | None = None, error_classification: str | None = None,
        lease_seconds: int = 300,
    ) -> dict:
        """Close a sent request or conservatively retain an ambiguous one as unknown."""
        from decimal import Decimal, InvalidOperation

        if outcome not in {"completed", "failed", "unknown"}:
            raise ValueError("outcome must be completed, failed or unknown")
        for name, value in (
            ("input_tokens_actual", input_tokens_actual),
            ("output_tokens_actual", output_tokens_actual),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")
        cost = None
        if actual_cost_usd is not None:
            try:
                cost = Decimal(str(actual_cost_usd))
            except (InvalidOperation, ValueError):
                raise ValueError("actual_cost_usd must be a non-negative decimal")
            if not cost.is_finite() or cost < 0:
                raise ValueError("actual_cost_usd must be a non-negative decimal")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (queue_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot settle provider usage without a live task lease")
                cursor.execute(
                    """
                    SELECT input_tokens_estimated, output_tokens_estimated,
                           estimated_cost_usd, cost_estimate_known, state
                    FROM yj64_provider_request_reservations
                    WHERE reservation_id = %s AND queue_task_id = %s
                    FOR UPDATE
                    """,
                    (reservation_id, queue_task_id),
                )
                reservation = cursor.fetchone()
                if reservation is None:
                    raise KeyError("provider reservation does not exist")
                if reservation[4] in {"completed", "failed", "expired"}:
                    return {"settled": True, "duplicate": True, "state": reservation[4]}
                if reservation[4] not in {"sending", "accepted", "unknown"}:
                    raise RuntimeError("provider request was not marked as sent")
                if outcome == "unknown":
                    cursor.execute(
                        """
                        UPDATE yj64_provider_request_reservations
                        SET state = 'unknown', last_error_classification = %s,
                            provider_request_id = COALESCE(%s, provider_request_id)
                        WHERE reservation_id = %s
                        """,
                        (error_classification, provider_request_id, reservation_id),
                    )
                    return {"settled": False, "duplicate": False, "state": "unknown", "requires_reconciliation": True}

                actual_input = reservation[0] if input_tokens_actual is None else input_tokens_actual
                actual_output = reservation[1] if output_tokens_actual is None else output_tokens_actual
                final_cost = (reservation[2] if reservation[3] else None) if cost is None else cost
                cursor.execute(
                    """
                    UPDATE yj64_provider_request_reservations
                    SET state = %s, input_tokens_actual = %s,
                        output_tokens_actual = %s, actual_cost_usd = %s,
                        provider_request_id = COALESCE(%s, provider_request_id),
                        last_error_classification = %s,
                        finished_at = now(), expires_at = NULL
                    WHERE reservation_id = %s
                    """,
                    (
                        outcome, actual_input, actual_output, final_cost,
                        provider_request_id, error_classification, reservation_id,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET reserved_input_tokens = GREATEST(0, reserved_input_tokens - %s),
                        reserved_output_tokens = GREATEST(0, reserved_output_tokens - %s),
                        reserved_cost_usd = GREATEST(0, reserved_cost_usd - %s),
                        consumed_input_tokens = consumed_input_tokens + %s,
                        consumed_output_tokens = consumed_output_tokens + %s,
                        consumed_cost_usd = consumed_cost_usd + %s,
                        updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                    """,
                    (
                        reservation[0], reservation[1], reservation[2],
                        actual_input, actual_output, final_cost or 0,
                        queue_task_id, worker_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("task lease was lost while settling provider usage")
                return {"settled": True, "duplicate": False, "state": outcome}

    def expire_unsent_provider_reservations(self, limit: int = 100) -> list[str]:
        """Release only reservations that expired before any network send began."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH expired AS (
                        SELECT reservation_id, queue_task_id,
                               input_tokens_estimated, output_tokens_estimated,
                               estimated_cost_usd
                        FROM yj64_provider_request_reservations
                        WHERE state = 'reserved' AND expires_at <= now()
                        ORDER BY expires_at, reservation_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                    ), released AS (
                        UPDATE yj64_provider_request_reservations AS reservation
                        SET state = 'expired', finished_at = now()
                        FROM expired
                        WHERE reservation.reservation_id = expired.reservation_id
                        RETURNING expired.reservation_id, expired.queue_task_id,
                                  expired.input_tokens_estimated, expired.output_tokens_estimated,
                                  expired.estimated_cost_usd
                    )
                    UPDATE yj64_task_queue AS task
                    SET reserved_input_tokens = GREATEST(0, task.reserved_input_tokens - released.input_tokens_estimated),
                        reserved_output_tokens = GREATEST(0, task.reserved_output_tokens - released.output_tokens_estimated),
                        reserved_cost_usd = GREATEST(0, task.reserved_cost_usd - released.estimated_cost_usd),
                        provider_requests_reserved = GREATEST(0, task.provider_requests_reserved - 1),
                        updated_at = now()
                    FROM released
                    WHERE task.task_id = released.queue_task_id
                    RETURNING released.reservation_id
                    """,
                    (limit,),
                )
                return [row[0] for row in cursor.fetchall()]

    def record_model_request_attempt(
        self, queue_task_id: int, worker_id: str, attempt: dict, decision: dict,
        lease_seconds: int = 300,
    ) -> dict:
        """Atomically append provider-attempt metadata and release/block the live task lease.

        Only allowlisted response headers are retained. Prompts, response bodies,
        credentials, and raw authorization headers are never persisted here.
        """
        import re
        from datetime import datetime, timezone, timedelta
        from urllib.parse import urlsplit

        required = ("attempt_number", "provider", "model", "endpoint", "error_classification")
        if not isinstance(queue_task_id, int) or isinstance(queue_task_id, bool) or queue_task_id < 1:
            raise ValueError("queue_task_id must be a positive integer")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(attempt, dict) or any(not attempt.get(key) for key in required):
            raise ValueError("attempt metadata is incomplete")
        if not isinstance(decision, dict):
            raise ValueError("decision must be an object")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        attempt_number = attempt["attempt_number"]
        if not isinstance(attempt_number, int) or isinstance(attempt_number, bool) or attempt_number < 1:
            raise ValueError("attempt_number must be positive")
        action = decision.get("action")
        if action not in {
            "schedule_retry", "block_until_reset", "split_or_decompose",
            "rebuild_smaller_context", "fail_or_require_configuration", "hold_for_review",
        }:
            raise ValueError("unsupported provider decision action")
        delay = decision.get("delay_seconds")
        if delay is not None and (not isinstance(delay, int) or isinstance(delay, bool) or not 0 <= delay <= 86400):
            raise ValueError("delay_seconds must be between 0 and 86400")
        if action == "schedule_retry" and delay is None:
            raise ValueError("scheduled retry requires delay_seconds")

        allowed_headers = {
            "retry-after", "x-ratelimit-reset", "ratelimit-reset", "x-quota-reset",
            "x-request-id", "request-id", "anthropic-ratelimit-requests-reset",
            "anthropic-ratelimit-tokens-reset", "x-ratelimit-remaining",
        }
        incoming_headers = attempt.get("headers") or {}
        if not isinstance(incoming_headers, dict):
            raise ValueError("headers must be an object")
        safe_headers = {
            str(key).lower(): str(value)[:256]
            for key, value in incoming_headers.items()
            if str(key).lower() in allowed_headers
        }
        # Persist a classification-oriented summary, not an arbitrary provider body.
        summary = str(decision.get("reason") or attempt["error_classification"])
        summary = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+", r"\1[REDACTED]", summary)
        summary = re.sub(r"(?i)(api[_-]?key\s*[:=]\s*)\S+", r"\1[REDACTED]", summary)[:1000]
        # Keep only the endpoint path: query strings and URL userinfo can carry secrets.
        parsed_endpoint = urlsplit(str(attempt["endpoint"]))
        safe_endpoint = (parsed_endpoint.path or "/")[:512]
        now = datetime.now(timezone.utc)
        scheduled_at = now + timedelta(seconds=delay) if delay is not None else None

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running'
                      AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (queue_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot record provider attempt without a live task lease")
                cursor.execute(
                    """
                    INSERT INTO yj64_model_request_attempts
                        (queue_task_id, attempt_number, provider, model, endpoint,
                         provider_request_id, error_classification, http_status,
                         retry_after_seconds, quota_reset_at, scheduled_retry_at,
                         reservation_id, safe_headers, error_summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING attempt_id
                    """,
                    (
                        queue_task_id, attempt_number, str(attempt["provider"])[:128],
                        str(attempt["model"])[:256], safe_endpoint,
                        attempt.get("provider_request_id"),
                        str(attempt["error_classification"])[:128],
                        attempt.get("http_status"), delay, attempt.get("quota_reset_at"),
                        scheduled_at, attempt.get("reservation_id"),
                        json.dumps(safe_headers, separators=(",", ":")), summary,
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    return {"recorded": False, "duplicate": True, "task_state": None}

                reservation_id = attempt.get("reservation_id")
                block_reason_override = None
                if reservation_id is not None:
                    cursor.execute(
                        """
                        SELECT input_tokens_estimated, output_tokens_estimated,
                               estimated_cost_usd, cost_estimate_known, state
                        FROM yj64_provider_request_reservations
                        WHERE reservation_id = %s AND queue_task_id = %s
                        FOR UPDATE
                        """,
                        (reservation_id, queue_task_id),
                    )
                    reservation = cursor.fetchone()
                    if reservation is None or reservation[4] not in {"sending", "accepted", "unknown"}:
                        raise RuntimeError("provider attempt is not linked to a sent durable reservation")
                    if attempt.get("http_status") is None:
                        # No response means delivery is ambiguous. Never blindly
                        # resend a request that may already have been processed.
                        cursor.execute(
                            """
                            UPDATE yj64_provider_request_reservations
                            SET state = 'unknown',
                                last_error_classification = %s
                            WHERE reservation_id = %s
                            """,
                            (str(attempt["error_classification"])[:128], reservation_id),
                        )
                        action = "hold_for_review"
                        block_reason_override = "request_outcome_unknown"
                        summary = "Provider delivery is ambiguous; reconcile the original idempotency key before retry"
                    else:
                        # A provider response was received. Settle conservatively
                        # using estimates unless the adapter supplied actual usage.
                        actual_input = attempt.get("input_tokens_actual")
                        actual_output = attempt.get("output_tokens_actual")
                        actual_input = reservation[0] if actual_input is None else actual_input
                        actual_output = reservation[1] if actual_output is None else actual_output
                        actual_cost = attempt.get("actual_cost_usd")
                        actual_cost = (
                            reservation[2] if reservation[3] else None
                        ) if actual_cost is None else actual_cost
                        cursor.execute(
                            """
                            UPDATE yj64_provider_request_reservations
                            SET state = 'failed', input_tokens_actual = %s,
                                output_tokens_actual = %s, actual_cost_usd = %s,
                                provider_request_id = COALESCE(%s, provider_request_id),
                                last_error_classification = %s, finished_at = now(),
                                expires_at = NULL
                            WHERE reservation_id = %s
                            """,
                            (
                                actual_input, actual_output, actual_cost,
                                attempt.get("provider_request_id"),
                                str(attempt["error_classification"])[:128], reservation_id,
                            ),
                        )
                        cursor.execute(
                            """
                            UPDATE yj64_task_queue
                            SET reserved_input_tokens = GREATEST(0, reserved_input_tokens - %s),
                                reserved_output_tokens = GREATEST(0, reserved_output_tokens - %s),
                                reserved_cost_usd = GREATEST(0, reserved_cost_usd - %s),
                                consumed_input_tokens = consumed_input_tokens + %s,
                                consumed_output_tokens = consumed_output_tokens + %s,
                                consumed_cost_usd = consumed_cost_usd + %s
                            WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                            """,
                            (
                                reservation[0], reservation[1], reservation[2],
                                actual_input, actual_output, actual_cost or 0,
                                queue_task_id, worker_id,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise RuntimeError("task lease was lost while settling failed provider request")

                if action == "schedule_retry":
                    cursor.execute(
                        """
                        UPDATE yj64_task_queue
                        SET state = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'pending' END,
                            available_at = CASE
                                WHEN attempts >= max_attempts THEN available_at
                                ELSE now() + (%s * interval '1 second')
                            END,
                            locked_at = NULL, lock_owner = NULL,
                            last_error = %s, updated_at = now()
                        WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                        RETURNING state
                        """,
                        (delay, summary, queue_task_id, worker_id),
                    )
                elif action == "fail_or_require_configuration":
                    cursor.execute(
                        """
                        UPDATE yj64_task_queue
                        SET state = 'failed', locked_at = NULL, lock_owner = NULL,
                            last_error = %s, updated_at = now()
                        WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                        RETURNING state
                        """,
                        (summary, queue_task_id, worker_id),
                    )
                elif action == "block_until_reset":
                    cursor.execute(
                        """
                        UPDATE yj64_task_queue
                        SET state = 'blocked', blocked_reason = 'quota_exhausted',
                            quota_reset_at = %s, locked_at = NULL, lock_owner = NULL,
                            last_error = %s, updated_at = now()
                        WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                        RETURNING state
                        """,
                        (attempt.get("quota_reset_at"), summary, queue_task_id, worker_id),
                    )
                else:
                    # Payload splitting, context rebuilding, and unknown failures
                    # remain blocked for an explicit orchestrator action.
                    cursor.execute(
                        """
                        UPDATE yj64_task_queue
                        SET state = 'blocked', blocked_reason = %s,
                            quota_reset_at = NULL, locked_at = NULL, lock_owner = NULL,
                            last_error = %s, updated_at = now()
                        WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                        RETURNING state
                        """,
                        (block_reason_override or action, summary, queue_task_id, worker_id),
                    )
                if cursor.rowcount != 1:
                    raise RuntimeError("task lease was lost while recording provider attempt")
                updated_state = cursor.fetchone()
                state = updated_state[0] if updated_state else (
                    "pending" if action == "schedule_retry" else (
                        "failed" if action == "fail_or_require_configuration" else "blocked"
                    )
                )
                return {"recorded": True, "duplicate": False, "task_state": state}
