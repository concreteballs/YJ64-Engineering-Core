"""PostgreSQL persistence and leased task queue for the YJ64 cycle."""

from __future__ import annotations

import json
import re
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

    def get_ci_event(self, event_id: int) -> dict | None:
        """Fetch one persisted CI event by its database identity; read-only."""
        if not isinstance(event_id, int) or isinstance(event_id, bool) or event_id < 1:
            raise ValueError("event_id must be a positive integer")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT event_id, repository, run_id, run_attempt, workflow,
                           conclusion, commit_sha, branch, run_url, received_at
                    FROM yj64_ci_events
                    WHERE event_id = %s
                    """,
                    (event_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return {
                    "event_id": row[0], "repository": row[1], "run_id": row[2],
                    "run_attempt": row[3], "workflow": row[4], "conclusion": row[5],
                    "commit_sha": row[6], "branch": row[7], "run_url": row[8],
                    "received_at": row[9].isoformat() if row[9] is not None else None,
                }

    def enqueue_task(
        self, task_type: str, payload: dict, dedupe_key: str,
        *, max_attempts: int = 3,
    ) -> dict:
        """Idempotently enqueue one allowlisted internal task in the existing queue."""
        allowed_types = {
            "process_ci_event", "analyze_ci_logs", "prepare_ci_fix", "generate_ci_patch",
            "submit_council_request", "poll_council_request", "council_result_ready",
        }
        if task_type not in allowed_types:
            raise ValueError("task_type is not allowlisted")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if (
            not isinstance(dedupe_key, str)
            or not re.fullmatch(r"[A-Za-z0-9:._-]{1,240}", dedupe_key)
        ):
            raise ValueError("dedupe_key must be a bounded safe identifier")
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        payload_json = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO yj64_task_queue
                        (task_type, payload, dedupe_key, max_attempts)
                    VALUES (%s, %s::jsonb, %s, %s)
                    ON CONFLICT (dedupe_key) DO NOTHING
                    RETURNING task_id
                    """,
                    (task_type, payload_json, dedupe_key, max_attempts),
                )
                inserted = cursor.fetchone()
                if inserted is not None:
                    return {
                        "enqueued": True, "duplicate": False,
                        "task_id": inserted[0], "state": "pending",
                    }
                cursor.execute(
                    """
                    SELECT task_id, task_type, payload, state
                    FROM yj64_task_queue
                    WHERE dedupe_key = %s
                    """,
                    (dedupe_key,),
                )
                existing = cursor.fetchone()
                if (
                    existing is None
                    or existing[1] != task_type
                    or existing[2] != payload
                ):
                    raise ValueError("dedupe_key already exists with conflicting task content")
                return {
                    "enqueued": False, "duplicate": True,
                    "task_id": existing[0], "state": existing[3],
                }

    def claim_next_task(
        self, worker_id: str, lease_seconds: int = 300,
        task_types: list[str] | None = None,
    ) -> dict | None:
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(lease_seconds, int) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        if task_types is not None and (
            not isinstance(task_types, list) or not task_types
            or any(not isinstance(item, str) or not item.strip() for item in task_types)
        ):
            raise ValueError("task_types must be a non-empty list of task type names")

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
                          AND (%s::text[] IS NULL OR task_type = ANY(%s::text[]))
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
                    (task_types, task_types, lease_seconds, worker_id),
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
                      AND (deadline_at IS NULL OR deadline_at > now())
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
                      AND (deadline_at IS NULL OR deadline_at > now())
                      AND NOT EXISTS (
                          SELECT 1 FROM yj64_provider_request_reservations AS reservation
                          WHERE reservation.queue_task_id = yj64_task_queue.task_id
                            AND reservation.state IN ('reserved', 'sending', 'accepted', 'unknown')
                      )
                    """,
                    (task_id, worker_id),
                )
                completed = cursor.rowcount == 1
                if completed:
                    cursor.execute(
                        """UPDATE yj64_task_resume_events
                           SET consumed_at = COALESCE(consumed_at, now())
                           WHERE parent_task_id = %s AND consumed_at IS NULL""",
                        (task_id,),
                    )
                return completed

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
                if row and row[0] == "failed":
                    cursor.execute(
                        """UPDATE yj64_task_resume_events
                           SET consumed_at = COALESCE(consumed_at, now())
                           WHERE parent_task_id = %s AND consumed_at IS NULL""",
                        (task_id,),
                    )
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
                blocked = cursor.rowcount == 1
                if blocked:
                    cursor.execute(
                        """UPDATE yj64_task_resume_events
                           SET consumed_at = COALESCE(consumed_at, now())
                           WHERE parent_task_id = %s AND consumed_at IS NULL""",
                        (task_id,),
                    )
                return blocked


    def suspend_task_for_council(
        self, queue_task_id: int, worker_id: str, checkpoint: dict,
        council_request_id: str, lease_seconds: int = 300,
    ) -> bool:
        """Atomically persist the waiting checkpoint and release the parent lease."""
        from .checkpoints import verify_checkpoint
        if not isinstance(queue_task_id, int) or isinstance(queue_task_id, bool) or queue_task_id < 1:
            raise ValueError("queue_task_id must be a positive integer")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(council_request_id, str) or not council_request_id.strip() or len(council_request_id) > 256:
            raise ValueError("council_request_id must be a non-empty string of at most 256 characters")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        verify_checkpoint(checkpoint)
        if checkpoint.get("task_id") != str(queue_task_id):
            raise ValueError("checkpoint task_id does not match queue_task_id")
        state = checkpoint.get("task_state")
        if not isinstance(state, dict) or state.get("stage") != "waiting_council" or state.get("expected_council_request_id") != council_request_id:
            raise ValueError("checkpoint must identify the expected waiting council request")
        payload = json.dumps(checkpoint, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second') FOR UPDATE""",
                    (queue_task_id, worker_id, lease_seconds))
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot suspend without a live parent task lease")
                cursor.execute("""SELECT checkpoint_hash FROM yj64_task_checkpoints
                    WHERE queue_task_id = %s AND sequence = %s""",
                    (queue_task_id, checkpoint["sequence"]))
                existing = cursor.fetchone()
                if existing is not None and existing[0].strip() != checkpoint["checkpoint_hash"]:
                    raise ValueError("checkpoint sequence already exists with different content")
                if existing is None:
                    cursor.execute("""SELECT sequence, checkpoint_hash FROM yj64_task_checkpoints
                        WHERE queue_task_id = %s ORDER BY sequence DESC LIMIT 1 FOR UPDATE""",
                        (queue_task_id,))
                    latest = cursor.fetchone()
                    expected_sequence = latest[0] + 1 if latest else 1
                    expected_hash = latest[1].strip() if latest else None
                    if checkpoint["sequence"] != expected_sequence:
                        raise ValueError("checkpoint sequence must immediately follow the latest checkpoint")
                    if checkpoint["previous_checkpoint_hash"] != expected_hash:
                        raise ValueError("checkpoint previous hash does not match the latest checkpoint")
                    cursor.execute("""INSERT INTO yj64_task_checkpoints
                        (queue_task_id, sequence, schema_version, checkpoint_hash, previous_checkpoint_hash, checkpoint)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)""",
                        (queue_task_id, checkpoint["sequence"], checkpoint["schema_version"],
                         checkpoint["checkpoint_hash"], checkpoint["previous_checkpoint_hash"], payload))
                cursor.execute("""UPDATE yj64_task_queue
                    SET state = 'waiting', locked_at = NULL, lock_owner = NULL, updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')""",
                    (queue_task_id, worker_id, lease_seconds))
                if cursor.rowcount != 1:
                    raise RuntimeError("parent task lease was lost while entering council wait")
                return True

    def record_council_resume_event(
        self, parent_task_id: int, result_task_id: int, worker_id: str,
        council_request_id: str, result_artifact_ref: str, result_sha256: str,
        resume_payload: dict,
    ) -> dict:
        """Persist a validated Council handoff into the parent checkpoint and requeue it."""
        from .checkpoints import create_checkpoint, verify_checkpoint

        if any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in (parent_task_id, result_task_id)):
            raise ValueError("parent_task_id and result_task_id must be positive integers")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(council_request_id, str) or not council_request_id.strip() or len(council_request_id) > 256:
            raise ValueError("council_request_id must be a non-empty string of at most 256 characters")
        if not isinstance(result_artifact_ref, str) or not result_artifact_ref.strip() or len(result_artifact_ref) > 1024:
            raise ValueError("result_artifact_ref must be a non-empty string of at most 1024 characters")
        if not isinstance(result_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", result_sha256):
            raise ValueError("result_sha256 must be a lowercase SHA-256 hash")
        if not isinstance(resume_payload, dict) or resume_payload.get("model_output_is_untrusted_data") is not True:
            raise ValueError("resume_payload must explicitly mark Council output as untrusted")
        execution_status = resume_payload.get("execution_status")
        if execution_status == "completed":
            result = resume_payload.get("result")
            if (
                not isinstance(result, dict)
                or result.get("outcome") not in {
                    "consensus", "qualified_consensus",
                    "unresolved_disagreement", "insufficient_evidence",
                }
                or not isinstance(result.get("summary"), str)
                or not result["summary"].strip()
            ):
                raise ValueError("completed resume_payload must contain a validated Council result")
        elif execution_status in {"blocked", "failed", "cancelled"}:
            terminal = resume_payload.get("terminal")
            if not isinstance(terminal, dict) or terminal.get("status") != execution_status:
                raise ValueError("terminal resume_payload does not match its execution status")
        else:
            raise ValueError("resume_payload has an invalid execution status")
        try:
            serialized_resume = json.dumps(
                resume_payload, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("resume_payload must contain finite JSON data") from exc
        if len(serialized_resume.encode("utf-8")) > 256 * 1024:
            raise ValueError("resume_payload exceeds the 256 KiB checkpoint limit")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT task_id, payload FROM yj64_task_queue
                       WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                       FOR UPDATE""",
                    (result_task_id, worker_id),
                )
                result_task = cursor.fetchone()
                if result_task is None:
                    raise RuntimeError("council result task lease is not owned by this worker")
                result_task_payload = result_task[1]
                if isinstance(result_task_payload, str):
                    try:
                        result_task_payload = json.loads(result_task_payload)
                    except (TypeError, ValueError):
                        raise ValueError("council result task payload is invalid") from None
                if (
                    not isinstance(result_task_payload, dict)
                    or result_task_payload.get("parent_task_id") != parent_task_id
                    or result_task_payload.get("parent_task_ref") is not None
                    or result_task_payload.get("request_id") != council_request_id
                    or result_task_payload.get("result_artifact_ref") != result_artifact_ref
                    or result_task_payload.get("execution_status") != execution_status
                ):
                    raise ValueError("council result task does not match the requested parent resume")

                cursor.execute(
                    "SELECT state FROM yj64_task_queue WHERE task_id = %s FOR UPDATE",
                    (parent_task_id,),
                )
                parent = cursor.fetchone()
                if parent is None:
                    return {"accepted": False, "duplicate": False, "reason": "parent_not_found"}
                cursor.execute(
                    """SELECT result_task_id, result_artifact_ref, result_sha256
                       FROM yj64_task_resume_events
                       WHERE parent_task_id = %s AND council_request_id = %s""",
                    (parent_task_id, council_request_id),
                )
                existing_event = cursor.fetchone()
                if existing_event is not None:
                    existing = (
                        existing_event[0], existing_event[1],
                        existing_event[2].strip() if isinstance(existing_event[2], str) else existing_event[2],
                    )
                    if existing != (result_task_id, result_artifact_ref, result_sha256):
                        raise ValueError("council resume identity conflicts with an existing event")
                    return {
                        "accepted": True, "duplicate": True,
                        "parent_task_id": parent_task_id, "state": parent[0],
                    }
                if parent[0] != "waiting":
                    return {"accepted": False, "duplicate": False, "reason": "parent_not_waiting"}

                cursor.execute(
                    """SELECT checkpoint FROM yj64_task_checkpoints
                       WHERE queue_task_id = %s ORDER BY sequence DESC LIMIT 1 FOR UPDATE""",
                    (parent_task_id,),
                )
                latest = cursor.fetchone()
                if latest is None:
                    return {"accepted": False, "duplicate": False, "reason": "parent_checkpoint_missing"}
                parent_checkpoint = latest[0]
                if isinstance(parent_checkpoint, str):
                    try:
                        parent_checkpoint = json.loads(parent_checkpoint)
                    except (TypeError, ValueError):
                        raise ValueError("parent checkpoint is invalid") from None
                verify_checkpoint(parent_checkpoint)
                if parent_checkpoint.get("task_id") != str(parent_task_id):
                    raise ValueError("parent checkpoint task identity mismatch")
                parent_state = parent_checkpoint.get("task_state")
                if (
                    not isinstance(parent_state, dict)
                    or parent_state.get("stage") != "waiting_council"
                    or parent_state.get("expected_council_request_id") != council_request_id
                ):
                    return {"accepted": False, "duplicate": False, "reason": "council_request_mismatch"}

                event_payload = {
                    "source": "council_result_ready",
                    "execution_status": execution_status,
                    "result_artifact_ref": result_artifact_ref,
                    "result_sha256": result_sha256,
                }
                cursor.execute(
                    """INSERT INTO yj64_task_resume_events
                       (parent_task_id, result_task_id, council_request_id,
                        result_artifact_ref, result_sha256, event_payload)
                       VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                       ON CONFLICT (parent_task_id, council_request_id) DO NOTHING
                       RETURNING resume_event_id""",
                    (
                        parent_task_id, result_task_id, council_request_id,
                        result_artifact_ref, result_sha256,
                        json.dumps(event_payload, sort_keys=True, separators=(",", ":")),
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    cursor.execute(
                        """SELECT result_task_id, result_artifact_ref, result_sha256
                           FROM yj64_task_resume_events
                           WHERE parent_task_id = %s AND council_request_id = %s""",
                        (parent_task_id, council_request_id),
                    )
                    existing = cursor.fetchone()
                    if existing is None or (
                        existing[0], existing[1],
                        existing[2].strip() if isinstance(existing[2], str) else existing[2],
                    ) != (result_task_id, result_artifact_ref, result_sha256):
                        raise ValueError("council resume identity conflicts with an existing event")
                    return {
                        "accepted": True, "duplicate": True,
                        "parent_task_id": parent_task_id, "state": parent[0],
                    }

                resumed_state = dict(parent_state)
                resumed_state["stage"] = "council_resume_ready"
                resumed_state["council_resume"] = {
                    "resume_event_id": inserted[0],
                    "request_id": council_request_id,
                    "result_task_id": result_task_id,
                    "result_artifact_ref": result_artifact_ref,
                    "result_sha256": result_sha256,
                    "execution_status": execution_status,
                    "result": resume_payload.get("result") if execution_status == "completed" else None,
                    "terminal": resume_payload.get("terminal") if execution_status != "completed" else None,
                    "model_output_is_untrusted_data": True,
                }
                previous_artifacts = parent_checkpoint.get("artifact_refs", [])
                if not isinstance(previous_artifacts, list):
                    raise ValueError("parent checkpoint artifact_refs is invalid")
                resumed_artifacts = list(previous_artifacts)
                if execution_status == "completed" and result_artifact_ref not in resumed_artifacts:
                    resumed_artifacts.append(result_artifact_ref)
                resumed_checkpoint = create_checkpoint(
                    task_id=str(parent_task_id),
                    sequence=parent_checkpoint["sequence"] + 1,
                    state="checkpointed",
                    task_spec_version=parent_checkpoint["task_spec_version"],
                    task_state=resumed_state,
                    budgets=parent_checkpoint.get("budgets", {}),
                    approvals=parent_checkpoint.get("approvals", {}),
                    artifact_refs=resumed_artifacts,
                    previous_checkpoint_hash=parent_checkpoint["checkpoint_hash"],
                )
                cursor.execute(
                    """INSERT INTO yj64_task_checkpoints
                       (queue_task_id, sequence, schema_version, checkpoint_hash,
                        previous_checkpoint_hash, checkpoint)
                       VALUES (%s, %s, %s, %s, %s, %s::jsonb)""",
                    (
                        parent_task_id, resumed_checkpoint["sequence"],
                        resumed_checkpoint["schema_version"], resumed_checkpoint["checkpoint_hash"],
                        resumed_checkpoint["previous_checkpoint_hash"],
                        json.dumps(resumed_checkpoint, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                    ),
                )
                cursor.execute(
                    """UPDATE yj64_task_queue
                       SET state = 'pending', available_at = now(), blocked_reason = NULL,
                           locked_at = NULL, lock_owner = NULL, updated_at = now()
                       WHERE task_id = %s AND state = 'waiting'""",
                    (parent_task_id,),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("waiting parent could not be atomically requeued")
                return {
                    "accepted": True, "duplicate": False,
                    "resume_event_id": inserted[0],
                    "parent_task_id": parent_task_id, "state": "pending",
                }

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

    def expire_deadline_tasks(self, limit: int = 100) -> list[int]:
        """Fail pending tasks whose absolute deadline elapsed before execution."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH expired AS (
                        SELECT task_id FROM yj64_task_queue
                        WHERE state IN ('pending', 'blocked', 'running')
                          AND blocked_reason IS DISTINCT FROM 'request_outcome_unknown'
                          AND deadline_at IS NOT NULL AND deadline_at <= now()
                          AND NOT EXISTS (
                              SELECT 1 FROM yj64_provider_request_reservations AS reservation
                              WHERE reservation.queue_task_id = yj64_task_queue.task_id
                                AND reservation.state IN ('reserved', 'sending', 'accepted', 'unknown')
                          )
                        ORDER BY deadline_at, task_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                    )
                    UPDATE yj64_task_queue AS task
                    SET state = 'failed', blocked_reason = 'task_deadline_exceeded',
                        lock_owner = NULL, locked_at = NULL,
                        last_error = 'Task deadline elapsed before completion',
                        updated_at = now()
                    FROM expired
                    WHERE task.task_id = expired.task_id
                    RETURNING task.task_id
                    """,
                    (limit,),
                )
                return [row[0] for row in cursor.fetchall()]

    def run_recovery_maintenance(self, limit: int = 100) -> dict:
        """Run bounded durable recovery work; safe to invoke repeatedly."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        quota_tasks = self.recover_due_quota_tasks(limit=limit)
        expired_reservations = self.expire_unsent_provider_reservations(limit=limit)
        deadline_tasks = self.expire_deadline_tasks(limit=limit)
        return {
            "quota_tasks_requeued": quota_tasks,
            "unsent_reservations_expired": expired_reservations,
            "deadline_tasks_failed": deadline_tasks,
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

    def get_payload_for_analysis(self, source_task_id: int, payload_id: str) -> str:
        """Read and hash-verify a ready-for-model payload without changing its state."""
        from .payload_chunks import assemble_payload

        if not isinstance(source_task_id, int) or isinstance(source_task_id, bool) or source_task_id < 1:
            raise ValueError("source_task_id must be a positive integer")
        if not isinstance(payload_id, str) or not payload_id.strip():
            raise ValueError("payload_id is required")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT manifest, state FROM yj64_payload_manifests
                    WHERE payload_id = %s AND queue_task_id = %s
                    """,
                    (payload_id, source_task_id),
                )
                row = cursor.fetchone()
                if row is None or row[1] != "ready_for_model":
                    raise KeyError("verified ready-for-model payload was not found")
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
                chunks = {chunk_id: content for chunk_id, content in cursor.fetchall()}
                return assemble_payload(manifest, chunks)

    def get_ci_log_analysis(self, analysis_task_id: int) -> dict | None:
        """Read a durable structured CI analysis by its unique analysis task."""
        if not isinstance(analysis_task_id, int) or isinstance(analysis_task_id, bool) or analysis_task_id < 1:
            raise ValueError("analysis_task_id must be a positive integer")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT source_task_id, event_id, payload_id, provider, model,
                           provider_reservation_id, provider_request_id,
                           provider_response_artifact_ref, analysis_artifact_ref,
                           analysis_sha256, analysis_status, analysis_json,
                           input_tokens, output_tokens, actual_cost_usd
                    FROM yj64_ci_log_analyses
                    WHERE analysis_task_id = %s
                    """,
                    (analysis_task_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                report = row[11]
                if isinstance(report, str):
                    report = json.loads(report)
                return {
                    "source_task_id": row[0], "event_id": row[1],
                    "payload_id": row[2], "provider": row[3], "model": row[4],
                    "provider_reservation_id": row[5], "provider_request_id": row[6],
                    "provider_response_artifact_ref": row[7],
                    "analysis_artifact_ref": row[8],
                    "analysis_sha256": str(row[9]).strip(),
                    "analysis_status": row[10], "analysis_json": report,
                    "input_tokens": row[12], "output_tokens": row[13],
                    "actual_cost_usd": str(row[14]),
                }

    def get_latest_provider_reservation(
        self, queue_task_id: int, *, provider: str, model: str, endpoint: str,
    ) -> dict | None:
        """Read the latest provider reservation so retries never replay an ambiguous send."""
        if not isinstance(queue_task_id, int) or isinstance(queue_task_id, bool) or queue_task_id < 1:
            raise ValueError("queue_task_id must be a positive integer")
        if any(not isinstance(value, str) or not value.strip() for value in (provider, model, endpoint)):
            raise ValueError("provider, model and endpoint are required")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT reservation_id, idempotency_key, state, provider_request_id,
                           provider_result_ref, request_payload_sha256, input_tokens_estimated,
                           output_tokens_estimated, input_tokens_actual,
                           output_tokens_actual, actual_cost_usd,
                           last_error_classification
                    FROM yj64_provider_request_reservations
                    WHERE queue_task_id = %s AND provider = %s
                      AND model = %s AND endpoint = %s
                    ORDER BY created_at DESC, reservation_id DESC
                    LIMIT 1
                    """,
                    (queue_task_id, provider, model, endpoint),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return {
                    "reservation_id": row[0], "idempotency_key": row[1],
                    "state": row[2], "provider_request_id": row[3],
                    "provider_result_ref": row[4],
                    "request_payload_sha256": str(row[5]).strip(),
                    "input_tokens_estimated": row[6],
                    "output_tokens_estimated": row[7],
                    "input_tokens_actual": row[8],
                    "output_tokens_actual": row[9],
                    "actual_cost_usd": str(row[10]) if row[10] is not None else None,
                    "last_error_classification": row[11],
                }

    def save_ci_log_analysis(
        self, *, analysis_task_id: int, worker_id: str, lease_seconds: int,
        source_task_id: int, event_id: int, payload_id: str,
        provider: str, model: str, provider_reservation_id: str,
        provider_request_id: str | None, provider_response_artifact_ref: str,
        analysis_artifact_ref: str, analysis_sha256: str,
        analysis_status: str, analysis_json: dict, input_tokens: int,
        output_tokens: int, actual_cost_usd="0",
    ) -> dict:
        """Persist a structured analysis under the live task lease, idempotently."""
        import hashlib
        import re

        for name, value in (("analysis_task_id", analysis_task_id),
                            ("source_task_id", source_task_id), ("event_id", event_id)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        if any(not isinstance(value, str) or not value.strip() for value in (
            payload_id, provider, model, provider_reservation_id,
            provider_response_artifact_ref, analysis_artifact_ref,
        )):
            raise ValueError("analysis identity and artifact references are required")
        if any("?" in value or "#" in value for value in (
            provider_response_artifact_ref, analysis_artifact_ref,
        )):
            raise ValueError("analysis artifact references must be opaque, not signed URLs")
        if not isinstance(analysis_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", analysis_sha256):
            raise ValueError("analysis_sha256 must be a lowercase SHA-256 digest")
        if analysis_status not in {"completed", "invalid_response"}:
            raise ValueError("unsupported analysis_status")
        if not isinstance(analysis_json, dict):
            raise ValueError("analysis_json must be an object")
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0
               for value in (input_tokens, output_tokens)):
            raise ValueError("token counts must be non-negative integers")
        report_json = json.dumps(
            analysis_json, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        actual_hash = hashlib.sha256(report_json.encode("utf-8")).hexdigest()
        if actual_hash != analysis_sha256:
            raise ValueError("analysis_sha256 does not match canonical analysis JSON")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (analysis_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot persist CI analysis without a live task lease")
                cursor.execute(
                    """
                    INSERT INTO yj64_ci_log_analyses
                        (analysis_task_id, source_task_id, event_id, payload_id,
                         provider, model, provider_reservation_id, provider_request_id,
                         provider_response_artifact_ref, analysis_artifact_ref,
                         analysis_sha256, analysis_status, analysis_json,
                         input_tokens, output_tokens, actual_cost_usd)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (analysis_task_id) DO NOTHING
                    """,
                    (
                        analysis_task_id, source_task_id, event_id, payload_id,
                        provider, model, provider_reservation_id, provider_request_id,
                        provider_response_artifact_ref, analysis_artifact_ref,
                        analysis_sha256, analysis_status, report_json,
                        input_tokens, output_tokens, actual_cost_usd,
                    ),
                )
                cursor.execute(
                    """
                    SELECT analysis_sha256, analysis_artifact_ref, analysis_status
                    FROM yj64_ci_log_analyses WHERE analysis_task_id = %s
                    """,
                    (analysis_task_id,),
                )
                saved = cursor.fetchone()
                if saved is None or (
                    str(saved[0]).strip() != analysis_sha256
                    or saved[1] != analysis_artifact_ref
                    or saved[2] != analysis_status
                ):
                    raise ValueError("analysis task already has conflicting durable output")
                return {
                    "persisted": True, "analysis_task_id": analysis_task_id,
                    "analysis_sha256": analysis_sha256,
                    "analysis_artifact_ref": analysis_artifact_ref,
                    "analysis_status": analysis_status,
                }

    def get_ci_fix_proposal(self, proposal_task_id: int) -> dict | None:
        """Read one durable repair proposal by its unique queue task."""
        if not isinstance(proposal_task_id, int) or isinstance(proposal_task_id, bool) or proposal_task_id < 1:
            raise ValueError("proposal_task_id must be a positive integer")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT analysis_task_id, event_id, proposal_status, proposal_json,
                           proposal_artifact_ref, proposal_sha256
                    FROM yj64_ci_fix_proposals
                    WHERE proposal_task_id = %s
                    """,
                    (proposal_task_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                proposal = row[3]
                if isinstance(proposal, str):
                    proposal = json.loads(proposal)
                return {
                    "proposal_task_id": proposal_task_id,
                    "analysis_task_id": row[0],
                    "event_id": row[1],
                    "proposal_status": row[2],
                    "proposal_json": proposal,
                    "proposal_artifact_ref": row[4],
                    "proposal_sha256": str(row[5]).strip(),
                }

    def save_ci_fix_proposal(
        self, *, proposal_task_id: int, worker_id: str, lease_seconds: int,
        analysis_task_id: int, event_id: int, proposal_status: str,
        proposal_json: dict, proposal_artifact_ref: str, proposal_sha256: str,
    ) -> dict:
        """Persist a repair proposal only under the live queue-task lease."""
        import hashlib
        import re

        for name, value in (
            ("proposal_task_id", proposal_task_id),
            ("analysis_task_id", analysis_task_id),
            ("event_id", event_id),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        if proposal_status not in {"awaiting_review", "needs_more_evidence"}:
            raise ValueError("unsupported initial proposal status")
        if not isinstance(proposal_json, dict):
            raise ValueError("proposal_json must be an object")
        implementation = proposal_json.get("implementation")
        if (
            proposal_json.get("proposal_status") != proposal_status
            or not isinstance(implementation, dict)
            or implementation.get("auto_apply") is not False
            or implementation.get("human_approval_required") is not True
            or implementation.get("patch_ready") is not False
            or not isinstance(proposal_json.get("source"), dict)
            or proposal_json["source"].get("analysis_task_id") != analysis_task_id
            or proposal_json["source"].get("event_id") != event_id
        ):
            raise ValueError("proposal does not satisfy the human-approval safety gate")
        if not isinstance(proposal_artifact_ref, str) or not proposal_artifact_ref.strip():
            raise ValueError("proposal_artifact_ref is required")
        if "?" in proposal_artifact_ref or "#" in proposal_artifact_ref:
            raise ValueError("proposal artifact reference must be opaque")
        if not isinstance(proposal_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", proposal_sha256):
            raise ValueError("proposal_sha256 must be a lowercase SHA-256 digest")
        proposal_text = json.dumps(
            proposal_json, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        if hashlib.sha256(proposal_text.encode("utf-8")).hexdigest() != proposal_sha256:
            raise ValueError("proposal hash does not match canonical JSON")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (proposal_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot persist proposal without a live task lease")
                cursor.execute(
                    """
                    INSERT INTO yj64_ci_fix_proposals
                        (proposal_task_id, analysis_task_id, event_id, proposal_status,
                         proposal_json, proposal_artifact_ref, proposal_sha256)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (analysis_task_id) DO NOTHING
                    """,
                    (
                        proposal_task_id, analysis_task_id, event_id, proposal_status,
                        proposal_text, proposal_artifact_ref, proposal_sha256,
                    ),
                )
                cursor.execute(
                    """
                    SELECT proposal_task_id, event_id, proposal_status,
                           proposal_artifact_ref, proposal_sha256
                    FROM yj64_ci_fix_proposals
                    WHERE analysis_task_id = %s
                    """,
                    (analysis_task_id,),
                )
                saved = cursor.fetchone()
                if saved is None or (
                    saved[0] != proposal_task_id or saved[1] != event_id
                    or saved[2] != proposal_status or saved[3] != proposal_artifact_ref
                    or str(saved[4]).strip() != proposal_sha256
                ):
                    raise ValueError("analysis already has a conflicting CI fix proposal")
                return {
                    "persisted": True, "proposal_task_id": proposal_task_id,
                    "analysis_task_id": analysis_task_id,
                    "proposal_status": proposal_status,
                    "proposal_sha256": proposal_sha256,
                }

    def get_ci_patch_candidate(self, patch_task_id: int) -> dict | None:
        """Read one durable patch candidate by its unique worker task."""
        if not isinstance(patch_task_id, int) or isinstance(patch_task_id, bool) or patch_task_id < 1:
            raise ValueError("patch_task_id must be a positive integer")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT proposal_task_id, analysis_task_id, event_id,
                           candidate_status, candidate_json, candidate_artifact_ref,
                           candidate_sha256
                    FROM yj64_ci_patch_candidates
                    WHERE patch_task_id = %s
                    """,
                    (patch_task_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                payload = row[4]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                return {
                    "patch_task_id": patch_task_id, "proposal_task_id": row[0],
                    "analysis_task_id": row[1], "event_id": row[2],
                    "candidate_status": row[3], "candidate_json": payload,
                    "candidate_artifact_ref": row[5],
                    "candidate_sha256": str(row[6]).strip(),
                }

    def save_ci_patch_candidate(
        self, *, patch_task_id: int, worker_id: str, lease_seconds: int,
        proposal_task_id: int, analysis_task_id: int, event_id: int,
        candidate_status: str, candidate_json: dict,
        candidate_artifact_ref: str, candidate_sha256: str,
    ) -> dict:
        """Persist an inspected patch candidate only under its live queue lease."""
        import hashlib
        import re

        for name, value in (
            ("patch_task_id", patch_task_id), ("proposal_task_id", proposal_task_id),
            ("analysis_task_id", analysis_task_id), ("event_id", event_id),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if not isinstance(lease_seconds, int) or isinstance(lease_seconds, bool) or not 30 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 30 and 3600")
        allowed = {
            "awaiting_review", "needs_target_file_evidence",
            "source_files_changed_since_failure", "no_patch_recommended",
            "invalid_model_patch", "git_apply_check_failed",
        }
        if candidate_status not in allowed or not isinstance(candidate_json, dict):
            raise ValueError("candidate status or JSON is invalid")
        safety = candidate_json.get("safety")
        if (
            candidate_json.get("candidate_status") != candidate_status
            or not isinstance(safety, dict)
            or safety.get("human_approval_required") is not True
            or safety.get("auto_apply") is not False
            or safety.get("auto_commit") is not False
            or (candidate_status == "awaiting_review" and safety.get("git_apply_check") is not True)
        ):
            raise ValueError("candidate does not satisfy patch safety gates")
        if not isinstance(candidate_artifact_ref, str) or not candidate_artifact_ref.strip() or "?" in candidate_artifact_ref or "#" in candidate_artifact_ref:
            raise ValueError("candidate artifact reference must be opaque")
        if not isinstance(candidate_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", candidate_sha256):
            raise ValueError("candidate_sha256 must be a lowercase SHA-256 digest")
        serialized = json.dumps(candidate_json, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False)
        if hashlib.sha256(serialized.encode("utf-8")).hexdigest() != candidate_sha256:
            raise ValueError("candidate hash does not match canonical JSON")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT task_id FROM yj64_task_queue
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
                      AND locked_at >= now() - (%s * interval '1 second')
                    FOR UPDATE
                    """,
                    (patch_task_id, worker_id, lease_seconds),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("cannot persist patch candidate without a live task lease")
                cursor.execute(
                    """
                    INSERT INTO yj64_ci_patch_candidates
                        (patch_task_id, proposal_task_id, analysis_task_id, event_id,
                         candidate_status, candidate_json, candidate_artifact_ref, candidate_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (proposal_task_id) DO NOTHING
                    """,
                    (patch_task_id, proposal_task_id, analysis_task_id, event_id,
                     candidate_status, serialized, candidate_artifact_ref, candidate_sha256),
                )
                cursor.execute(
                    """
                    SELECT patch_task_id, analysis_task_id, event_id, candidate_status,
                           candidate_artifact_ref, candidate_sha256
                    FROM yj64_ci_patch_candidates WHERE proposal_task_id = %s
                    """,
                    (proposal_task_id,),
                )
                row = cursor.fetchone()
                if row is None or (
                    row[0] != patch_task_id or row[1] != analysis_task_id
                    or row[2] != event_id or row[3] != candidate_status
                    or row[4] != candidate_artifact_ref
                    or str(row[5]).strip() != candidate_sha256
                ):
                    raise ValueError("proposal already has a conflicting patch candidate")
                return {"persisted": True, "patch_task_id": patch_task_id,
                        "proposal_task_id": proposal_task_id,
                        "candidate_status": candidate_status,
                        "candidate_sha256": candidate_sha256}

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
                      AND provider_requests_reserved = 0 AND provider_requests_consumed = 0
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
        if all(value is None for value in (
            daily_token_limit, monthly_token_limit,
            daily_cost_limit_usd, monthly_cost_limit_usd,
            daily_request_limit, monthly_request_limit,
        )):
            raise ValueError("at least one global daily or monthly usage ceiling must be configured")
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
                if global_budget is None or all(value is None for value in global_budget):
                    return {
                        "reserved": False, "action": "hold_for_review",
                        "reason": "No explicit global usage budget is configured; refusing an unbounded provider request",
                    }
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
                      AND (deadline_at IS NULL OR deadline_at > now())
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
        provider_request_id: str | None = None, provider_result_ref: str | None = None,
        error_classification: str | None = None,
        lease_seconds: int = 300,
    ) -> dict:
        """Close a sent request or conservatively retain an ambiguous one as unknown."""
        from decimal import Decimal, InvalidOperation

        if outcome not in {"completed", "failed", "unknown"}:
            raise ValueError("outcome must be completed, failed or unknown")
        if outcome == "completed" and (
            not isinstance(provider_result_ref, str) or not provider_result_ref.strip()
            or len(provider_result_ref) > 1024
        ):
            raise ValueError("completed provider request requires a durable provider_result_ref")
        if provider_result_ref is not None and (
            "?" in provider_result_ref or "#" in provider_result_ref
        ):
            raise ValueError("provider_result_ref must be an opaque artifact reference, not a signed URL")
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
                        provider_result_ref = COALESCE(%s, provider_result_ref),
                        last_error_classification = %s,
                        finished_at = now(), expires_at = NULL
                    WHERE reservation_id = %s
                    """,
                    (
                        outcome, actual_input, actual_output, final_cost,
                        provider_request_id, provider_result_ref,
                        error_classification, reservation_id,
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
