# YJ64 Engineering Core — implementation status

This document distinguishes executable code from architectural requirements recorded in the development plan. A documented or planned capability is not considered implemented.

## Status key

- **Implemented prototype** — executable code and automated tests exist, but scope may be limited.
- **Partially implemented** — useful executable foundation exists; major functions remain.
- **Planned** — requirements are documented, but no corresponding functional subsystem is yet implemented.
- **Not started** — no meaningful implementation identified in the current core.

## Package status

| Area | Status | Implemented now | Still required |
|---|---|---|---|
| Universal engineering core | Partially implemented | Shared request/response contracts, solver interfaces, explicit dispatcher, pipeline, component/dependency graph, mass/CG/inertia records, evidence and stale-result tracking | Persistent project database, multi-user collaboration/locking, automatic dependency recomputation, richer geometry/material/load schemas and provenance |
| Physics and engineering solvers | Partially implemented | Axial member screening, limited CalculiX axial truss adapter, coefficient-based aero/hydrodynamics, sail polar and apparent wind, catamaran hydrostatics, mass budget, hull material screening, ROV cylindrical pressure-housing screen, hull hydrostatic panel loads with polygon integration, six-DOF vessel point kinematics | General beam/plate/shell/solid FEM, hull scantlings and global strength, buckling/fatigue/vibration, seakeeping/RAOs, CFD, thermal, electrical, mechanisms, uncertainty and optimization; full cross-domain physics catalogue is now specified but most listed solvers are not implemented |
| Materials and manufacturing | Partially implemented | Limited hull-material mass/cost/maintenance comparison | Traceable material database, anisotropic composites, process qualification, metal/polymer AM, CNC process planning, tolerances, inspection, validated STEP/STL/3MF/toolpaths/G-code workflows |
| Electrical and energy systems | Planned | Requirements and architecture are documented | DC/AC network model, 12/24/48 V comparisons, loads/energy balance, battery/BMS, solar/alternators/generator/shore power, cable sizing, voltage drop, protection/selectivity, grounding/bonding, fault analysis and diagrams |
| Complete yacht / marine engineering | Partially implemented | Parametric hull geometry/CAD, preliminary catamaran hydrostatics, mass budget, sail polar/apparent wind, material screening and hydrostatic pressure load generation | Integrated design of hull structure, crossbeams, foils, rig, propulsion, propellers, rudders, accommodation, tanks/plumbing, deck gear, stability/trim/damage, energy, systems integration and class/design validation |
| Marine electronics and vessel automation | Planned | High-level requirements for sensors, navigation, communications, local control, remote supervision and fail-safe modes | Equipment/data model, sensor fusion, network architecture, control interfaces, alarm/health model, redundancy, COLREG-aware autonomy and verification |
| Robotics, mechanisms and autonomous vehicles | Planned | Architecture requirements for marine robots, UAVs, human-scale robots, mechanisms and motion compensation; vessel six-DOF base-point kinematics is now available | Robot link/joint model, multibody dynamics, actuators, balance/contact on moving decks, manipulators, winches/hoists, propeller sizing, ROV/AUV/UAV performance and safety controllers |
| Invention methods and engineering knowledge | Planned | TRIZ, USIT, SIT/ASIT, morphology, biomimicry, QFD, FMEA/HAZOP and related methods are listed in the plan | Structured knowledge base, method workflows, source/licensing metadata, contradiction/problem representations, idea generation and engineering validation pipeline |
| Reverse engineering, repair and lifecycle | Planned | Visual reference intake stores image metadata/hash and structured human annotations | Measurement/scan geometry reconstruction, tolerance analysis, component identification, repair plans, lifecycle/maintenance and qualification evidence |
| Visualization and simulation presentation | Partially implemented | SVG drawings, OpenSCAD/FreeCAD generation adapters, parametric hull outputs and image-reference annotations | Integrated accurate renderings, section/exploded views, actual kinematic animations, simulation post-processing and distinction between CAD-grounded and concept imagery |
| Website, publishing and commercial workflows | Not started | Requirements only | Content pipeline, website, product/service catalogue, marketing, sales and commercial analytics |

## Latest delivered block: vessel motion kinematics

VesselMotionKinematicsSolver (marine.vessel_motion_point_kinematics) transforms a body-fixed equipment or robot-base point into earth-frame position, velocity and acceleration from a supplied rigid-body six-DOF state. It includes roll/pitch/yaw orientation, translational motion, angular velocity, angular acceleration and centripetal acceleration.

This is **not** a wave-response or seakeeping predictor. A measured/prescribed vessel motion signal is an input. Sea-state modelling, hydrodynamic response, sensor fusion, time-series processing, deck contact and robot balance remain future work. See [VESSEL_MOTION_KINEMATICS.md](VESSEL_MOTION_KINEMATICS.md).

## Immediate next implementation sequence

1. Marine environment properties: seawater temperature/salinity-dependent density with explicit validity range and source equation; then viscosity/conductivity/pressure-depth profiles where validated models are available.
2. Extend vessel motion from a single prescribed state to timestamped motion series and interpolation with frame/sensor conventions and uncertainty.
3. Couple motion kinematics to a minimal robot link/joint model and evaluate base motion separately from robot articulation and contact.
4. Begin electrical subsystem with traceable DC loads, voltage architecture comparison, cable sizing and protection inputs.
5. Continue hull structural analysis only through validated analytical models and tests; do not label load generation or low-order screening as structural certification.

## Evidence policy

Only source code with automated tests is counted as implemented. CI success confirms the tested software state, not engineering qualification or physical validation. A solver result marked screening-only is not a design approval, class approval or safe operating limit.


## Physics scope expansion (architecture delivered; solvers still outstanding)

The target is now a universal cross-domain physics platform, not a yacht-only solver collection. `docs/PHYSICS_DOMAIN_CATALOG.md` defines the intended disciplines: mechanics, strength of materials, structural FEM, fluid mechanics, full aerodynamics and flight mechanics, general trajectory/ballistics mechanics, thermodynamics, heat transfer, electricity/electronics, electromagnetics, materials science/chemistry, corrosion/tribology, acoustics/vibration/waves, optics/photonics, controls, robotics, environmental physics, reliability and optimization. It also defines reusable application packs including marine craft, aircraft/seaplanes, vehicles, industrial machinery, energy systems, robotics and repair engineering.

**Important status:** this is a requirements/catalogue expansion, not implementation of those solvers. Current aerodynamics remains limited; full aircraft aerodynamics/flight mechanics, general ballistics/trajectory tools, comprehensive materials science, FEM, CFD, thermal, electrical and other domain solvers remain to be built and verified. The yacht is the first integrated application, not the boundary of the platform.
