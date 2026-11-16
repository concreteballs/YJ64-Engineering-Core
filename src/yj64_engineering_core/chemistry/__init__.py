"""Chemistry & Molecular Design discipline-pack public API.

The current executable capability is evidence-aware formulation screening;
it does not generate molecules or predict chemistry from first principles.
"""
from ..discipline_contracts import (
    CompositionComponent, MaterialCandidate, MaterialCandidateResponse,
    MicrostructureDescriptor, PropertyConstraint,
)
from .screening import (
    CandidateScreeningResult, ChemistryCandidate, ChemistryScreeningEngine,
    ChemistryScreeningReport, StimulusResponseEvidence,
)

CHEMISTRY_PACK_ID = "chemistry-molecular-design"
CHEMISTRY_PACK_VERSION = "0.2.0"

__all__ = [
    "CHEMISTRY_PACK_ID", "CHEMISTRY_PACK_VERSION", "CompositionComponent",
    "MaterialCandidate", "MaterialCandidateResponse", "MicrostructureDescriptor",
    "PropertyConstraint", "CandidateScreeningResult", "ChemistryCandidate",
    "ChemistryScreeningEngine", "ChemistryScreeningReport", "StimulusResponseEvidence",
]
