# YJ64 External Engineering Ecosystem — Evaluation and Integration Policy

This document defines the external-tool shortlist and adoption process for the authoritative YJ64 development plan.

## 1. Decision

YJ64 owns the canonical project model, common engineering semantics, provenance, compatibility rules and extension contracts. Mature specialist tools may be reused through replaceable adapters and isolated workers. YJ64 will not rebuild mature numerical engines by default, and it will not surrender its architecture to one third-party platform.

The candidates below are an evaluation shortlist, not approved dependencies. No tool becomes a required runtime dependency until it passes task-specific technical, legal, operational and validation review.

## 2. Responsibility boundary

YJ64 owns:
- canonical, versioned project/component/assembly/interface identities;
- quantities, units, coordinate frames, geometry references and typed engineering states;
- solver-neutral input/output contracts and boundary validation;
- provenance, assumptions, applicability, uncertainty, evidence and result history;
- dependencies, stale-result propagation, reproducibility and orchestration;
- extension discovery, compatibility, permissions and execution isolation.

External tools own their specialist numerical algorithms and native data structures. An adapter translates YJ64 data to and from the tool, validates conversions, launches it in a bounded worker and returns a normalized, traceable result. Native files may be retained as source artifacts, but they do not replace the canonical YJ64 project model.

## 3. Candidate portfolio

| Candidate | Role to evaluate | Important boundary | Initial priority |
|---|---|---|---|
| OpenMDAO | Multidisciplinary workflow composition, coupling and optimization | Orchestrator, not a general physics solver or project database | High |
| SALOME | Geometry/pre-processing, meshing, solver supervision, post-processing and visualization | Platform for simulation workflows; not a universal solver | High |
| FreeCAD | Parametric CAD, automation and geometry exchange | Not a complete CAE or multidisciplinary kernel | High |
| OpenModelica / OMSimulator | Equation-based system models and FMI/SSP co-simulation | Not a replacement for specialist CFD/FEM | High |
| OpenFOAM | CFD and fluid/thermal analyses within supported models | Specialist solver, not a project platform | High |
| MOOSE | Extensible multiphysics finite-element applications | Evaluate against a concrete use case, not as a turnkey universal solver | Medium |
| CalculiX | Structural FEM for suitable cases | Existing narrow adapter is not full structural qualification | High comparison |
| Elmer FEM | Multiphysics FEM for suitable structural, thermal and electromagnetic cases | Compare formulations and validation case-by-case | Medium |
| Code_Aster | Advanced structural mechanics workflows | Assess automation, complexity and compute footprint | Medium |
| NASA Software Catalog: GMAT, Trick, GUNNS, NASA CEA and other releases | Reuse task-specific mission, aerospace, system and physical tools | Every release has its own scope, interfaces and licence conditions | Per-task |
| Orekit | Astrodynamics, orbit determination/propagation, frames, time and flight dynamics | Evaluate supported use cases, data dependencies, exact version and licence | High candidate |
| Tudat | Astrodynamics and trajectory simulation | Research/toolkit scope; benchmark and integration effort must be assessed | Medium |
| NASA SPICE / NAIF | Planetary and spacecraft geometry, kernels, ephemeris-based computations | Kernel provenance, time/frame conventions and data licensing/coverage | High candidate |
| NOVAS / ERFA / Skyfield | Astronomical transformations, astrometry and ephemeris-related calculations | Distinguish reference algorithms from data sources; validate time scales and accuracy | Per-task |
| OpenCPN and Signal K ecosystem | Marine navigation interoperability, instrument data and plugin interfaces | Do not assume access to proprietary chart data or compatibility with every app | High evaluation |
| Celeste and other celestial-navigation apps | Reference implementations for offline celestial-navigation workflows | Evaluate code licence, algorithm correctness, offline datasets and safety limits | Research |
| Navionics and other commercial chart/anchoring apps | Existing user-facing charting, route and anchoring capabilities | Integrate only through documented/licensed APIs or supported exports; no scraping or licence bypass | Per-provider |
| 3DEXPERIENCE, Siemens Xcelerator/Simcenter, Ansys ModelCenter | Commercial architecture/workflow benchmarks and optional integrations | Not the open-source foundation; access and terms apply | Reference |

OpenMDAO is not treated as a physics solver. SALOME is not treated as a universal solver. FMI is an interface standard, not a solver or complete coupling algorithm.

## 4. Standards and interoperability

Evaluate:
- FMI for model exchange and co-simulation; distinguish Model Exchange from Co-Simulation and document event, time-step and synchronization semantics.
- SSP for packaging and describing system structures and connections where supported.
- STEP for suitable solid CAD exchange; record application protocol and fidelity losses.
- Solver-specific mesh and field formats, without assuming identical semantics from matching file extensions.
- Versioned JSON contracts for canonical YJ64 project, request/response, evidence and provenance records.
- NMEA 0183/NMEA 2000 and Signal K for marine instrument exchange where the exact implementation and licensing permit; GPX for suitable route/track/waypoint exchange.
- Time and reference-frame standards/conventions required by astronomical and geospatial data; every adapter declares UTC/TAI/TT/UT1 or other time-scale handling explicitly.

Standards are interoperability boundaries, not substitutes for validation. Every adapter states what is preserved, transformed, approximated or discarded.

## 5. Mandatory candidate evaluation record

For each exact product, release and optional module, record:
1. Identity, maintainers, release history, activity, supported platforms and end-of-life policy.
2. Exact licence for code, dependencies, plugins, GUI bindings, runtime libraries, datasets and generated artifacts; attribution, redistribution, source-disclosure and commercial-use obligations; legal review where unclear.
3. Interfaces: CLI/API/Python bindings, headless operation, input/output formats, schema stability, error reporting and testability.
4. Technical scope: physics, numerical methods, assumptions, supported boundary conditions, limitations and validation evidence.
5. Execution: installation, OS, CPU/GPU/HPC, memory/time, parallelism, offline use and worker feasibility.
6. Data semantics: units, coordinate conventions, sign conventions, mesh/field conventions and precision.
7. Security/reliability: dependency health, sandbox feasibility, file/network permissions, crash containment and resource limits.
8. Validation: documented examples, benchmarks, independent comparison, experimental correlation and applicability envelope.
9. Integration cost: adapter effort, maintenance, upgrade burden, usability and fallback options.
10. Decision: adopt, pilot, defer, reject or optional commercial integration, with reasons and review date.

Do not infer licence compatibility from a project name. Review the exact release and complete dependency set. A process boundary does not automatically resolve every licence obligation.

## 6. Adapter contract

Every adapter declares:
- stable adapter ID and semantic version;
- external tool and exact supported versions;
- licence metadata and dependency inventory;
- supported operations/capabilities;
- accepted and returned schema versions;
- required/optional inputs, units, frames and sign conventions;
- assumptions, applicability bounds and unsupported cases;
- conversion rules and lossy transformations;
- execution mode, resource limits, timeout and cancellation;
- reproducibility settings where available;
- benchmark IDs and evidence level;
- structured warnings/errors, logs and artifact references.

Reject incompatible schemas, missing inputs, invalid units/frames and unsupported ranges before execution where possible. Validate outputs before accepting them. A crash, timeout or malformed result must not corrupt project state.

External tools run in isolated, resource-bounded workers with least-privilege file/network access. The core must not execute arbitrary LLM-generated code. Extensions require reviewable manifests, declared capabilities and controlled installation.

## 7. Integration gates

A. **Inventory and screening:** exact release, maintenance, licence/dependencies, interface and one bounded task. No core dependency at this stage.

B. **Standalone reproducibility:** run a documented example; capture exact inputs, version, settings, logs, outputs, resource use and reproducibility limits.

C. **Thin adapter:** implement one narrow operation; validate unit/frame/schema conversions and failure handling.

D. **Benchmark:** compare against analytical, published or independently checked references; record tolerances, convergence, sensitivity and discrepancies.

E. **Project integration:** verify provenance, revision pinning, stale propagation, repeatability, cancellation, error containment and replacement by another implementation where practical.

F. **Adoption decision:** only after A–E may a tool be accepted as an optional adapter. Mandatory dependency status requires a separate architecture decision and a reduced core mode without it.

## 8. Recommended first pilots

1. OpenMDAO: orchestrate two simple YJ64 analysis components without duplicating the canonical project graph.
2. SALOME: exchange one parametric solid and mesh; inspect fidelity, metadata and coordinate conventions.
3. FreeCAD: test STEP import/export round trips against current YJ64 geometry.
4. OpenModelica/OMSimulator with FMI/SSP: exchange a small thermal/electrical/mechanical model; test units, initialization, events and time synchronization.
5. OpenFOAM: run one bounded documented CFD benchmark; validate mesh, boundary mapping, convergence and extraction.
6. FEM comparison: solve one like-for-like structural benchmark with the current CalculiX adapter and one of Elmer, Code_Aster or MOOSE.

Do not begin with a complete yacht, aircraft or humanoid robot model.

## 9. First-priority questions

| Candidate | First question | Main risk |
|---|---|---|
| OpenMDAO | Can it orchestrate YJ64 components without a competing project graph? | Duplicate workflow state |
| SALOME | Can its geometry/mesh pipeline run headlessly and preserve metadata? | Geometry/mesh semantic loss; runtime footprint |
| FreeCAD | Can geometry survive repeatable STEP round trips? | Loss of parametric feature history |
| OpenModelica | Can FMI/SSP represent required connections and time semantics? | Units, events and co-simulation mismatch |
| OpenFOAM | Can a case be generated, run and parsed in an isolated worker? | Case complexity, compute cost and GPL obligations |
| MOOSE | Does a concrete multiphysics case justify its build/integration cost? | Application-specific complexity |
| FEM candidates | Which engine best fits a chosen benchmark and workflow? | Formulation/element/material/convergence differences |
| NASA tools | Is the exact release usable under compatible terms with a workable interface? | Per-tool licence, platform and maintenance |

## 10. Primary sources to re-check

- OpenMDAO: https://openmdao.org/docs/
- SALOME licence and FAQ: https://www.salome-platform.org/?page_id=2622 and https://www.salome-platform.org/?page_id=428
- OpenFOAM Foundation licence: https://openfoam.org/licence/
- OpenFOAM.com licensing: https://www.openfoam.com/documentation/licencing
- OpenModelica licence: https://openmodelica.org/useresresources/license/
- FMI specification: https://fmi-standard.org/docs/main/
- NASA Software Catalog: https://software.nasa.gov/

These are starting points, not legal opinions or permanent licence guarantees. Re-check the exact version, dependencies and distribution model before adoption.

## 11. Non-goals

- Do not replace the YJ64 kernel with OpenMDAO, SALOME, OpenModelica or a commercial platform.
- Do not implement every adapter before proving a useful task.
- Do not require all external tools to use core YJ64.
- Do not equate successful execution with numerical/physical validity.
- Do not silently convert units, frames, sign conventions or assumptions.
- Do not allow an external solver to rewrite canonical project data without a validated, reviewable import.


## 12. Navigation, location and time integrations

Evaluate phone platform location APIs and sensor interfaces, external GNSS receivers, marine instrument gateways, NMEA 0183/2000, Signal K, GPX, OpenCPN plugins and provider-supported APIs for commercial charting/anchoring applications. Each integration must document permissions, data ownership, offline behaviour, update/correction policy, licensing and whether it provides a fix, an estimate or only a route/chart artifact. Do not reverse-engineer protected interfaces, scrape chart tiles or imply that an app offers a public API without verification.

Time-source adapters must preserve source, last synchronization, uncertainty, monotonic-clock relation, UTC/time-scale semantics and timezone separately. Peer time is not trusted merely because a device recently had internet access; its synchronization provenance and drift must be evaluated.

## 13. Astronomy and astrodynamics candidates

Evaluate Orekit, Tudat, NASA SPICE/NAIF, NOVAS, ERFA and Skyfield for concrete tasks. Pin ephemeris/kernel datasets separately from software versions. Validate reference frames, time scales, leap-second data, gravitational parameters, coordinate transformations and numerical tolerances against authoritative references. Celestial-navigation application examples may inform UI and procedures but do not replace independently verified navigation algorithms.

## 14. Integration boundaries

- A charting application is not a YJ64 navigation solver; it may be a licensed external provider or user-facing companion.
- A phone sensor is not a calibrated navigation-grade instrument by default.
- A dead-reckoned position is an estimate with growing uncertainty, not a GNSS-equivalent fix.
- An ephemeris library and its ephemeris datasets are separate dependencies with separate provenance.
- Candidate names are evaluation leads, not approved dependencies or claims of current API availability.
