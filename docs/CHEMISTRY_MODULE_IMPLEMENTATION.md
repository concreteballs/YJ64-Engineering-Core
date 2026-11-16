# Chemistry & Molecular Design — first executable screening layer

## Implemented capability

The yj64_engineering_core.chemistry package now includes an evidence-aware formulation screening workflow:

- ChemistryCandidate binds a versioned shared MaterialCandidate formulation to the shared MaterialRecord identity and optional stimulus-response evidence.
- StimulusResponseEvidence explicitly distinguishes electric, magnetic and hybrid electric-plus-magnetic response. Hybrid evidence must contain both field inputs in the same test record; separate electric and magnetic records are not silently combined.
- ChemistryScreeningEngine accepts an ActuatorMaterialRequest, evaluates supplied material-property evidence against the requested limits, and classifies each formulation as candidate, rejected or unresolved.
- ChemistryScreeningReport.to_contract_response() converts accepted formulations into the existing cross-discipline response contract.

## Input conventions

All field values are SI:

| Input | Unit |
|---|---|
| Electric field | V/m |
| Magnetic flux density | T |
| Magnetic field strength | A/m |
| Contraction strain | fraction of original gauge length |
| Blocked stress | Pa |
| Response time | s |
| Temperature range | K |

Material property evidence must use the exact requested unit in this first version. No implicit conversion is performed. If multiple evidence records exist for the same property and unit, the result is unresolved until test conditions can be selected explicitly.

Each non-hypothesis stimulus response requires source references. hypothesis may be recorded without a source, but it remains clearly labelled and produces a warning. Reversibility and test conditions are also surfaced as warnings rather than assumed.

## Minimal use

```python
from yj64_engineering_core.chemistry import ChemistryScreeningEngine
from yj64_engineering_core.discipline_contracts import ActuatorMaterialRequest

report = ChemistryScreeningEngine().screen(request, candidate_records)
for result in report.results:
    print(result.candidate_id, result.disposition, result.unresolved_constraints)
```

request is an ActuatorMaterialRequest; candidate_records is a sequence of ChemistryCandidate objects. The exact composition, material property records and stimulus-response evidence must be supplied by the researcher or an upstream data source.

## Electrical and magnetic design boundary

The chemistry pack can record and screen three distinct response classes:

1. Electric-field response — an explicitly recorded electric field and measured/reported contraction response.
2. Magnetic-field response — an explicitly recorded magnetic flux density or magnetic field strength and response.
3. Hybrid response — electric and magnetic fields applied together in one evidence record.

A magnetorheological change in stiffness is not treated as contraction unless contraction strain and blocked stress are separately supplied. No default field strength, strain, stress, cycle life, conductivity, dielectric strength or thermal limit is invented.

## Current limitations

This is a deterministic formulation/evidence screening engine, not a molecular structure generator, reaction predictor, quantum-chemistry engine, molecular-dynamics solver, polymerization simulator or multiphysics material predictor. It does not optimize chemistry or infer synthesis routes. It cannot establish whether a proposed formulation is safe, manufacturable, stable or experimentally real.

The next increments are: explicit condition filtering and unit normalization through the shared quantity registry; candidate formulation authoring helpers; optional structure-file adapters; mechanism-specific chemistry/property adapters; and experiment-data ingestion with uncertainty handling. External scientific tools remain optional adapters and are not installed or claimed integrated.
