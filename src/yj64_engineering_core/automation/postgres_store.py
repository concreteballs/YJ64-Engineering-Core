"""PostgreSQL persistence for the YJ64 autonomous engineering cycle."""

from __future__ import annotations

import json
from typing import Callable


class PostgresCycleStore:
    """Persist CI events and enqueue one idempotent follow-up task per run attempt.

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
        return psycopg.connect(self.database_url)

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
