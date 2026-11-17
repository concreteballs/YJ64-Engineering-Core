"""Single-step durable worker orchestration.

This module deliberately does not start a background loop or select a provider.
A deployment must explicitly construct a WorkerRunner and call run_once().
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Mapping, Protocol


@dataclass(frozen=True)
class TaskExecutionResult:
    """A handler's explicit, bounded decision for the claimed task."""

    outcome: str
    reason: str = ""
    retry_delay_seconds: int = 60

    def __post_init__(self) -> None:
        if self.outcome not in {"completed", "retry", "blocked"}:
            raise ValueError("outcome must be completed, retry or blocked")
        if not isinstance(self.reason, str) or (self.reason and not re.fullmatch(r"[a-z][a-z0-9_.:-]{0,119}", self.reason)):
            raise ValueError("reason must be a safe lowercase classification")
        if (
            not isinstance(self.retry_delay_seconds, int)
            or isinstance(self.retry_delay_seconds, bool)
            or not 0 <= self.retry_delay_seconds <= 86400
        ):
            raise ValueError("retry_delay_seconds must be between 0 and 86400")


class CycleStore(Protocol):
    def run_recovery_maintenance(self, limit: int = 100) -> dict: ...
    def claim_next_task(self, worker_id: str, lease_seconds: int = 300) -> dict | None: ...
    def renew_task_lease(self, task_id: int, worker_id: str, lease_seconds: int = 300) -> bool: ...
    def save_checkpoint(self, queue_task_id: int, worker_id: str, checkpoint: dict, lease_seconds: int = 300) -> bool: ...
    def load_latest_checkpoint(self, queue_task_id: int) -> dict | None: ...
    def complete_task(self, task_id: int, worker_id: str) -> bool: ...
    def fail_task(self, task_id: int, worker_id: str, error: str, retry_delay_seconds: int = 60) -> str | None: ...
    def block_task(self, task_id: int, worker_id: str, reason: str) -> bool: ...


@dataclass(frozen=True)
class TaskContext:
    """Lease-scoped operations exposed to a task handler."""

    store: CycleStore
    task_id: int
    worker_id: str
    lease_seconds: int

    def renew_lease(self) -> bool:
        return self.store.renew_task_lease(
            self.task_id, self.worker_id, self.lease_seconds
        )

    def save_checkpoint(self, checkpoint: dict) -> bool:
        return self.store.save_checkpoint(
            self.task_id, self.worker_id, checkpoint, self.lease_seconds
        )

    def load_latest_checkpoint(self) -> dict | None:
        return self.store.load_latest_checkpoint(self.task_id)


TaskHandler = Callable[[dict, TaskContext], TaskExecutionResult]


class WorkerRunner:
    """Execute at most one leased task per explicit invocation.

    Recovery maintenance runs before claiming work. Unknown task types are
    blocked rather than silently discarded. Handler exceptions are reduced to
    their class name before persistence so exception text cannot leak secrets.
    """

    def __init__(
        self,
        store: CycleStore,
        *,
        worker_id: str,
        handlers: Mapping[str, TaskHandler],
        lease_seconds: int = 300,
        recovery_limit: int = 100,
    ) -> None:
        if not isinstance(worker_id, str) or not worker_id.strip():
            raise ValueError("worker_id is required")
        if (
            not isinstance(lease_seconds, int)
            or isinstance(lease_seconds, bool)
            or not 30 <= lease_seconds <= 3600
        ):
            raise ValueError("lease_seconds must be between 30 and 3600")
        if (
            not isinstance(recovery_limit, int)
            or isinstance(recovery_limit, bool)
            or not 1 <= recovery_limit <= 1000
        ):
            raise ValueError("recovery_limit must be between 1 and 1000")
        if not isinstance(handlers, Mapping):
            raise ValueError("handlers must be a mapping")
        for task_type, handler in handlers.items():
            if not isinstance(task_type, str) or not task_type.strip() or not callable(handler):
                raise ValueError("each handler needs a non-empty task type and callable")
        self.store = store
        self.worker_id = worker_id.strip()
        self.handlers = dict(handlers)
        self.lease_seconds = lease_seconds
        self.recovery_limit = recovery_limit

    def run_once(self) -> dict:
        """Run recovery and process no more than one task; never loops in background."""
        recovery = self.store.run_recovery_maintenance(limit=self.recovery_limit)
        task = self.store.claim_next_task(self.worker_id, self.lease_seconds)
        if task is None:
            return {"status": "idle", "recovery": recovery}

        task_id = task.get("task_id")
        task_type = task.get("task_type")
        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id < 1:
            raise RuntimeError("claimed task has an invalid task_id")
        if not isinstance(task_type, str) or not task_type.strip():
            blocked = self.store.block_task(task_id, self.worker_id, "invalid_task_type")
            return {"status": "blocked" if blocked else "lease_lost", "task_id": task_id, "reason": "invalid_task_type", "recovery": recovery}
        handler = self.handlers.get(task_type)
        if handler is None:
            blocked = self.store.block_task(
                task_id, self.worker_id, "no_handler_registered"
            )
            return {
                "status": "blocked" if blocked else "lease_lost",
                "task_id": task_id,
                "reason": "no_handler_registered",
                "recovery": recovery,
            }

        context = TaskContext(
            store=self.store,
            task_id=task_id,
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        try:
            decision = handler(task, context)
            if not isinstance(decision, TaskExecutionResult):
                raise TypeError("handler_must_return_TaskExecutionResult")
        except Exception as exc:
            state = self.store.fail_task(
                task_id,
                self.worker_id,
                "handler_exception:" + type(exc).__name__,
                retry_delay_seconds=60,
            )
            return {
                "status": state or "lease_lost",
                "task_id": task_id,
                "reason": "handler_exception",
                "error_type": type(exc).__name__,
                "recovery": recovery,
            }

        if decision.outcome == "completed":
            completed = self.store.complete_task(task_id, self.worker_id)
            return {
                "status": "completed" if completed else "lease_lost",
                "task_id": task_id,
                "recovery": recovery,
            }
        if decision.outcome == "retry":
            state = self.store.fail_task(
                task_id,
                self.worker_id,
                decision.reason or "handler_requested_retry",
                retry_delay_seconds=decision.retry_delay_seconds,
            )
            return {
                "status": state or "lease_lost",
                "task_id": task_id,
                "reason": "retry_scheduled" if state else "lease_lost",
                "recovery": recovery,
            }

        blocked = self.store.block_task(
            task_id, self.worker_id, decision.reason or "handler_requested_block"
        )
        return {
            "status": "blocked" if blocked else "lease_lost",
            "task_id": task_id,
            "reason": "handler_requested_block",
            "recovery": recovery,
        }
