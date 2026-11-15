"""Coefficient-based aerodynamic screening solver."""
from __future__ import annotations

from ..models import AnalysisRequest, AnalysisResult
from .flow import coefficient_flow_result


class AerodynamicsSolver:
    """Estimate steady aerodynamic forces from supplied force coefficients.

    This is suitable for preliminary sail/rig force bookkeeping only. It does
    not calculate sail coefficients, wind fields, mast interaction, or CFD.
    """

    name = "YJ64 coefficient-based aerodynamics"
    version = "0.1.0"

    def supports(self, analysis_type: str) -> bool:
        return analysis_type == "aerodynamics.coefficient_forces"

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        if not self.supports(request.analysis_type):
            raise ValueError(f"Unsupported analysis type: {request.analysis_type}")
        return coefficient_flow_result(
            request,
            analysis_type=request.analysis_type,
            method="steady_incompressible_coefficient_force_screening",
            solver_name=self.name,
            limitations=[
                "No sail-shape or airfoil-polar calculation; lift, drag and side-force coefficients must be supplied.",
                "No apparent-wind iteration, sail interaction, mast/rig interference, aeroelasticity, gust response, or trim optimisation.",
                "No compressibility correction; intended for low-speed marine aerodynamics.",
            ],
        )
