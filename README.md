# YJ64 Engineering Core

A modular engineering service for the YJ64 multi-agent system.

Its purpose is to let language models, autonomous agents, and commercial agents work with structured engineering artifacts rather than relying on prose alone.

## Architecture

- **Versioned contracts** — canonical JSON requests and responses shared by agents and engineering services.
- **Dispatcher** — explicit routing to registered CAD and physics backends; operations are never guessed.
- **Engineering pipeline** — runs CAD and physics branches for the same request and preserves each branch's result or error independently.
- **Physics adapters** — a common interface for analytical solvers and external simulation engines.
- **CAD adapters** — workspace-bound OpenSCAD, FreeCAD macro, and SVG generators.
- **Validation and provenance** — SI units, finite numeric values, explicit assumptions, solver identity, warnings, limitations, and artifact references.

## Engineering rule

A generated drawing or 3D model is not proof that a design is physically safe. Analytical estimates, numerical simulations, and physical tests must be identified separately. Every result must state its method, assumptions, units, and limitations. Screening results are not certification.

## Current implementation

1. Versioned engineering request/response contracts (contracts.py).
2. Validation and JSON serialization for geometry, load cases, provenance, and artifact references.
3. Explicit engineering dispatcher (dispatcher.py).
4. Built-in dispatcher adapter for axial linear-elastic screening.
5. Workspace-bound OpenSCAD source generation.
6. Workspace-bound FreeCAD macro generation.
7. Workspace-bound schematic SVG drawing generation.
8. Independent CAD + physics pipeline with combined JSON result (pipeline.py).
9. Automated unit tests and GitHub Actions.

The dispatcher supports explicit operations such as physics.axial_member and cad.generate. CAD backends are registered by the application and selected explicitly in operating_conditions.cad_backend. The built-in CAD adapters currently support cylinder geometry only.

The pipeline runs the selected physics operation and cad.generate independently against the same EngineeringRequest. A failure in one branch does not suppress the other. Its overall status is completed (both branches ran), partial (one ran), or failed (neither ran). Branch execution status is separate from an engineering screening outcome such as fail_screening.

**Important boundary:** in this first pipeline version, CAD and physics consume the same source request independently. Physics does not yet import or derive its calculation mesh/geometry from the generated CAD artifact. No geometry equivalence or FEM result is implied.

The FreeCAD adapter generates a macro but never runs it automatically. OpenSCAD source generation also does not invoke the OpenSCAD executable. FEM, CFD, thermal, electromagnetic, and hardware-control integrations are not yet implemented.

## Pipeline example

    from pathlib import Path
    from yj64_engineering_core import (
        AxialMemberSolver,
        EngineeringDispatcher,
        EngineeringPipeline,
        EngineeringRequest,
        GeometrySpec,
        LoadCase,
        OpenSCADSourceBackend,
    )

    dispatcher = EngineeringDispatcher()
    dispatcher.register_physics_solver(AxialMemberSolver())
    dispatcher.register_cad_backend(
        "openscad", OpenSCADSourceBackend(Path("./artifacts"))
    )

    request = EngineeringRequest(
        request_id="bar-001",
        title="Axial bar",
        objective="Preliminary axial screening and CAD source generation",
        geometry=GeometrySpec(
            "cylinder",
            {
                "diameter_m": 0.05,
                "height_m": 2.0,
                "area_m2": 0.001,
                "length_m": 2.0,
            },
        ),
        material={
            "name": "Example steel",
            "youngs_modulus_pa": 200e9,
            "allowable_stress_pa": 150e6,
        },
        load_cases=(
            LoadCase("service", force_n=(0.0, 0.0, 1000.0)),
        ),
        operating_conditions={"cad_backend": "openscad"},
    )

    pipeline = EngineeringPipeline(dispatcher)
    result = pipeline.run(request, physics_operation="physics.axial_member")
    print(result.to_json())

The cylinder geometry fields used by the CAD generator and the area/length fields used by the axial screening solver are deliberately explicit. The caller must supply consistent values; the current pipeline does not infer cross-sectional area from the CAD solid.

## Dispatcher example

    from yj64_engineering_core import (
        AxialMemberSolver,
        EngineeringDispatcher,
        EngineeringRequest,
        GeometrySpec,
        LoadCase,
    )

    dispatcher = EngineeringDispatcher()
    dispatcher.register_physics_solver(AxialMemberSolver())

    request = EngineeringRequest(
        request_id="bar-001",
        title="Axial bar",
        objective="Preliminary axial screening",
        geometry=GeometrySpec(
            "prismatic_member",
            {"area_m2": 0.001, "length_m": 2.0},
        ),
        material={
            "name": "Example steel",
            "youngs_modulus_pa": 200e9,
            "allowable_stress_pa": 150e6,
        },
        load_cases=(
            LoadCase("service", force_n=(0.0, 0.0, 1000.0)),
        ),
    )

    result = dispatcher.dispatch(request, "physics.axial_member")
    print(result.response.to_json())

## Contract rules

Contract version 1.0 accepts SI units only. Geometry parameter names should carry unit suffixes (for example, width_m or diameter_m). The contract validates numeric finiteness and structural shape; backend-specific validators must still check required parameters, physical ranges, material standards, boundary conditions, and solver suitability.

## Development

Python 3.11 or newer.

    python -m pip install -e .
    python -m unittest discover -s tests -v

## Planned integrations

- Parametric CAD geometry, assemblies, tolerances, and production drawings.
- CalculiX or another solver for finite-element analysis.
- Additional physics engines for CFD, thermal, electromagnetic, multibody dynamics, fatigue, and optimization.
- A verified geometry-to-mesh handoff between CAD and numerical solvers.
- Isolated workers and a service API for CAD and physics backends.

## Data exchange

Prefer editable engineering formats where possible:

- STEP for solid CAD exchange.
- DXF or SVG for 2D drawing exchange.
- STL or 3MF for mesh/3D-print workflows.
- Versioned JSON for agent-to-service requests and results.

The exact export capability depends on the selected CAD backend.
