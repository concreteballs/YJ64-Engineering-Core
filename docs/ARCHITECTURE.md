# YJ64 Engineering Core — architecture

## System responsibilities

- Application / consortium dispatcher: project state, permissions, routing, and audit history.
- Yacht Agent: permitted research and workflow tasks; it is a client, not the owner of engineering truth.
- CAD service: creates editable geometry and drawing artifacts.
- Physics service: runs analytical solvers and external numerical simulation backends.
- Commercial agent: consumes versioned engineering results to estimate manufacturing, operating, maintenance, and lifecycle costs.
- Independent oversight: reviews proposed actions and consequences and cannot be modified by the supervised agent.

## Contract boundary

The contracts.py module defines version 1.0 of the shared request/response envelope. Requests carry stable IDs, geometry, material data, load cases, operating conditions, requirements, assumptions, and SI units. Responses carry status, solver provenance, values and units, assumptions, warnings, limitations, uncertainty, and artifact references.

JSON serialization rejects non-finite numbers. Request and response deserialization reject JSON NaN/Infinity constants. The shared contract checks envelope structure and generic numeric validity; each backend must additionally validate required fields, dimensional meaning, physical ranges, boundary conditions, and solver suitability.

## Dispatcher

EngineeringDispatcher requires an explicit operation:
- physics.axial_member routes to a registered solver supporting axial_member.
- cad.generate routes to a registered CAD backend named in operating_conditions.cad_backend.

AxialMemberSolver adapts the existing linear-elastic axial screening calculation. It accepts one load case, Z-axis force only, and no applied moment. Geometry must provide area_m2 and length_m; material must provide name, youngs_modulus_pa, and allowable_stress_pa. Unsupported loads are rejected rather than silently ignored.

## CAD adapters

The workspace-bound adapters implement the CADBackend interface and currently support cylinder geometry:
- OpenSCADSourceBackend writes editable .scad source; it does not execute OpenSCAD.
- FreeCADMacroBackend writes a .FCMacro file; it does not execute FreeCAD.
- SVGDrawingBackend writes a schematic orthographic SVG; it is explicitly not a manufacturing drawing.

Each adapter receives a workspace path at construction. The request cannot choose an arbitrary output path. Filenames are derived from a sanitized request ID. Generated artifacts are returned as typed artifact references in EngineeringResponse when both format and location are supplied.

## Data flow

1. The consortium converts a design discussion into an EngineeringRequest.
2. The application validates it and calls the dispatcher with an explicit operation.
3. The selected CAD or physics adapter performs the operation.
4. The dispatcher returns a versioned EngineeringResponse with provenance and limitations.
5. The consortium revises the design based on evidence.
6. The commercial agent evaluates manufacturing and lifecycle costs.
7. Independent oversight reviews assumptions, evidence, and proposed real-world actions.

## Current solver limits

- Axial linear-elastic screening: implemented.
- FEM, CFD, electromagnetic, thermal, multibody dynamics, fatigue, and optimization: not yet implemented.
- Screening calculations and generated CAD artifacts are not certification or substitutes for physical testing.

## Security and reliability

- Do not execute arbitrary LLM-generated Python in the application process.
- Keep artifact output inside an assigned project workspace.
- Run external CAD/solver processes in isolated workers with resource limits.
- Do not give engineering workers credentials or unrestricted network access.
- Require independent validation for safety-critical designs.
