"""Explicit bridge from generic parent tasks to the existing engineering dispatcher."""
from __future__ import annotations

from typing import Any

from ..contracts import EngineeringRequest
from ..dispatcher import EngineeringDispatcher
from ..task_contracts import TaskRequest
from .checkpoints import create_checkpoint
from .parent_tasks import ParentTaskState
from .worker import TaskExecutionResult


class EngineeringDispatcherTaskAdapter:
    """Run one explicitly selected physics/CAD operation through existing adapters.

    The generic task envelope must contain:
      input_data.operation: an explicit EngineeringDispatcher operation
      input_data.engineering_request: an EngineeringRequest dictionary

    No solver or CAD backend is selected here. The supplied dispatcher must
    already contain the concrete backends registered by the deployment.
    """

    def __init__(self, dispatcher: EngineeringDispatcher) -> None:
        if not isinstance(dispatcher, EngineeringDispatcher):
            raise TypeError("dispatcher must be an EngineeringDispatcher")
        self.dispatcher = dispatcher

    def __call__(
        self,
        request: TaskRequest,
        state: ParentTaskState,
        context: Any,
    ) -> TaskExecutionResult:
        if state.stage == "council_result_received":
            return TaskExecutionResult("blocked", "engineering_adapter_cannot_consume_council_result")
        try:
            operation = request.input_data.get("operation")
            engineering_data = request.input_data.get("engineering_request")
            if not isinstance(operation, str) or not operation.strip():
                return TaskExecutionResult("blocked", "engineering_operation_required")
            if not isinstance(engineering_data, dict):
                return TaskExecutionResult("blocked", "engineering_request_required")
            engineering_request = EngineeringRequest.from_dict(engineering_data)
            if engineering_request.request_id != request.task_id:
                return TaskExecutionResult("blocked", "engineering_request_id_mismatch")
            dispatched = self.dispatcher.dispatch(engineering_request, operation)
            response = dispatched.response.to_dict()
            previous = context.load_latest_checkpoint()
            sequence = int(previous.get("sequence", 0)) + 1 if isinstance(previous, dict) else 1
            previous_hash = previous.get("checkpoint_hash") if isinstance(previous, dict) else None
            artifact_refs = list(state.artifact_refs)
            for artifact in response.get("artifacts", []):
                uri = artifact.get("uri")
                if isinstance(uri, str) and uri not in artifact_refs:
                    artifact_refs.append(uri)
            checkpoint = create_checkpoint(
                task_id=str(context.task_id),
                sequence=sequence,
                state="completed",
                task_spec_version=request.contract_version,
                task_state={
                    "stage": "engineering_execution_completed",
                    "task_type": request.task_type,
                    "operation": dispatched.operation,
                    "engineering_request_id": engineering_request.request_id,
                    "engineering_response": response,
                    "resume_state": dict(state.resume_state),
                },
                budgets=dict(request.constraints),
                approvals=dict(request.approval_policy),
                artifact_refs=artifact_refs,
                previous_checkpoint_hash=previous_hash,
            )
            if not context.save_checkpoint(checkpoint):
                return TaskExecutionResult("retry", "engineering_result_checkpoint_failed", 90)
            return TaskExecutionResult("completed")
        except (TypeError, ValueError, KeyError):
            return TaskExecutionResult("blocked", "invalid_engineering_task_input")
        except LookupError:
            return TaskExecutionResult("blocked", "engineering_backend_not_registered")
        except (OSError, RuntimeError):
            return TaskExecutionResult("retry", "engineering_backend_unavailable", 90)
