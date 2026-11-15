# YJ64 Engineering Core

A modular engineering service for the YJ64 multi-agent system.

Its purpose is to let language models, autonomous agents, and commercial agents work with structured engineering artifacts rather than relying on prose alone.

## Architecture

- **Versioned contracts** — canonical JSON requests and responses shared by agents and engineering services.
- **Dispatcher** — explicit routing to registered CAD and physics backends; operations are never guessed.
- **Physics adapters** — a common interface for analytical solvers and external simulation engines.
- **CAD adapters** — a common interface for 2D drawings and parametric 3D geometry.
- **Validation and provenance** — SI units, finite numeric values, explicit assumptions, solver identity, warnings, limitations, and artifact references.

## Engineering rule

A generated drawing or 3D model is not proof that a design is physically safe. Analytical estimates, numerical simulations, and physical tests must be identified separately. Every result must state its method, assumptions, units, and limitations. Screening results are not certification.

## Current implementation

1. Versioned engineering request/response contracts (contracts.py).
2. Validation and JSON serialization for geometry, load cases, provenance, and artifact references.
3. Explicit engineering dispatcher (dispatcher.py).
4. Built-in dispatcher adapter for axial linear-elastic screening.
5. OpenSCAD source generation for a simple cylinder.
6. FreeCAD macro generation for a parametric cylinder and export instructions.
7. Basic orthographic SVG generation for a cylinder.
8. Automated unit tests and GitHub Actions.

The dispatcher supports explicit operations such as physics.axial_member and cad.generate. CAD backends must be registered by the application and selected explicitly in operating_conditions.cad_backend. The current CAD dispatcher test uses a dummy backend; the real CAD generators have not yet been wrapped as production backend plugins.

The FreeCAD adapter currently generates a macro; actual CAD execution requires FreeCAD to be installed and explicitly invoked. FEM, CFD, thermal, electromagnetic, and hardware-control integrations are not yet implemented.

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

- Wrap the existing FreeCAD and OpenSCAD generators as registered CAD backend plugins.
- CalculiX or another solver for finite-element analysis.
- Additional physics engines for CFD, thermal, electromagnetic, multibody dynamics, fatigue, and optimization.
- More complete CAD feature trees, assemblies, tolerances, and production drawings.
- Isolated workers and a service API for CAD and physics backends.

## Data exchange

Prefer editable engineering formats where possible:

- STEP for solid CAD exchange.
- DXF or SVG for 2D drawing exchange.
- STL or 3MF for mesh/3D-print workflows.
- Versioned JSON for agent-to-service requests and results.

The exact export capability depends on the selected CAD backend.
