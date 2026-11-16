"""Artificial Muscle Engineering discipline-pack public contracts.

This package currently exposes actuator-to-material request contracts only;
no actuator constitutive solver or performance predictor is implied.
"""
from ..discipline_contracts import (
    ActuatorMaterialRequest,
    MaterialCandidateResponse,
    PropertyConstraint,
)

ARTIFICIAL_MUSCLE_PACK_ID = "artificial-muscle-engineering"
ARTIFICIAL_MUSCLE_PACK_VERSION = "0.1.0"

__all__ = [
    "ARTIFICIAL_MUSCLE_PACK_ID", "ARTIFICIAL_MUSCLE_PACK_VERSION",
    "ActuatorMaterialRequest", "MaterialCandidateResponse", "PropertyConstraint",
]
