# YJ64 Engineering Core

A modular engineering service for the YJ64 multi-agent system.

Its purpose is to let language models, autonomous agents, and commercial agents work with structured engineering artifacts rather than relying on prose alone.

## Architecture

- **Versioned contracts** — canonical JSON requests and responses shared by agents and engineering services.
- **Physics adapters** — a common interface for analytical solvers and external simulation engines.
- **CAD adapters** — a common interface for 2D drawings and parametric 3D geometry.
- **Agent integration** — stable JSON contracts so the application, Yacht Agent, and consortium members can use the same services.
- **Validation and provenance** — SI units, finite numeric values, explicit assumptions, solver identity, warnings, limitations, and artifact references.

## Engineering rule

A generated drawing or 3D model is not proof that a design is physically safe. Analytical estimates, numerical simulations, and physical tests must be identified separately. Every result must state its method, assumptions, units, and limitations. Screening results are not certification.

## Current implementation

1. Versioned engineering request/response contracts (contracts.py).
2. Validation and JSON serialization for geometry, load cases, provenance, and artifact references.
3. A transparent axial-member screening calculation.
4. OpenSCAD source generation for a simple cylinder.
5. FreeCAD macro generation for a parametric cylinder and export instructions.
6. Basic orthographic SVG generation for a cylinder.
7. Automated unit tests and GitHub Actions.

The FreeCAD adapter currently generates a macro; actual CAD execution requires FreeCAD to be installed and explicitly invoked. FEM, CFD, thermal, electromagnetic, and hardware-control integrations are not yet implemented.

## Contract example

    from yj64_engineering_core import EngineeringRequest, GeometrySpec, LoadCase

    request = EngineeringRequest(
        request_id="bracket-001",
        title="Bracket concept",
        objective="Prepare a preliminary structural check",
        geometry=GeometrySpec(
            geometry_type="plate",
            parameters={"width_m": 0.08, "thickness_m": 0.006},
        ),
        load_cases=(
            LoadCase(name="service", force_n=(0.0, 0.0, -1200.0)),
        ),
    )

    payload = request.to_json()
    validated_request = EngineeringRequest.from_json(payload)

Contract version 1.0 accepts SI units only. Geometry parameter names should carry unit suffixes (for example, width_m or diameter_m). The contract validates numeric finiteness and structural shape; backend-specific validators must still check required parameters, physical ranges, material standards, boundary conditions, and solver suitability.

## Development

Python 3.11 or newer.

    python -m pip install -e .
    python -m unittest discover -s tests -v

## Planned integrations

- CalculiX or another solver for finite-element analysis.
- Additional physics engines for CFD, thermal, electromagnetic, multibody dynamics, fatigue, and optimization.
- More complete CAD feature trees, assemblies, tolerances, and production drawings.
- A service dispatcher and isolated workers for CAD and physics backends.

## Data exchange

Prefer editable engineering formats where possible:

- STEP for solid CAD exchange.
- DXF or SVG for 2D drawing exchange.
- STL or 3MF for mesh/3D-print workflows.
- Versioned JSON for agent-to-service requests and results.

The exact export capability depends on the selected CAD backend.
