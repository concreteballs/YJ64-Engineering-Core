# YJ64 Engineering Core

A modular engineering service for the YJ64 multi-agent system. The first real design workflow is a parametric yacht hull: generate technical views and editable 3D geometry, revise it from structured instructions or visual markup, and preserve traceable revisions.

## Current architecture

- **Versioned engineering contracts** — canonical JSON requests and responses using SI units.
- **Dispatcher and pipeline** — explicit routing; CAD-only iteration is supported before a physics model exists.
- **Parametric yacht hull** — longitudinal stations define the outer hull envelope in X/Y/Z.
- **2D technical drawing** — SVG with plan, profile and transverse section views.
- **3D CAD source** — editable OpenSCAD polyhedron and a generated FreeCAD macro for a parametric loft.
- **3D mesh rendering** — optional real OpenSCAD execution exports STL; the CI integration test runs this when OpenSCAD is installed.
- **Visual reference intake** — PNG/JPEG ingestion, SHA-256 identity, normalized user annotations and structured observations from a vision-capable model.
- **Controlled design edits** — a whitelist of parameter changes returns before/after geometry and a change record.
- **Physics adapters** — analytical axial screening and a narrow CalculiX T3D2 axial-truss test case.

## Yacht hull geometry

The first hull model is a **single-hull outer envelope**. Each longitudinal station contains:

- x_m — longitudinal position;
- half_beam_m — half breadth;
- keel_z_m — keel/centreline height;
- chine_z_m — chine height;
- deck_z_m — sheer/deck-edge height.

The station sequence is interpolated into a closed 3D surface. The current section profile is a deliberately simple five-point chine section. It is a useful editable envelope for design iteration, not a complete naval-architecture model.

### Generate 2D and 3D artifacts

    from pathlib import Path
    from yj64_engineering_core import (
        EngineeringDispatcher,
        EngineeringPipeline,
        EngineeringRequest,
        GeometrySpec,
        YachtHullCADBackend,
    )

    hull_parameters = {
        "name": "Prototype mono-hull",
        "chine_fraction": 0.72,
        "stations": [
            {"x_m": 0.0, "half_beam_m": 0.025,
             "keel_z_m": -0.35, "chine_z_m": -0.10, "deck_z_m": 0.45},
            {"x_m": 1.0, "half_beam_m": 0.55,
             "keel_z_m": -0.55, "chine_z_m": -0.22, "deck_z_m": 0.65},
            {"x_m": 3.0, "half_beam_m": 0.90,
             "keel_z_m": -0.62, "chine_z_m": -0.24, "deck_z_m": 0.72},
            {"x_m": 5.0, "half_beam_m": 0.70,
             "keel_z_m": -0.50, "chine_z_m": -0.18, "deck_z_m": 0.68},
            {"x_m": 6.0, "half_beam_m": 0.025,
             "keel_z_m": -0.30, "chine_z_m": -0.08, "deck_z_m": 0.40},
        ],
    }

    dispatcher = EngineeringDispatcher()
    dispatcher.register_cad_backend(
        "yacht_hull",
        YachtHullCADBackend(Path("./hull-artifacts")),
    )
    request = EngineeringRequest(
        request_id="hull-001",
        title="Prototype yacht hull",
        objective="Create a preliminary hull technical drawing and editable 3D CAD",
        geometry=GeometrySpec("yacht_hull", hull_parameters),
        operating_conditions={"cad_backend": "yacht_hull"},
    )
    result = EngineeringPipeline(dispatcher).run(request)
    print(result.to_json())

The default backend creates:
- hull-001.svg — plan, profile and three transverse sections;
- hull-001.scad — editable 3D OpenSCAD source;
- hull-001.FCMacro — FreeCAD macro that creates a loft and, when deliberately run in FreeCAD, exports FCStd, STEP and STL.

To also render an STL directly in the backend, pass the installed OpenSCAD executable and render_stl=True. The CI workflow installs OpenSCAD and exercises a real render-to-STL integration test.

## Iteration from words and drawings

A language model should translate the user's natural-language request into the structured, whitelisted operations accepted by apply_hull_changes. It must not write or execute arbitrary Python.

Supported operations currently include:
- set_station: change one station's half_beam_m, keel_z_m, chine_z_m, deck_z_m or x_m;
- scale_beam: scale all station half-beams;
- translate_vertical: move keel, chine and deck heights together;
- rename: change the design name.

Each edit returns the new validated hull plus a before/after change record. Regenerating the CAD artifacts from the new parameter set creates the next design revision.

For visual correction, ingest_reference_image accepts PNG/JPEG files and records their dimensions, SHA-256 digest and URI. ImageAnnotation stores normalized points/markup. A vision-capable model can inspect the uploaded drawing and provide VisualObservation records with image regions, descriptions, confidence and candidate station references. Only explicit, validated annotation-to-parameter mappings are converted into geometry edits by visual_changes. The image parser itself does not claim to understand the picture; semantic interpretation is the responsibility of the connected vision model.

## Current engineering boundary

The present hull is geometry, not a certified design:
- no internal frames, stringers, bulkheads, laminate schedule, plate thickness or scantlings;
- no hydrostatics, stability, resistance, slamming or fatigue model;
- no hull-specific shell/solid FEM yet;
- no verified CAD-to-mesh-to-FEM handoff yet.

The existing CalculiX adapter only validates a single axial T3D2 truss element. It must **not** be used to claim that the yacht hull has been structurally calculated. The next engineering milestone is a hull-specific mesh and shell-FEM workflow with explicit material thickness, boundary conditions, load cases, mesh-quality checks and solver convergence evidence.

The first hull profile is monohull. Catamaran/multihull assembly, appendages, foils and interior structure are planned after the single-hull geometry and revision workflow are tested.

## Data exchange and safety

- STEP for solid CAD exchange;
- DXF/SVG for 2D drawing exchange;
- STL for rendered mesh exchange;
- versioned JSON for design parameters, edits, observations and results.

Generated geometry is not proof of physical safety. Every calculation must identify its method, inputs, assumptions, units, warnings and limitations. External CAD/solver processes must run with bounded time and resources in an isolated worker. Safety-critical designs require independent engineering review and physical validation.

## Development

Python 3.11 or newer.

    python -m pip install -e .
    python -m unittest discover -s tests -v

GitHub Actions installs CalculiX and OpenSCAD, then runs unit tests, a real axial FEM test, and a real yacht-hull STL rendering test.
