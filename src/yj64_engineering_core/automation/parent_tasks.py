"""Universal parent-task handler with an explicit execution-adapter registry.

The coordinator owns validation, routing and resume-state delivery. Domain work
belongs to registered adapters; no adapter is loaded or guessed dynamically.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Mapping

from ..task_contracts import TaskRequest
from .worker import TaskExecutionResult
from .task_requests import PARENT_TASK_QUEUE_TYPE
from .checkpoints import verify_checkpoint


_TASK_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class ParentTaskState:
    """Durable parent state delivered to an adapter on first run and resume."""

    stage: str
    resume_state: dict[str, Any]
    council_resume_event: dict[str, Any] | None
    artifact_refs: tuple[str, ...]


TaskAdapter = Callable[[TaskRequest, ParentTaskState, Any], TaskExecutionResult]


@dataclass(frozen=True)
class TaskAdapterRegistration:
    task_type: str
    adapter: TaskAdapter
    capabilities: frozenset[str]
    council_enabled: bool


class TaskAdapterRegistry:
    """In-memory allowlist of explicitly constructed task execution adapters."""

    def __init__(self) -> None:
        self._registrations: dict[str, TaskAdapterRegistration] = {}

    @property
    def registrations(self) -> Mapping[str, TaskAdapterRegistration]:
        return dict(self._registrations)

    def register(
        self,
        task_type: str,
        adapter: TaskAdapter,
        *,
        capabilities: tuple[str, ...] | list[str] = (),
        council_enabled: bool = False,
    ) -> None:
        if not isinstance(task_type, str) or not _TASK_TYPE.fullmatch(task_type):
            raise ValueError("task_type must be a lowercase identifier")
        if not callable(adapter):
            raise TypeError("adapter must be callable")
        if not isinstance(council_enabled, bool):
            raise TypeError("council_enabled must be a boolean")
        if not isinstance(capabilities, (tuple, list)):
            raise TypeError("capabilities must be a list or tuple")
        normalized = tuple(capabilities)
        if any(not isinstance(item, str) or not _CAPABILITY.fullmatch(item) for item in normalized):
            raise ValueError("capabilities contains an invalid capability")
        if len(set(normalized)) != len(normalized):
            raise ValueError("capabilities must be unique")
        if task_type in self._registrations:
            raise ValueError(f"task adapter already registered: {task_type}")
        self._registrations[task_type] = TaskAdapterRegistration(
            task_type=task_type,
            adapter=adapter,
            capabilities=frozenset(normalized),
            council_enabled=council_enabled,
        )

    def get(self, task_type: str) -> TaskAdapterRegistration | None:
        return self._registrations.get(task_type)


class _CouncilGuardStore:
    """Narrow store proxy that enforces council_policy='never'."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def enqueue_council_task_and_suspend_parent(self, *args: Any, **kwargs: Any) -> dict:
        raise PermissionError("Council use is forbidden by this task request")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)


class _CouncilGuardContext:
    """Lease-scoped context proxy with Council disabled."""

    def __init__(self, context: Any) -> None:
        self._context = context
        self.store = _CouncilGuardStore(context.store)
        self.task_id = context.task_id
        self.worker_id = context.worker_id
        self.lease_seconds = context.lease_seconds

    def suspend_for_council(self, *args: Any, **kwargs: Any) -> bool:
        raise PermissionError("Council use is forbidden by this task request")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._context, name)


def _parent_state(context: Any) -> ParentTaskState:
    checkpoint = context.load_latest_checkpoint()
    if checkpoint is None:
        return ParentTaskState(
            stage="new",
            resume_state={},
            council_resume_event=None,
            artifact_refs=(),
        )
    if not isinstance(checkpoint, dict) or checkpoint.get("task_id") != str(context.task_id):
        raise ValueError("parent_checkpoint_identity_mismatch")
    verify_checkpoint(checkpoint)
    state = checkpoint.get("task_state")
    if not isinstance(state, dict):
        raise ValueError("parent_checkpoint_state_invalid")
    stage = state.get("stage")
    if stage == "waiting_council":
        raise ValueError("parent_waiting_for_council_without_resume_event")
    resume_state = state.get("resume_state", {})
    if not isinstance(resume_state, dict):
        raise ValueError("parent_resume_state_invalid")
    resume_event = state.get("council_resume_event")
    if resume_event is not None:
        if not isinstance(resume_event, dict):
            raise ValueError("parent_council_resume_event_invalid")
        artifact_ref = resume_event.get("result_artifact_ref")
        result_hash = resume_event.get("result_sha256")
        if (
            not isinstance(artifact_ref, str) or not artifact_ref.strip()
            or not isinstance(result_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", result_hash)
        ):
            raise ValueError("parent_council_resume_event_invalid")
    if stage == "council_result_received" and resume_event is None:
        raise ValueError("parent_council_resume_event_missing")
    refs = checkpoint.get("artifact_refs", [])
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise ValueError("parent_artifact_refs_invalid")
    return ParentTaskState(
        stage=stage if isinstance(stage, str) else "checkpointed",
        resume_state=dict(resume_state),
        council_resume_event=dict(resume_event) if resume_event is not None else None,
        artifact_refs=tuple(refs),
    )


def handle_parent_task_request(
    task: dict,
    context: Any,
    *,
    registry: TaskAdapterRegistry,
) -> TaskExecutionResult:
    """Validate, route and resume one generic parent task through a registered adapter."""
    try:
        if not isinstance(task, dict) or task.get("task_type") != PARENT_TASK_QUEUE_TYPE:
            return TaskExecutionResult("blocked", "invalid_parent_task_type")
        payload = task.get("payload")
        if not isinstance(payload, dict) or set(payload) != {"task_request"}:
            return TaskExecutionResult("blocked", "invalid_parent_task_payload")
        request = TaskRequest.from_dict(payload["task_request"])
        if not isinstance(registry, TaskAdapterRegistry):
            return TaskExecutionResult("blocked", "task_adapter_registry_unavailable")
        registration = registry.get(request.task_type)
        if registration is None:
            return TaskExecutionResult("blocked", "no_task_adapter_registered")
        missing = set(request.requested_capabilities) - registration.capabilities
        if missing:
            return TaskExecutionResult("blocked", "task_capability_not_registered")
        state = _parent_state(context)
        if request.council_policy == "required" and not registration.council_enabled:
            return TaskExecutionResult("blocked", "required_council_not_supported")
        if request.council_policy == "never" and state.stage == "council_result_received":
            return TaskExecutionResult("blocked", "unexpected_council_resume_forbidden")
        adapter_context = (
            _CouncilGuardContext(context)
            if request.council_policy == "never"
            else context
        )
        decision = registration.adapter(request, state, adapter_context)
        if not isinstance(decision, TaskExecutionResult):
            return TaskExecutionResult("blocked", "adapter_returned_invalid_result")
        if (
            request.council_policy == "required"
            and state.stage != "council_result_received"
            and decision.outcome != "suspended"
        ):
            return TaskExecutionResult("blocked", "required_council_handoff_missing")
        return decision
    except PermissionError:
        return TaskExecutionResult("blocked", "council_use_forbidden")
    except (TypeError, ValueError, KeyError):
        return TaskExecutionResult("blocked", "invalid_parent_task_request")



def create_parent_task_handler(
    registry: TaskAdapterRegistry,
) -> Callable[[dict, Any], TaskExecutionResult]:
    """Bind an explicit registry for WorkerRunner's task-type handler map."""
    if not isinstance(registry, TaskAdapterRegistry):
        raise TypeError("registry must be a TaskAdapterRegistry")

    def handler(task: dict, context: Any) -> TaskExecutionResult:
        return handle_parent_task_request(task, context, registry=registry)

    return handler
