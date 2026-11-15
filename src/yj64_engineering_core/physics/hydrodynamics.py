"""Coefficient-based hydrodynamic screening solver."""
from __future__ import annotations

from ..models import AnalysisRequest, AnalysisResult
from .flow import coefficient_flow_result


class HydrodynamicsSolver:
    """Estimate steady hydrodynamic forces from supplied force coefficients.

    Can represent a foil or a wetted body only when the user supplies
    appropriate reference area and coefficients. It is not a hull-resistance
    or free-surface CFD solver.
    """

    name = "YJ64 coefficient-based hydrodynamics"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "hydrodynamics.coefficient_forces"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        return coefficient_flow_result(
            request,
            analysis_type=request.analysis_type,
            method="steady_incompressible_coefficient_force_screening",
            solver_name=self.name,
            limitations=[
                "No prediction of lift/drag coefficients; coefficients must come from validated data, tests, or a separate analysis.",
                "No free-surface wave-making, viscous boundary-layer resolution, hull interference, ventilation, cavitation, or unsteady foil dynamics.",
                "No hydrostatic restoring forces, seakeeping, slamming, or manoeuvring model.",
            ],
        )
