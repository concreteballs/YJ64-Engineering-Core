# YJ64 Engineering Core — architecture

## Services and responsibilities

- Application / consortium dispatcher: user-facing project state, permissions, routing, and audit history.
- Yacht Agent: permitted research and workflow tasks; it is a client, not the owner of engineering truth.
- CAD service: creates editable geometry and drawing artifacts.
- Physics service: runs analytical solvers and external numerical simulation backends.
- Commercial agent: consumes versioned engineering results to estimate manufacturing, operating, maintenance, and lifecycle costs.
- Independent oversight: reviews proposed actions and consequences and cannot be modified by the supervised agent.

## Shared request/result contract

Exchange structured JSON with explicit SI units. Results should include solver/backend name and version, input parameters and units, assumptions and boundary conditions, calculated values and units, warnings and limitations, uncertainty where available, and artifact identifiers and hashes.

A language model may translate natural language into a structured request, but the adapter must validate it before passing it to a solver.

## CAD backend status

- OpenSCAD source generation: implemented for a simple cylinder.
- Basic orthographic SVG: implemented for a simple cylinder; schematic only.
- FreeCAD macro generation: implemented for a parametric Part cylinder with FCStd, STEP, and STL export.
- FreeCAD execution: explicit opt-in via run_freecad_macro; FreeCAD must be installed separately.
- Production drawings, tolerances, GD&T, assemblies, and full parametric feature trees: planned.

## Physics backend status

- Axial linear-elastic screening calculation: implemented.
- FEM, CFD, electromagnetic, thermal, multibody dynamics, fatigue, and optimization: planned adapters.
- A screening calculation or simulation is not certification or a substitute for testing.

## Security and reliability

- Do not execute arbitrary LLM-generated Python in the application process.
- Validate structured inputs and restrict output paths to an assigned project workspace in production.
- Run external CAD/solver processes in isolated workers with resource limits.
- Do not give engineering workers credentials or unrestricted network access.
- Require review and independent validation for safety-critical designs.
