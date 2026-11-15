# YJ64 Engineering Core — architecture

## System responsibilities

- Application / consortium dispatcher: project state, permissions, routing, and audit history.
- Yacht Agent: permitted research and workflow tasks; it is a client, not the owner of engineering truth.
- CAD service: creates editable geometry and drawing artifacts.
- Physics service: runs analytical solvers and external numerical simulation backends.
- Commercial agent: consumes versioned engineering results to estimate manufacturing, operating, maintenance, and lifecycle costs.
- Independent oversight: reviews proposed actions and consequences and cannot be modified by the supervised agent.

## Contract boundary

The contracts.py module defines version 1.0 of the shared request/response envelope.

A request contains:
- stable request ID, title, and objective;
- optional geometry descriptor and parameters;
- material data;
- named load cases with force (N) and moment (N·m) vectors;
- operating conditions, requirements, and assumptions;
- explicit SI unit system and contract version.

A response contains:
- matching request ID and controlled status;
- solver name, version, and method;
- values and a unit for each reported value;
- assumptions, warnings, and limitations;
- artifact references and optional uncertainty data.

JSON serialization rejects non-finite numbers. Request deserialization rejects JSON NaN/Infinity constants. The shared contract checks envelope structure and generic numeric validity; each backend must additionally validate its own required fields, dimensional meaning, physical ranges, boundary conditions, and supported analysis types.

## Data-flow target

1. The language-model consortium converts a design discussion into an EngineeringRequest.
2. The dispatcher validates the request and routes geometry work to a CAD adapter.
3. A physics adapter receives validated geometry/material/load data and returns an EngineeringResponse.
4. The consortium revises the design based on solver results and limitations.
5. The commercial agent evaluates manufacturing and lifecycle costs from versioned artifacts and results.
6. Independent oversight reviews assumptions, evidence, and proposed real-world actions.

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
- Require independent validation for safety-critical designs.
