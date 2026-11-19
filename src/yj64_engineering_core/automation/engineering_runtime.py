"""Explicit production wiring for the universal engineering task worker.

Deployments supply a configured dispatcher (with real solver/CAD backends) and
any additional task handlers. This module never guesses or creates external
executables, credentials, storage, or domain adapters.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..dispatcher import EngineeringDispatcher
from .engineering_task_adapter import EngineeringDispatcherTaskAdapter
from .parent_tasks import TaskAdapterRegistry, create_parent_task_handler
from .task_requests import PARENT_TASK_QUEUE_TYPE
from .worker import TaskHandler, WorkerRunner


ENGINEERING_TASK_TYPE = "engineering.analysis"
ENGINEERING_CAPABILITIES = ("engineering.dispatch",)


def create_engineering_task_registry(
    dispatcher: EngineeringDispatcher,
) -> TaskAdapterRegistry:
    """Create the allowlisted registry for the concrete configured dispatcher."""
    if not isinstance(dispatcher, EngineeringDispatcher):
        raise TypeError("dispatcher must be an explicitly configured EngineeringDispatcher")
    registry = TaskAdapterRegistry()
    registry.register(
        ENGINEERING_TASK_TYPE,
        EngineeringDispatcherTaskAdapter(dispatcher),
        capabilities=ENGINEERING_CAPABILITIES,
        council_enabled=False,
    )
    return registry


def create_engineering_worker_runner(
    store: Any,
    *,
    dispatcher: EngineeringDispatcher,
    worker_id: str,
    additional_handlers: Mapping[str, TaskHandler] | None = None,
    lease_seconds: int = 300,
    recovery_limit: int = 100,
) -> WorkerRunner:
    """Build a WorkerRunner with the universal parent-task handler wired in.

    Additional task handlers are preserved (for example CI event/log/patch
    handlers). A caller cannot override the universal ingress handler.
    """
    registry = create_engineering_task_registry(dispatcher)
    handlers = dict(additional_handlers or {})
    if PARENT_TASK_QUEUE_TYPE in handlers:
        raise ValueError(f"{PARENT_TASK_QUEUE_TYPE} is reserved by the universal task runtime")
    handlers[PARENT_TASK_QUEUE_TYPE] = create_parent_task_handler(registry)
    return WorkerRunner(
        store,
        worker_id=worker_id,
        handlers=handlers,
        lease_seconds=lease_seconds,
        recovery_limit=recovery_limit,
        allowed_task_types=list(handlers),
    )
