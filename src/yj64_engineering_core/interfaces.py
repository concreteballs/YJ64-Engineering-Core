"""Stable plugin contracts shared by the app, agents, and solver adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import AnalysisRequest, AnalysisResult


@runtime_checkable
class PhysicsSolver(Protocol):
    """A physics backend that accepts structured requests and returns provenance."""

    name: str
    version: str

    def supports(self, analysis_type: str) -> bool:
        """Return whether this solver handles the requested analysis type."""
        ...

    def solve(self, request: AnalysisRequest) -> AnalysisResult:
        """Run the analysis and return values, units, assumptions, and limitations."""
        ...


@runtime_checkable
class CADBackend(Protocol):
    """A CAD backend that creates editable engineering artifacts."""

    name: str
    version: str

    def supported_formats(self) -> tuple[str, ...]:
        """Return supported import/export formats."""
        ...

    def generate(self, specification: dict) -> dict:
        """Generate an artifact and return its format, location, and metadata.

        Implementations must validate specifications and must not execute
        arbitrary source code supplied by an LLM.
        """
        ...
