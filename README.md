# YJ64 Engineering Core

A modular engineering service for the YJ64 multi-agent system.

Its purpose is to let language models, autonomous agents, and commercial agents work with **structured engineering artifacts** rather than relying on prose alone.

## Initial architecture

- **Project data** — typed, unit-explicit engineering requests and results.
- **Physics adapters** — a common interface for analytical solvers and external simulation engines.
- **CAD adapters** — a common interface for 2D drawings and parametric 3D geometry.
- **Agent integration** — stable JSON contracts so the app, Yacht Agent, and other consortium members can use the same services.
- **Validation** — input validation, explicit assumptions, units, provenance, and tests.

## Important engineering rule

A generated drawing or 3D model is not proof that a design is physically safe. Analytical estimates, numerical simulations, and physical tests must be identified separately. Every result must state its method, assumptions, units, and limitations.

## First milestone

The first implementation is deliberately dependency-light:

1. Typed SI-unit data structures.
2. A small, transparent axial-member calculation as a reference physics solver.
3. A parametric OpenSCAD source exporter for simple geometry.
4. Automated tests for validation and calculations.

This is a foundation, not a certified engineering package. It does not yet integrate FreeCAD, FEM, CFD, or hardware control.

## Development

Python 3.11 or newer.

```bash
python -m unittest discover -s tests -v
```

## Planned adapters

- FreeCAD / OpenCASCADE for editable CAD geometry and technical drawings.
- OpenSCAD for code-driven parametric models.
- CalculiX or another solver for finite-element analysis.
- Additional physics engines behind the same solver interface.

## Data exchange

Prefer editable engineering formats where possible:

- STEP for solid CAD exchange.
- DXF or SVG for 2D drawing exchange.
- STL or 3MF for mesh/3D-print workflows.
- JSON for agent-to-service requests and results.

The exact export capability depends on the selected CAD backend.
