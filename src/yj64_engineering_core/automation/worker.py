"""Single-step durable worker orchestration.

This module deliberately does not start a background loop or select a provider.
A deployment must explicitly construct a WorkerRunner and call run_once().
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class TaskExecutionResult:
    """A handler's explicit, bounded decision for the claimed task."""

    outcome: str
    reason: str = ""
    retry_delay_seconds: int = 60

    def __post_init__(self) -> None:
        if self.outcome not in {"completed", "retry", "blocked", "suspended"}:
            raise ValueError("outcome must be completed, retry, blocked or suspended")
        if not isinstance(self.reason, str) or (
            self.reason and not re.fullmatch(r"[a-z][a-z0-9_.:-]{0,119}", self.reason)
        ):
            raise ValueError("reason must be a safe lowercase classification")
        if (
            not isinstance(self.retry_delay_seconds, int)
            or isinstance(self.retry_delay_seconds, bool)
            or not 0 <= self.retry_delay_seconds <= 86400
        ):
            raise ValueError("retry_delay_seconds must be between 0 and 86400")


@dataclass(frozen=True)
class ProviderReconciliationDecision:
    """Evidence-backed resolution of one ambiguous provider request."""

    reservation_id: str
    outcome: str
    evidence_ref: str
    provider_result_ref: str | None = None
    provider_request_id: str | None = None
    input_tokens_actual: int | None = None
    output_tokens_actual: int | None = None
    actual_cost_usd: str | int | float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reservation_id, str) or not self.reservation_id.strip():
            raise ValueError("reservation_id is required")
        if self.outcome not in {"provider_found", "provider_not_found"}:
            raise ValueError("invalid reconciliation outcome")
        for name, value in (
            ("evidence_ref", self.evidence_ref),
            ("provider_result_ref", self.provider_result_ref),
            ("provider_request_id", self.provider_request_id),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 1024
            ):
                raise ValueError(f"{name} must be a non-empty string of at most 1024 characters")
        if not self.evidence_ref:
            raise ValueError("evidence_ref is required")
        if self.outcome == "provider_found" and not self.provider_result_ref:
            raise ValueError("provider_found requires a durable provider_result_ref")
        if self.outcome == "provider_not_found" and self.provider_result_ref is not None:
            raise ValueError("provider_not_found cannot include a provider_result_ref")
        for name, value in (
            ("input_tokens_actual", self.input_tokens_actual),
            ("output_tokens_actual", self.output_tokens_actual),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None")


class CycleStore(Protocol):
    def run_recovery_maintenance(self, limit: int = 100) -> dict: ...
    def claim_next_task(self, worker_id: str, lease_seconds: int = 300, task_types: list[str] | None = None) -> dict | None: ...
    def claim_next_reconciliation_task(self, worker_id: str, lease_seconds: int = 300) -> dict | None: ...
    def list_unknown_provider_requests(self, queue_task_id: int, worker_id: str, lease_seconds: int = 300) -> list[dict]: ...
    def list_recovered_provider_results(self, queue_task_id: int, worker_id: str, lease_seconds: int = 300) -> list[dict]: ...
    def resolve_unknown_provider_request(self, queue_task_id: int, worker_id: str, reservation_id: str, **kwargs) -> dict: ...
    def renew_task_lease(self, task_id: int, worker_id: str, lease_seconds: int = 300) -> bool: ...
    def save_checkpoint(self, queue_task_id: int, worker_id: str, checkpoint: dict, lease_seconds: int = 300) -> bool: ...
    def load_latest_checkpoint(self, queue_task_id: int) -> dict | None: ...
    def suspend_task_for_council(self, queue_task_id: int, worker_id: str, checkpoint: dict, council_request_id: str, lease_seconds: int = 300) -> bool: ...
    def record_council_resume_event(self, parent_task_id: int, result_task_id: int, worker_id: str, council_request_id: str, result_artifact_ref: str, result_sha256: str, resume_payload: dict) -> dict: ...
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

    def suspend_for_council(self, checkpoint: dict, council_request_id: str) -> bool:
        """Persist the parent checkpoint and release its lease while awaiting Council."""
        return self.store.suspend_task_for_council(
            self.task_id, self.worker_id, checkpoint, council_request_id, self.lease_seconds
        )

    _council_resume_required: bool = field(default=False, init=False, compare=False, repr=False)
    _council_resume_loaded: bool = field(default=False, init=False, compare=False, repr=False)
    _council_resume_expected_request_id: str | None = field(default=None, init=False, compare=False, repr=False)

    def record_council_resume_event(
        self, parent_task_id: int, council_request_id: str,
        result_artifact_ref: str, result_sha256: str, resume_payload: dict,
    ) -> dict:
        """Atomically persist the validated result and wake its waiting parent."""
        return self.store.record_council_resume_event(
            parent_task_id, self.task_id, self.worker_id, council_request_id,
            result_artifact_ref, result_sha256, resume_payload,
        )

    def _require_council_resume(self, checkpoint: dict) -> None:
        from .checkpoints import verify_checkpoint
        verify_checkpoint(checkpoint)
        if checkpoint.get("task_id") != str(self.task_id):
            raise ValueError("council resume checkpoint belongs to another task")
        state = checkpoint.get("task_state")
        resume = state.get("council_resume") if isinstance(state, dict) else None
        request_id = resume.get("request_id") if isinstance(resume, dict) else None
        if (
            not isinstance(state, dict)
            or state.get("stage") != "council_resume_ready"
            or not isinstance(request_id, str) or not request_id
        ):
            raise ValueError("checkpoint does not contain a pending council resume")
        object.__setattr__(self, "_council_resume_required", True)
        object.__setattr__(self, "_council_resume_expected_request_id", request_id)

    def load_council_resume(self) -> dict | None:
        """Load the untrusted Council handoff from this task's latest checkpoint."""
        from .checkpoints import verify_checkpoint
        checkpoint = self.load_latest_checkpoint()
        if checkpoint is None:
            return None
        verify_checkpoint(checkpoint)
        if checkpoint.get("task_id") != str(self.task_id):
            raise ValueError("council resume checkpoint belongs to another task")
        state = checkpoint.get("task_state")
        if not isinstance(state, dict):
            raise ValueError("task checkpoint state is invalid")
        if state.get("stage") != "council_resume_ready":
            return None
        self._require_council_resume(checkpoint)
        resume = state.get("council_resume")
        if not isinstance(resume, dict):
            raise ValueError("council resume payload is missing")
        if (
            not isinstance(resume.get("result_task_id"), int)
            or isinstance(resume.get("result_task_id"), bool)
            or resume["result_task_id"] < 1
            or not isinstance(resume.get("result_artifact_ref"), str)
            or not resume["result_artifact_ref"]
            or not isinstance(resume.get("result_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", resume["result_sha256"])
            or resume.get("model_output_is_untrusted_data") is not True
        ):
            raise ValueError("council resume identity or trust marker is invalid")
        status = resume.get("execution_status")
        if status == "completed":
            result = resume.get("result")
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("summary"), str)
                or not result.get("summary")
                or result.get("outcome") not in {
                    "consensus", "qualified_consensus",
                    "unresolved_disagreement", "insufficient_evidence",
                }
            ):
                raise ValueError("completed council resume result is invalid")
        elif status in {"blocked", "failed", "cancelled"}:
            terminal = resume.get("terminal")
            if not isinstance(terminal, dict) or terminal.get("status") != status:
                raise ValueError("terminal council resume result is invalid")
        else:
            raise ValueError("council resume execution status is invalid")
        object.__setattr__(self, "_council_resume_loaded", True)
        return {
            **resume,
            "parent_task_id": self.task_id,
            "parent_task_state": {
                key: value for key, value in state.items() if key != "council_resume"
            },
        }

    def list_recovered_provider_results(self) -> list[dict]:
        """Return durable result references; task handlers must consume these before issuing new calls."""
        return self.store.list_recovered_provider_results(
            self.task_id, self.worker_id, self.lease_seconds
        )


TaskHandler = Callable[[dict, TaskContext], TaskExecutionResult]
ReconciliationHandler = Callable[
    [dict, list[dict], list[dict], TaskContext],
    Sequence[ProviderReconciliationDecision],
]


class WorkerRunner:
    """Execute at most one leased task per explicit invocation.

    Reconciliation is opt-in. It runs before ordinary work only when an
    evidence-checking reconciliation handler is configured. No provider request
    is sent by this runner. Ambiguous requests remain blocked unless the
    handler returns explicit evidence-backed decisions.
    """

    def __init__(
        self,
        store: CycleStore,
        *,
        worker_id: str,
        handlers: Mapping[str, TaskHandler],
        reconciliation_handler: ReconciliationHandler | None = None,
        lease_seconds: int = 300,
        recovery_limit: int = 100,
        allowed_task_types: list[str] | None = None,
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
        if reconciliation_handler is not None and not callable(reconciliation_handler):
            raise ValueError("reconciliation_handler must be callable")
        if allowed_task_types is not None and (
            not isinstance(allowed_task_types, list) or not allowed_task_types
            or any(not isinstance(item, str) or not item.strip() for item in allowed_task_types)
        ):
            raise ValueError("allowed_task_types must be a non-empty list of task type names")
        if allowed_task_types is not None and not set(handlers).issuperset(allowed_task_types):
            raise ValueError("every allowed task type must have a registered handler")
        self.store = store
        self.worker_id = worker_id.strip()
        self.handlers = dict(handlers)
        self.reconciliation_handler = reconciliation_handler
        self.lease_seconds = lease_seconds
        self.recovery_limit = recovery_limit
        self.allowed_task_types = list(allowed_task_types) if allowed_task_types is not None else None

    def run_once(self) -> dict:
        """Run recovery and process no more than one task; never loops in background."""
        recovery = self.store.run_recovery_maintenance(limit=self.recovery_limit)

        if self.reconciliation_handler is not None:
            reconciliation_task = self.store.claim_next_reconciliation_task(
                self.worker_id, self.lease_seconds
            )
            if reconciliation_task is not None:
                return self._reconcile_once(reconciliation_task, recovery)

        if self.allowed_task_types is None:
            task = self.store.claim_next_task(self.worker_id, self.lease_seconds)
        else:
            task = self.store.claim_next_task(
                self.worker_id, self.lease_seconds, self.allowed_task_types
            )
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
        claimed_checkpoint = task.get("checkpoint")
        if isinstance(claimed_checkpoint, dict):
            claimed_state = claimed_checkpoint.get("task_state")
            if isinstance(claimed_state, dict) and claimed_state.get("stage") == "council_resume_ready":
                try:
                    context._require_council_resume(claimed_checkpoint)
                except ValueError:
                    blocked = self.store.block_task(
                        task_id, self.worker_id, "invalid_council_resume_checkpoint"
                    )
                    return {
                        "status": "blocked" if blocked else "lease_lost",
                        "task_id": task_id,
                        "reason": "invalid_council_resume_checkpoint",
                        "recovery": recovery,
                    }
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

        if decision.outcome == "suspended":
            return {"status": "waiting_council", "task_id": task_id, "recovery": recovery}

        if decision.outcome == "completed":
            if context._council_resume_required:
                try:
                    latest = context.load_latest_checkpoint()
                except Exception:
                    state = self.store.fail_task(
                        task_id, self.worker_id,
                        "council_resume_checkpoint_unavailable",
                        retry_delay_seconds=90,
                    )
                    return {
                        "status": state or "lease_lost",
                        "task_id": task_id,
                        "reason": "council_resume_checkpoint_unavailable",
                        "recovery": recovery,
                    }
                latest_state = latest.get("task_state") if isinstance(latest, dict) else None
                latest_resume = latest_state.get("council_resume") if isinstance(latest_state, dict) else None
                if (
                    not context._council_resume_loaded
                    or not isinstance(latest_state, dict)
                    or latest_state.get("stage") == "council_resume_ready"
                    or not isinstance(latest_resume, dict)
                    or latest_resume.get("request_id") != context._council_resume_expected_request_id
                ):
                    blocked = self.store.block_task(
                        task_id, self.worker_id, "council_resume_not_checkpointed"
                    )
                    return {
                        "status": "blocked" if blocked else "lease_lost",
                        "task_id": task_id,
                        "reason": "council_resume_not_checkpointed",
                        "recovery": recovery,
                    }
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

    def _reconcile_once(self, task: dict, recovery: dict) -> dict:
        task_id = task.get("task_id")
        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id < 1:
            raise RuntimeError("claimed reconciliation task has an invalid task_id")
        context = TaskContext(
            store=self.store,
            task_id=task_id,
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        try:
            unknown = self.store.list_unknown_provider_requests(
                task_id, self.worker_id, self.lease_seconds
            )
            recovered = self.store.list_recovered_provider_results(
                task_id, self.worker_id, self.lease_seconds
            )
            decisions = self.reconciliation_handler(task, unknown, recovered, context)
            if not isinstance(decisions, Sequence) or isinstance(decisions, (str, bytes)):
                raise TypeError("reconciliation_handler_must_return_a_sequence")
            allowed_ids = {item.get("reservation_id") for item in unknown}
            seen_ids = set()
            for decision in decisions:
                if not isinstance(decision, ProviderReconciliationDecision):
                    raise TypeError("invalid_reconciliation_decision")
                if decision.reservation_id not in allowed_ids:
                    raise ValueError("decision references a reservation outside the unknown set")
                if decision.reservation_id in seen_ids:
                    raise ValueError("duplicate reconciliation decision")
                seen_ids.add(decision.reservation_id)

            remaining = len(unknown)
            for decision in decisions:
                result = self.store.resolve_unknown_provider_request(
                    task_id,
                    self.worker_id,
                    decision.reservation_id,
                    outcome=decision.outcome,
                    evidence_ref=decision.evidence_ref,
                    provider_result_ref=decision.provider_result_ref,
                    input_tokens_actual=decision.input_tokens_actual,
                    output_tokens_actual=decision.output_tokens_actual,
                    actual_cost_usd=decision.actual_cost_usd,
                    provider_request_id=decision.provider_request_id,
                    lease_seconds=self.lease_seconds,
                )
                remaining = result["remaining_unknown_requests"]

            if remaining == 0 and decisions:
                # The store atomically releases the lease and requeues the task
                # after its final unknown reservation is resolved.
                return {
                    "status": "reconciled",
                    "task_id": task_id,
                    "resolved_count": len(decisions),
                    "task_resumed": True,
                    "recovery": recovery,
                }

            released = self.store.block_task(
                task_id, self.worker_id, "reconciliation_evidence_incomplete"
                if decisions else "reconciliation_no_decision"
            )
            return {
                "status": "reconciliation_pending" if released else "lease_lost",
                "task_id": task_id,
                "resolved_count": len(decisions),
                "remaining_unknown_requests": remaining,
                "recovery": recovery,
            }
        except Exception as exc:
            # Never schedule a retry here: the provider may already have charged
            # the original request. Release the lease but preserve its blocked state.
            released = self.store.block_task(
                task_id, self.worker_id, "reconciliation_handler_error"
            )
            return {
                "status": "reconciliation_pending" if released else "lease_lost",
                "task_id": task_id,
                "reason": "reconciliation_handler_error",
                "error_type": type(exc).__name__,
                "recovery": recovery,
            }
