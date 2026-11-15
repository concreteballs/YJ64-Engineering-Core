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
- physics.axial_member routes to the analytical axial screening solver.
- physics.axial_truss_fem routes a Z-axis axial load case to the registered CalculiX T3D2 solver.
- cad.generate routes to a registered CAD backend named in operating_conditions.cad_backend.

AxialMemberSolver adapts the existing linear-elastic axial screening calculation. It accepts one load case, Z-axis force only, and no applied moment. Geometry must provide area_m2 and length_m; material must provide name, youngs_modulus_pa, and allowable_stress_pa. Unsupported loads are rejected rather than silently ignored.

## Engineering pipeline

EngineeringPipeline executes two explicit branches for one EngineeringRequest:
1. The configured physics operation (for example, physics.axial_member).
2. cad.generate using operating_conditions.cad_backend.

Each branch is attempted independently. Exceptions are captured with their type and message in that branch; a failure in CAD does not prevent physics from running, and vice versa. Pipeline status is:
- completed: both branches returned a dispatcher result;
- partial: exactly one branch returned a dispatcher result;
- failed: neither branch returned a dispatcher result.

A branch execution completing does not mean that the design passed engineering screening. For example, a physics response with status fail_screening is still a successfully executed calculation whose result indicates a failed criterion.

**Current data boundary:** both branches receive the same original request, but run independently. Physics does not read the CAD artifact, derive a mesh from it, or verify geometric equivalence. Geometry values required by each branch must be provided explicitly and kept consistent by the caller. The pipeline makes no claim of FEM accuracy or CAD-to-analysis traceability.

## CalculiX FEM adapter

CalculiXTrussSolver is a bounded external-process adapter for one explicitly limited analysis:
- A single straight T3D2 truss element aligned with global Z.
- One axial force component in global Z; transverse forces and applied moments are rejected.
- Explicit area, length, Young's modulus, and Poisson ratio in SI units.
- Node 1 fixed in all translations; node 2 restrained in X/Y and loaded in Z.
- The solver writes its own input deck in a configured workspace, starts `ccx -i <job>` with `shell=False`, and enforces a timeout.
- It reads the tip displacement from the CalculiX text result. Axial strain and stress are then derived from that displacement and the supplied material modulus.

The adapter does not accept arbitrary LLM-provided .inp files. The current one-element truss has no bending stiffness and does not resolve 3D solid stress concentrations, buckling, fatigue, contact, or nonlinear behavior. It is a narrow FEM integration and verification milestone, not a general structural solver.

## CAD adapters

The workspace-bound adapters implement the CADBackend interface and currently support cylinder geometry:
- OpenSCADSourceBackend writes editable .scad source; it does not execute OpenSCAD.
- FreeCADMacroBackend writes a .FCMacro file; it does not execute FreeCAD.
- SVGDrawingBackend writes a schematic orthographic SVG; it is explicitly not a manufacturing drawing.

Each adapter receives a workspace path at construction. The request cannot choose an arbitrary output path. Filenames are derived from a sanitized request ID. Generated artifacts are returned as typed artifact references in EngineeringResponse when both format and location are supplied.

## Data flow

1. The consortium converts a design discussion into an EngineeringRequest.
2. The application validates it and calls EngineeringPipeline with an explicit physics operation.
3. The pipeline invokes the physics and CAD dispatcher branches independently.
4. Each branch returns a versioned EngineeringResponse or a captured branch error.
5. The combined result is returned to the consortium for review and design iteration.
6. The commercial agent evaluates manufacturing and lifecycle costs using traceable inputs.
7. Independent oversight reviews assumptions, evidence, and proposed real-world actions.

## Current solver limits

- Axial linear-elastic screening: implemented.
- CAD source/macro/SVG generation for cylinders: implemented; external CAD executables are not run.
- General 3D solid FEM, mesh generation/quality validation, CAD-to-mesh transfer, CFD, electromagnetic, thermal, multibody dynamics, fatigue, and optimization: not yet implemented.
- The current CalculiX integration is limited to one axial T3D2 truss element.
- Screening calculations and generated CAD artifacts are not certification or substitutes for physical testing.

## Security and reliability

- Do not execute arbitrary LLM-generated Python in the application process.
- Keep artifact output inside an assigned project workspace.
- Run external CAD/solver processes in isolated workers with resource limits.
- Do not give engineering workers credentials or unrestricted network access.
- Require independent validation for safety-critical designs.
