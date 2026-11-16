"""Chemistry & Molecular Design discipline-pack public contracts.

This package currently exposes data contracts only; no molecular generator,
reaction predictor or synthesis solver is claimed to be implemented.
"""
from ..discipline_contracts import (
    CompositionComponent,
    MaterialCandidate,
    MaterialCandidateResponse,
    MicrostructureDescriptor,
    PropertyConstraint,
)

CHEMISTRY_PACK_ID = "chemistry-molecular-design"
CHEMISTRY_PACK_VERSION = "0.1.0"

__all__ = [
    "CHEMISTRY_PACK_ID", "CHEMISTRY_PACK_VERSION", "CompositionComponent",
    "MaterialCandidate", "MaterialCandidateResponse", "MicrostructureDescriptor",
    "PropertyConstraint",
]
