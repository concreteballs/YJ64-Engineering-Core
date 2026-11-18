"""Queue ingress for generic, versioned YJ64 parent task requests.

This is an adapter into the existing cycle queue, not a second queue or worker.
Execution remains disabled until a matching parent-task handler is registered.
"""
from __future__ import annotations

from typing import Any

from ..task_contracts import TaskRequest


PARENT_TASK_QUEUE_TYPE = "execute_task_request"


def enqueue_task_request(
    store: Any,
    request: TaskRequest,
    *,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Persist one generic task envelope in the existing PostgreSQL cycle queue.

    The task ID is the stable idempotency identity. PostgresCycleStore compares
    the existing task type and canonical payload when this key is reused, so a
    changed request cannot silently replace or alias an earlier task.
    """
    if not callable(getattr(store, "enqueue_task", None)):
        raise TypeError("store must provide enqueue_task()")
    if not isinstance(request, TaskRequest):
        raise TypeError("request must be a TaskRequest")

    return store.enqueue_task(
        PARENT_TASK_QUEUE_TYPE,
        {"task_request": request.to_dict()},
        dedupe_key=f"task-request:{request.task_id}",
        max_attempts=max_attempts,
    )
