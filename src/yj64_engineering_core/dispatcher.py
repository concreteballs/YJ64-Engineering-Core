"""Explicit dispatcher for engineering requests and backend adapters.

The dispatcher never guesses which operation to run. Callers must choose
"physics.<analysis_type>" or "cad.generate" explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import EngineeringRequest, EngineeringResponse, SolverProvenance
from .interfaces import CADBackend, PhysicsSolver
from .models import AnalysisRequest, MaterialProperties
from .physics.statics import calculate_axial_member


@dataclass(frozen=True)
class DispatchResult:
    operation: str
    response: EngineeringResponse


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
        response = EngineeringResponse(
            request_id=request.request_id,
            status="completed",
            provenance=SolverProvenance(
                solver_name=getattr(backend, "name", backend_name),
                solver_version=getattr(backend, "version", "unspecified"),
                method="cad_backend_generation",
            ),
            values={"artifact_count": 1},
            units={"artifact_count": "count"},
            assumptions=request.assumptions,
            warnings=tuple(artifact.get("warnings", ())),
            limitations=tuple(artifact.get("limitations", ())),
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
            ),
            values=result.values,
            units=result.units,
            assumptions=tuple(result.assumptions),
            warnings=tuple(result.warnings),
            limitations=tuple(result.limitations),
        )
        return DispatchResult(operation=f"physics.{analysis_type}", response=response)

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
