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

A request contains a stable ID, title, objective, optional geometry descriptor, material data, named load cases, operating conditions, requirements, assumptions, and explicit SI units.

A response contains the request ID, controlled status, solver name/version/method, values and units, assumptions, warnings, limitations, uncertainty data, and artifact references.

JSON serialization rejects non-finite numbers. Request and response deserialization reject JSON NaN/Infinity constants. The shared contract checks envelope structure and generic numeric validity; each backend must additionally validate its own required fields, dimensional meaning, physical ranges, boundary conditions, and supported analysis types.

## Dispatcher

EngineeringDispatcher requires the caller to select an explicit operation:
- physics.axial_member routes to a registered solver supporting axial_member.
- cad.generate routes to a registered CAD backend selected by operating_conditions.cad_backend.

The built-in AxialMemberSolver adapts the existing transparent linear-elastic axial screening calculation to the shared plugin interface. The adapter currently accepts one load case, force along the Z axis only, and no applied moment. It requires geometry parameters area_m2 and length_m plus material name, youngs_modulus_pa, and allowable_stress_pa. Unsupported transverse forces and moments are rejected rather than silently ignored.

The CAD dispatcher forwards a structured geometry/material specification to the selected backend. It records artifact metadata only when the backend returns both a media format and a location. A dummy backend in unit tests verifies routing; the existing CAD source generators still need dedicated production adapters.

## Data-flow target

1. The language-model consortium converts a design discussion into an EngineeringRequest.
2. The application validates it and calls the dispatcher with an explicit operation.
3. The selected CAD or physics adapter performs the requested operation.
4. The dispatcher returns a versioned EngineeringResponse with provenance and limitations.
5. The consortium revises the design based on evidence.
6. The commercial agent evaluates manufacturing and lifecycle costs.
7. Independent oversight reviews assumptions, evidence, and proposed real-world actions.

## CAD backend status

- OpenSCAD source generation: implemented for a simple cylinder.
- Basic orthographic SVG: implemented for a simple cylinder; schematic only.
- FreeCAD macro generation: implemented for a parametric Part cylinder with FCStd, STEP, and STL export.
- FreeCAD execution: explicit opt-in via run_freecad_macro; FreeCAD must be installed separately.
- Production CAD plugin adapters, production drawings, tolerances, GD&T, assemblies, and full parametric feature trees: planned.

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
