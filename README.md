# YJ64 Engineering Core

A modular engineering service for the YJ64 multi-agent system. The first real design workflow is a parametric yacht hull: generate technical views and editable 3D geometry, revise it from structured instructions or visual markup, and preserve traceable revisions.

## Current architecture

- Versioned engineering contracts using SI units.
- Explicit dispatcher and pipeline; CAD-only iteration is supported.
- Parametric yacht hull with 2D SVG and editable OpenSCAD/FreeCAD outputs.
- Visual reference intake with image hashes, normalized markup and structured observations from a vision-capable model.
- Controlled geometry edits with before/after records.
- Physics plugins for axial structural screening, a narrow CalculiX T3D2 verification case, and first coefficient-based aerodynamic/hydrodynamic force screening.

## Preliminary aerodynamic and hydrodynamic layer

The core exposes two independently registerable physics plugins:

- AerodynamicsSolver — operation physics.aerodynamics.coefficient_forces.
- HydrodynamicsSolver — operation physics.hydrodynamics.coefficient_forces.

Both calculate dynamic pressure, lift, drag, side force and Reynolds number from SI inputs and explicitly supplied force coefficients. This provides a common calculation contract for early sail, foil and body-force bookkeeping.

Important boundary: these are low-order steady-flow screening models, not CFD. They do not predict sail/foil coefficients, hull resistance, free-surface waves, cavitation, ventilation, transient manoeuvres or foil-borne transition. Coefficients must come from validated polars, test data or an independently justified source. Results are labelled screening_only.

See docs/FLOW_ANALYSIS.md for the input contract and staged roadmap.

## Yacht hull geometry

The first hull model is a single-hull outer envelope. Each longitudinal station contains x_m, half_beam_m, keel_z_m, chine_z_m and deck_z_m, all in SI metres. The section profile is a deliberately simple five-point chine shape: useful for iteration, not a complete naval-architecture model.

### Generate 2D and 3D artifacts

    from pathlib import Path
    from yj64_engineering_core import EngineeringDispatcher, EngineeringPipeline, EngineeringRequest, GeometrySpec, YachtHullCADBackend

    hull_parameters = {
        "name": "Prototype mono-hull",
        "chine_fraction": 0.72,
        "stations": [
            {"x_m": 0.0, "half_beam_m": 0.025, "keel_z_m": -0.35, "chine_z_m": -0.10, "deck_z_m": 0.45},
            {"x_m": 1.0, "half_beam_m": 0.55, "keel_z_m": -0.55, "chine_z_m": -0.22, "deck_z_m": 0.65},
            {"x_m": 3.0, "half_beam_m": 0.90, "keel_z_m": -0.62, "chine_z_m": -0.24, "deck_z_m": 0.72},
            {"x_m": 5.0, "half_beam_m": 0.70, "keel_z_m": -0.50, "chine_z_m": -0.18, "deck_z_m": 0.68},
            {"x_m": 6.0, "half_beam_m": 0.025, "keel_z_m": -0.30, "chine_z_m": -0.08, "deck_z_m": 0.40},
        ],
    }
    dispatcher = EngineeringDispatcher()
    dispatcher.register_cad_backend("yacht_hull", YachtHullCADBackend(Path("./hull-artifacts")))
    request = EngineeringRequest(
        request_id="hull-001",
        title="Prototype yacht hull",
        objective="Create a preliminary hull technical drawing and editable 3D CAD",
        geometry=GeometrySpec("yacht_hull", hull_parameters),
        operating_conditions={"cad_backend": "yacht_hull"},
    )
    result = EngineeringPipeline(dispatcher).run(request)

The default backend creates SVG, editable OpenSCAD source and a FreeCAD loft macro. An optional OpenSCAD run exports STL.

## Iteration from words and drawings

A language model translates natural-language requests into whitelisted operations accepted by apply_hull_changes; it must not execute arbitrary Python. Supported operations include set_station, scale_beam, translate_vertical and rename. Each edit returns a validated hull and before/after change record.

For visual correction, ingest_reference_image records PNG/JPEG dimensions, SHA-256 and URI. A vision-capable model must interpret the image and return structured observations; the image parser itself does not claim semantic image recognition. Only explicit, validated annotation-to-parameter mappings become geometry edits.

## Current engineering boundary

The present hull is geometry, not a certified design:
- no internal frames, stringers, bulkheads, laminate schedule, plate thickness or scantlings;
- no hydrostatics, stability, resistance, slamming or fatigue model;
- no hull-specific shell/solid FEM or verified CAD-to-mesh-to-FEM handoff;
- no coupled sail–hull–foil equilibrium or time-domain foiling-transition simulation.

The existing CalculiX adapter only validates a single axial T3D2 truss element. It must not be used to claim that the yacht hull has been structurally calculated. The next milestones are validated aerodynamic/hydrodynamic coefficient sources, sail force and moment equilibrium, hull resistance/hydrostatics, foil analysis, coupled dynamics and then hull-specific shell FEM.

The first hull profile is monohull. Catamaran/multihull assembly, appendages, foils and interior structure remain future work.

## Data exchange and safety

STEP for solid CAD exchange; DXF/SVG for 2D drawings; STL for meshes; versioned JSON for design parameters, edits, observations and results.

Every calculation must identify its method, inputs, assumptions, units, warnings and limitations. External CAD/solver processes must run with bounded time and resources in an isolated worker. Safety-critical designs require independent engineering review and physical validation.

## Development

Python 3.11 or newer.

    python -m pip install -e .
    python -m unittest discover -s tests -v

GitHub Actions installs CalculiX and OpenSCAD, then runs unit tests, an axial FEM test and a real yacht-hull STL rendering test.
