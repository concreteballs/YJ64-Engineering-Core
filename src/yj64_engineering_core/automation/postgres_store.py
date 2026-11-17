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

    def complete_task(self, task_id: int, worker_id: str) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE yj64_task_queue
                    SET state = 'completed', locked_at = NULL, lock_owner = NULL,
                        updated_at = now()
                    WHERE task_id = %s AND state = 'running' AND lock_owner = %s
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
                         safe_headers, error_summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING attempt_id
                    """,
                    (
                        queue_task_id, attempt_number, str(attempt["provider"])[:128],
                        str(attempt["model"])[:256], safe_endpoint,
                        attempt.get("provider_request_id"),
                        str(attempt["error_classification"])[:128],
                        attempt.get("http_status"), delay, attempt.get("quota_reset_at"),
                        scheduled_at, json.dumps(safe_headers, separators=(",", ":")), summary,
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    return {"recorded": False, "duplicate": True, "task_state": None}

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
                        """,
                        (action, summary, queue_task_id, worker_id),
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
