"""Run independent CAD and physics branches for one engineering request.

The pipeline shares the same validated request with both branches. It does not
claim that physics consumes geometry exported by CAD; both branches currently
interpret the request independently.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .contracts import EngineeringRequest
from .dispatcher import DispatchResult, EngineeringDispatcher


@dataclass(frozen=True)
class PipelineBranch:
    """Outcome of one independently executed branch."""

    operation: str
    execution_status: str
    result: DispatchResult | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "execution_status": self.execution_status,
            "result": (
                self.result.response.to_dict() if self.result is not None else None
            ),
            "error": (
                {
                    "type": self.error_type,
                    "message": self.error_message,
                }
                if self.error_type is not None
                else None
            ),
        }


@dataclass(frozen=True)
class PipelineResult:
    """Combined result with independent outcomes for CAD and physics."""

    request_id: str
    status: str
    branches: dict[str, PipelineBranch]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "branches": {
                name: branch.to_dict() for name, branch in self.branches.items()
            },
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        )


class EngineeringPipeline:
    """Execute CAD and physics without allowing one branch to suppress the other."""

    def __init__(self, dispatcher: EngineeringDispatcher) -> None:
        if not isinstance(dispatcher, EngineeringDispatcher):
            raise TypeError("dispatcher must be an EngineeringDispatcher")
        self.dispatcher = dispatcher

    def run(
        self,
        request: EngineeringRequest,
        physics_operation: str | None = None,
        cad_operation: str = "cad.generate",
    ) -> PipelineResult:
        if not isinstance(request, EngineeringRequest):
            raise TypeError("request must be an EngineeringRequest")
        if physics_operation is not None and (
            not isinstance(physics_operation, str)
            or not physics_operation.startswith("physics.")
        ):
            raise ValueError("physics_operation must be None or start with 'physics.'")
        if cad_operation != "cad.generate":
            raise ValueError("cad_operation must be 'cad.generate'")

        # Deliberately execute both branches even if the first one raises.
        branches = {}
        if physics_operation is not None:
            branches["physics"] = self._execute(request, physics_operation)
        branches["cad"] = self._execute(request, cad_operation)
        successful = sum(
            branch.execution_status == "completed" for branch in branches.values()
        )
        if successful == len(branches):
            status = "completed"
        elif successful:
            status = "partial"
        else:
            status = "failed"
        return PipelineResult(
            request_id=request.request_id,
            status=status,
            branches=branches,
        )

    def _execute(self, request: EngineeringRequest, operation: str) -> PipelineBranch:
        try:
            result = self.dispatcher.dispatch(request, operation)
        except Exception as exc:
            return PipelineBranch(
                operation=operation,
                execution_status="error",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        return PipelineBranch(
            operation=operation,
            execution_status="completed",
            result=result,
        )
