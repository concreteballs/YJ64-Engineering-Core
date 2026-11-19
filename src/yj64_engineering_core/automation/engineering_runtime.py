"""Explicit production wiring for the universal engineering task worker.

Deployments supply a configured dispatcher (with real solver/CAD backends) and
any additional task handlers. This module never guesses or creates external
executables, credentials, storage, or domain adapters.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..dispatcher import AxialMemberSolver, EngineeringDispatcher
from ..cad import FreeCADMacroBackend, OpenSCADSourceBackend, SVGDrawingBackend
from .engineering_task_adapter import EngineeringDispatcherTaskAdapter
from .parent_tasks import TaskAdapterRegistry, create_parent_task_handler
from .task_requests import PARENT_TASK_QUEUE_TYPE
from .worker import TaskHandler, WorkerRunner


ENGINEERING_TASK_TYPE = "engineering.analysis"
ENGINEERING_CAPABILITIES = ("engineering.dispatch",)


def create_reference_engineering_dispatcher(
    *,
    cad_workspace: str | None = None,
) -> EngineeringDispatcher:
    """Configure only built-in reference solvers and optional workspace CAD writers.

    The axial solver is a screening calculation. CAD backends write editable
    source/macro/drawing files; they do not launch FreeCAD or OpenSCAD.
    """
    dispatcher = EngineeringDispatcher()
    dispatcher.register_physics_solver(AxialMemberSolver())
    if cad_workspace is not None:
        dispatcher.register_cad_backend(
            "openscad_source", OpenSCADSourceBackend(cad_workspace)
        )
        dispatcher.register_cad_backend(
            "freecad_macro", FreeCADMacroBackend(cad_workspace)
        )
        dispatcher.register_cad_backend(
            "svg_drawing", SVGDrawingBackend(cad_workspace)
        )
    return dispatcher


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
