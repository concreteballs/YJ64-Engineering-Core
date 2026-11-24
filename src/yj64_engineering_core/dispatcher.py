"""Explicit dispatcher for engineering requests and backend adapters.

The dispatcher never guesses which operation to run. Callers must choose
"physics.<analysis_type>" or "cad.generate" explicitly. Council-derived
operations additionally require an externally verified approval and an
explicitly registered typed handler; this class does not create a task loop.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .automation.executor_intent import (
    SUPPORTED_EXECUTOR_OPERATIONS,
    build_executor_intent,
)
from .contracts import ArtifactReference, EngineeringRequest, EngineeringResponse, SolverProvenance
from .interfaces import CADBackend, PhysicsSolver
from .models import AnalysisRequest, MaterialProperties
from .physics.statics import calculate_axial_member


@dataclass(frozen=True)
class DispatchResult:
    operation: str
    response: EngineeringResponse


@dataclass(frozen=True)
class ApprovedIntentDispatchResult:
    operation: str
    intent: dict[str, Any]
    result: dict[str, Any]


class AxialMemberSolver:
    """Adapter exposing the built-in axial screening calculation as a plugin."""

    name = "YJ64 reference statics solver"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "axial_member"

    def solve(self, request: AnalysisRequest):
        if request.analysis_type != "axial_member":
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        p = request.parameters
        required = ("force_n", "area_m2", "length_m", "material")
        missing = [key for key in required if key not in p]
        if missing:
            raise ValueError(f"Missing axial_member parameters: {', '.join(missing)}")
        material_data = p["material"]
        material = (
            material_data
            if isinstance(material_data, MaterialProperties)
            else MaterialProperties(**material_data)
        )
        return calculate_axial_member(
            force_n=p["force_n"],
            area_m2=p["area_m2"],
            length_m=p["length_m"],
            material=material,
        )


class EngineeringDispatcher:
    """Routes validated requests to explicitly registered backends."""

    def __init__(self) -> None:
        self._physics_solvers: list[PhysicsSolver] = []
        self._cad_backends: dict[str, CADBackend] = {}
        self._approved_intent_handlers: dict[
            str, Callable[[Mapping[str, Any], Any], Mapping[str, Any]]
        ] = {}

    def register_physics_solver(self, solver: PhysicsSolver) -> None:
        if not callable(getattr(solver, "supports", None)) or not callable(
            getattr(solver, "solve", None)
        ):
            raise TypeError("Physics solver must implement supports() and solve()")
        if not getattr(solver, "name", None) or not getattr(solver, "version", None):
            raise ValueError("Physics solver must declare name and version")
        self._physics_solvers.append(solver)

    def register_cad_backend(self, name: str, backend: CADBackend) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("CAD backend name must be non-empty")
        if not callable(getattr(backend, "generate", None)):
            raise TypeError("CAD backend must implement generate()")
        self._cad_backends[name] = backend

    def register_approved_intent_handler(
        self,
        operation: str,
        handler: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    ) -> None:
        """Register trusted code for one fixed operation; never register model text."""
        if operation not in SUPPORTED_EXECUTOR_OPERATIONS:
            raise ValueError("unsupported_approved_intent_operation")
        if not callable(handler):
            raise TypeError("approved intent handler must be callable")
        if operation in self._approved_intent_handlers:
            raise ValueError("approved_intent_handler_already_registered")
        self._approved_intent_handlers[operation] = handler

    def dispatch_approved_intent(
        self,
        *,
        decision_policy: Mapping[str, Any],
        approval: Mapping[str, Any],
        task_id: str,
        permission_snapshot_digest: str,
        verify_approval: Callable[[Mapping[str, Any]], bool],
        execution_context: Any,
    ) -> ApprovedIntentDispatchResult:
        """Invoke only a registered typed handler after task-scoped approval.

        The context must be the active parent TaskContext for the same task.
        It is passed to trusted handler code so that continuation state can be
        checkpointed by the existing worker. This method creates no queue,
        worker, scheduler, or independent engineering cycle.
        """
        if execution_context is None:
            raise ValueError("approved_intent_execution_context_required")
        if str(getattr(execution_context, "task_id", None)) != str(task_id):
            raise ValueError("approved_intent_context_task_mismatch")
        if not callable(getattr(execution_context, "load_latest_checkpoint", None)) or not callable(
            getattr(execution_context, "save_checkpoint", None)
        ):
            raise TypeError("approved_intent_requires_parent_task_context")

        intent = build_executor_intent(
            decision_policy=decision_policy,
            approval=approval,
            task_id=task_id,
            permission_snapshot_digest=permission_snapshot_digest,
            verify_approval=verify_approval,
        )
        handler = self._approved_intent_handlers.get(intent["operation"])
        if handler is None:
            raise LookupError("no_approved_intent_handler_registered")

        handler_intent = json.loads(json.dumps(
            intent, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ))
        result = handler(handler_intent, execution_context)
        if not isinstance(result, Mapping):
            raise TypeError("approved_intent_handler_must_return_object")
        try:
            result_snapshot = json.loads(json.dumps(
                dict(result), sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ))
        except (TypeError, ValueError):
            raise ValueError("approved_intent_handler_result_must_be_finite_json") from None
        return ApprovedIntentDispatchResult(
            operation=intent["operation"],
            intent=intent,
            result=result_snapshot,
        )

    def dispatch(self, request: EngineeringRequest, operation: str) -> DispatchResult:
        if not isinstance(request, EngineeringRequest):
            raise TypeError("request must be an EngineeringRequest")
        if not isinstance(operation, str) or not operation.strip():
            raise ValueError("operation must be explicit and non-empty")
        if operation == "cad.generate":
            return self._dispatch_cad(request)
        if operation.startswith("physics."):
            analysis_type = operation.removeprefix("physics.")
            if not analysis_type:
                raise ValueError("Physics operation must include an analysis type")
            return self._dispatch_physics(request, analysis_type)
        raise ValueError(f"Unsupported operation: {operation}")

    def _dispatch_cad(self, request: EngineeringRequest) -> DispatchResult:
        if request.geometry is None:
            raise ValueError("CAD generation requires request.geometry")
        backend_name = request.operating_conditions.get("cad_backend")
        if not backend_name:
            raise ValueError("Set operating_conditions.cad_backend explicitly")
        backend = self._cad_backends.get(backend_name)
        if backend is None:
            raise LookupError(f"CAD backend is not registered: {backend_name}")
        specification = {
            "geometry_type": request.geometry.geometry_type,
            "parameters": request.geometry.parameters,
            "coordinate_system": request.geometry.coordinate_system,
            "material": request.material,
            "request_id": request.request_id,
        }
        artifact = backend.generate(specification)
        if not isinstance(artifact, dict):
            raise TypeError("CAD backend must return an artifact metadata object")
        artifact_items = artifact.get("artifacts")
        if artifact_items is None:
            artifact_items = (
                [{"format": artifact["format"], "location": artifact["location"],
                  "sha256": artifact.get("sha256")}]
                if artifact.get("location") and artifact.get("format")
                else []
            )
        artifact_references = tuple(
            ArtifactReference(
                artifact_id=f"{request.request_id}-cad-{index + 1}",
                media_type=item["format"],
                uri=item["location"],
                sha256=item.get("sha256"),
            )
            for index, item in enumerate(artifact_items)
            if item.get("format") and item.get("location")
        )
        response = EngineeringResponse(
            request_id=request.request_id,
            status="completed",
            provenance=SolverProvenance(
                solver_name=getattr(backend, "name", backend_name),
                solver_version=getattr(backend, "version", "unspecified"),
                method="cad_backend_generation",
                input_digest_sha256=self._input_digest(request, "cad.generate"),
            ),
            values={"artifact_count": len(artifact_references)},
            units={"artifact_count": "count"},
            assumptions=request.assumptions,
            warnings=tuple(artifact.get("warnings", ())),
            limitations=tuple(artifact.get("limitations", ())),
            artifacts=artifact_references,
        )
        return DispatchResult(operation="cad.generate", response=response)

    def _dispatch_physics(
        self, request: EngineeringRequest, analysis_type: str
    ) -> DispatchResult:
        solver = next(
            (item for item in self._physics_solvers if item.supports(analysis_type)),
            None,
        )
        if solver is None:
            raise LookupError(f"No registered solver supports: {analysis_type}")
        if analysis_type == "axial_member":
            parameters = self._axial_parameters(request)
        elif analysis_type == "axial_truss_fem":
            parameters = self._axial_truss_parameters(request)
        else:
            parameters = {
                "geometry": (
                    {
                        "geometry_type": request.geometry.geometry_type,
                        **request.geometry.parameters,
                    }
                    if request.geometry
                    else None
                ),
                "material": request.material,
                "load_cases": [
                    {
                        "name": case.name,
                        "force_n": case.force_n,
                        "moment_nm": case.moment_nm,
                    }
                    for case in request.load_cases
                ],
                "operating_conditions": request.operating_conditions,
            }
        result = solver.solve(
            AnalysisRequest(
                analysis_type=analysis_type,
                parameters=parameters,
                assumptions=request.assumptions,
            )
        )
        response = EngineeringResponse(
            request_id=request.request_id,
            status=result.status,
            provenance=SolverProvenance(
                solver_name=result.solver_name or solver.name,
                solver_version=result.solver_version or solver.version,
                method=result.method,
                input_digest_sha256=self._input_digest(
                    request, f"physics.{analysis_type}"
                ),
            ),
            values=result.values,
            units=result.units,
            assumptions=tuple(result.assumptions),
            warnings=tuple(result.warnings),
            limitations=tuple(result.limitations),
        )
        return DispatchResult(operation=f"physics.{analysis_type}", response=response)

    @staticmethod
    def _input_digest(request: EngineeringRequest, operation: str) -> str:
        """Bind a result to the exact canonical request and selected operation."""
        payload = f"{operation}\\n{request.to_json()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _axial_parameters(request: EngineeringRequest) -> dict[str, Any]:
        if request.geometry is None:
            raise ValueError("axial_member requires geometry")
        geometry = request.geometry.parameters
        for key in ("area_m2", "length_m"):
            if key not in geometry:
                raise ValueError(f"axial_member geometry requires {key}")
        material = dict(request.material)
        required_material = ("name", "youngs_modulus_pa", "allowable_stress_pa")
        missing = [key for key in required_material if key not in material]
        if missing:
            raise ValueError(f"Missing material fields: {', '.join(missing)}")
        if len(request.load_cases) != 1:
            raise ValueError("axial_member requires exactly one load case")
        force_x, force_y, force_z = request.load_cases[0].force_n
        if force_x != 0 or force_y != 0:
            raise ValueError("axial_member adapter supports only Z-axis axial force")
        if any(request.load_cases[0].moment_nm):
            raise ValueError("axial_member adapter does not support applied moments")
        return {
            "force_n": force_z,
            "area_m2": geometry["area_m2"],
            "length_m": geometry["length_m"],
            "material": material,
        }

    @staticmethod
    def _axial_truss_parameters(request: EngineeringRequest) -> dict[str, Any]:
        """Map the shared request into the constrained CalculiX T3D2 case."""
        if request.geometry is None:
            raise ValueError("axial_truss_fem requires geometry")
        geometry = request.geometry.parameters
        for key in ("area_m2", "length_m"):
            if key not in geometry:
                raise ValueError(f"axial_truss_fem geometry requires {key}")
        material = dict(request.material)
        required_material = ("name", "youngs_modulus_pa", "poisson_ratio")
        missing = [key for key in required_material if key not in material]
        if missing:
            raise ValueError(
                f"axial_truss_fem material requires: {', '.join(missing)}"
            )
        if len(request.load_cases) != 1:
            raise ValueError("axial_truss_fem requires exactly one load case")
        force_x, force_y, force_z = request.load_cases[0].force_n
        if force_x != 0 or force_y != 0:
            raise ValueError("axial_truss_fem supports only Z-axis axial force")
        if any(request.load_cases[0].moment_nm):
            raise ValueError("axial_truss_fem does not support applied moments")
        return {
            "request_id": request.request_id,
            "force_n": force_z,
            "area_m2": geometry["area_m2"],
            "length_m": geometry["length_m"],
            "material": {
                "name": material["name"],
                "youngs_modulus_pa": material["youngs_modulus_pa"],
                "poisson_ratio": material["poisson_ratio"],
            },
        }
