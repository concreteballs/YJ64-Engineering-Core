# Universal Physics and Engineering Domain Catalogue

**Scope:** YJ64 Engineering Core, branch `main`. This catalogue defines the intended breadth of the reusable physics and engineering solver platform. Listing a domain is a roadmap commitment, not a claim that its solvers already exist.

## Architectural principle

Build one shared physics kernel with versioned units, coordinate frames, geometry, materials, boundary conditions, loads, environmental states, uncertainty, provenance and validation status. Add discipline-specific solver packs behind common contracts. A solver must declare its model class, assumptions, valid parameter range, numerical method, uncertainty and exclusions.

Do not build dozens of disconnected calculators. Discipline packs are plugins over the same physical world model: they consume common geometry, material evidence, environmental state, coordinate frames and loads, then publish results and constraints back into the shared project model. A result from one discipline may create checks or boundary conditions for another. The kernel must make cross-discipline dependencies visible so an omitted physical effect can be identified rather than hidden.

The same physics may be reused across applications, but domain-specific validity must remain explicit. For example, fluid mechanics is shared by a yacht, a hydroplane and an aircraft cooling duct; the models, boundary conditions and validation evidence are not interchangeable.

## A. Classical mechanics and applied mathematics

- Kinematics and dynamics of particles and rigid bodies; 3D coordinate transforms; reference frames; rotations; angular velocity/acceleration.
- Statics, equilibrium, free-body diagrams, force/moment systems, constraints and reactions.
- Work, energy, momentum, impulse, power and conservation laws.
- Lagrangian/Newton-Euler formulations, constrained systems and multibody dynamics.
- Nonlinear dynamics, stability, bifurcations, chaotic response and sensitivity.
- Dimensional analysis, similarity, scaling, nondimensional groups and model testing.
- Numerical methods: linear/nonlinear algebra, ODE/PDE solvers, eigenproblems, optimization, interpolation and uncertainty propagation.

## B. Strength of materials and structural mechanics

- Axial, torsional, bending and combined loading; stress/strain tensors; Mohr circle; principal stresses; deflection and stiffness.
- Beams, frames, trusses, plates, shells, curved panels, pressure vessels and 3D solids.
- Elasticity, plasticity, viscoelasticity, hyperelasticity and large deformation.
- Contact, friction, joints, bolts, pins, welds, bonded joints, fasteners and load transfer.
- Local and global buckling, post-buckling, crippling and imperfection sensitivity.
- Fatigue, cumulative damage, crack initiation/growth, fracture mechanics and failure assessment.
- Impact, drop, shock, slamming, crashworthiness and transient structural response.
- Composite laminates, sandwich panels, core shear, skin wrinkling, delamination and anisotropic failure.
- Rotor/shaft dynamics, bearings, gears, couplings, pressure housings and rotating structures.
- Structural FEM from beam to shell/solid; mesh convergence, element quality, contacts, boundary-condition sensitivity and verification benchmarks.

## C. Fluid mechanics, hydraulics and hydrology

- Fluid statics, hydrostatic pressure, buoyancy, stability of floating bodies and pressure resultants.
- Incompressible and compressible flow; laminar/turbulent regimes; boundary layers; transition and separation.
- Internal flows: pipes, ducts, fittings, valves, manifolds, losses, pumps, fans, turbines and hydraulic circuits.
- External flow: lift, drag, moments, wakes, vortices, circulation and interference.
- Free-surface flow, waves, wave-current interaction, sloshing, green water and water entry/exit.
- Ship resistance, propulsors, rudders, foils, planing, hydrofoils, cavitation, ventilation and propeller-hull interaction.
- Aeration, multiphase flow, bubbles, droplets, sprays, jets and atomization.
- Compressible gas dynamics, nozzles, diffusers, shocks and expansion; heat transfer in flowing fluids.
- CFD interfaces and solver orchestration, with mesh, turbulence model, convergence and validation metadata.
- Groundwater, drainage, rainfall/runoff and environmental flow where relevant to land-based engineering.

## D. Aerodynamics and flight mechanics — full domain

- Low-speed, high-speed and compressible aerodynamics; subsonic, transonic, supersonic and hypersonic regimes where models/data are available.
- Airfoils, wings, finite-wing effects, induced/profile drag, lift distribution, downwash and stall.
- 3D aircraft configurations: fuselage, tail, control surfaces, propeller slipstream, interference and trim.
- Boundary layers, laminar/turbulent transition, separation, vortices, dynamic stall and unsteady aerodynamics.
- High-lift devices, flaps, slats, spoilers, control derivatives and stability/control derivatives.
- Rotorcraft, multicopters, propellers, ducted fans, autorotation and rotor aerodynamics.
- Ground effect, water surface interaction, spray ingestion and amphibious aircraft considerations.
- Aircraft performance: takeoff, climb, cruise, range, endurance, glide, descent and landing.
- Flight mechanics: longitudinal/lateral-directional stability, trim, control authority, manoeuvres and gust response.
- Aeroelasticity: divergence, control reversal, flutter, gust loads and flexible-wing response.
- Wind engineering: gusts, turbulence, crosswind, wind loading, buildings, masts and antennas.
- Wind-tunnel and flight-test correlation; CFD is not automatically validated by convergence.

## E. Ballistics and trajectory mechanics

- General trajectory mechanics for non-weapon engineering applications: gravity, drag, wind, density variation, spin/Magnus effects where appropriate, launch/release conditions and uncertainty.
- Atmospheric trajectories, parachute descent, payload release, rescue-marker trajectories, sports/projectile motion and re-entry/orbital transition interfaces.
- Impact mechanics, rebound, penetration as a material-response topic, energy absorption and impact test interpretation.
- Exterior trajectory estimation may be supported at a general physics level; hazardous projectile-launcher design, weapon construction, propellant/charge selection, barrel/nozzle optimization for firing, and weapon performance enhancement are outside this engineering core's supported design scope.
- For maritime distress signalling, prioritize non-projectile systems and certified equipment: radio distress alerts, AIS/DSC where applicable, EPIRB/PLB, radar transponders, high-intensity visible/infrared strobes, searchlights, acoustic signals and approved commercial pyrotechnic devices used strictly according to their instructions and regulations.

## F. Thermodynamics, heat transfer and energy systems

- First/second law, cycles, gas properties, equations of state, combustion thermodynamics and exergy.
- Conduction, convection, radiation, thermal resistance networks and conjugate heat transfer.
- Thermal expansion, thermal stress, insulation, heat exchangers, radiators, cooling loops and heat pipes.
- Refrigeration, heat pumps, HVAC, dehumidification, cold storage and phase change.
- Engines, turbines, compressors, pumps, energy conversion and efficiency maps.
- Batteries, electrochemistry, fuel cells and thermal runaway modelling through validated specialist models.
- Solar thermal/photovoltaic energy, wind/hydro generation and energy storage integration.

## G. Electricity, electronics and electromagnetics

- DC and AC circuits, three-phase systems, transient circuits, power quality and harmonics.
- Cable sizing, voltage drop, ampacity, thermal rise, connectors, busbars and distribution.
- Batteries, BMS, chargers, converters, inverters, motors, generators and power electronics.
- Protection coordination, fuses, breakers, fault currents, insulation, isolation, earthing/grounding and bonding.
- Electromagnetic fields, induction, transformers, coils, motors, generators, magnetic circuits and actuators.
- EMC/EMI, shielding, antenna systems, RF propagation, transmission lines and lightning/surge protection.
- Sensors, instrumentation, signal conditioning, ADC/DAC, noise, sampling and calibration.
- Embedded systems and control electronics interfaces; safety-related control remains separately verified.

## H. Materials science and chemistry

- Metals/alloys, phase diagrams, solidification, heat treatment, precipitation, work hardening and welding metallurgy.
- Polymers, elastomers, thermoplastics, thermosets, foams, adhesives and ageing.
- Ceramics, glasses, coatings, paints, sealants and surface engineering.
- Fibre composites, laminate theory, matrix/fibre behaviour, anisotropy, sandwich cores and interface failure.
- Corrosion: uniform, pitting, crevice, galvanic, microbiologically influenced, stress-corrosion cracking and erosion-corrosion.
- Tribology: friction, lubrication, wear, bearings, seals and surface contact.
- Diffusion, oxidation, chemical compatibility, solvent/fuel resistance and environmental degradation.
- Material/process databases must distinguish grade, product form, condition, direction, temperature, test method, source and statistical scatter.

## I. Acoustics, vibration and waves

- Linear/nonlinear vibration, free/forced response, modal analysis, resonance, damping and transmissibility.
- Rotating machinery vibration, balancing, shaft critical speeds and bearing diagnostics.
- Structural acoustics, airborne/structure-borne noise, sound insulation and noise control.
- Underwater acoustics, sonar propagation, absorption, reverberation, Doppler and transducer coupling.
- Wave mechanics: water waves, sound, elastic waves, shock waves and electromagnetic waves.
- Fatigue caused by vibration and cyclic environmental loading.

## J. Optics, photonics and thermal imaging

- Geometric and physical optics, lenses, mirrors, apertures, aberrations and optical systems.
- Lasers, beam propagation, divergence, alignment, reflection, refraction and scattering.
- Underwater optical attenuation, turbidity, bubbles, wavelength selection and receiver field of view.
- Cameras, low-light imaging, infrared/thermal systems, illumination and radiometry.
- Optical safety and laser classification must be treated as design constraints.

## K. Control theory, robotics and mechanisms

- Classical/modern control, state-space models, PID, observers, estimation, filtering and sensor fusion.
- Robust, adaptive, optimal and model-predictive control with explicit stability and safety boundaries.
- Mechanism kinematics/dynamics, linkages, gears, belts, chains, screws, cams, clutches and brakes.
- Robot links/joints, workspace, singularities, inverse kinematics, dynamics, manipulators and mobile robots.
- Actuator sizing: electric, hydraulic, pneumatic, cable/tendon, compliant and series-elastic systems.
- Contact, traction, balance and manipulation on moving platforms; base-motion compensation.
- Fault detection, fail-safe states, redundancy, interlocks and human-machine interaction.

## L. Geophysics, environment and exposure

- Atmosphere: pressure, temperature, humidity, density, wind, turbulence and altitude.
- Ocean: temperature, salinity, pressure, density, viscosity, conductivity, sound speed and optical properties.
- Weather exposure, icing, rain, spray, salt fog, UV, freeze-thaw and thermal cycling.
- Seismic vibration, ground motion, soil mechanics and foundations where relevant.
- Environmental loads and degradation must be linked to component location, mission profile and operating envelope.

## M. Reliability, risk and optimization

- Reliability engineering, failure rates, fault trees, FMEA/FMECA, HAZID/HAZOP and event trees.
- Sensitivity analysis, Monte Carlo, interval methods, uncertainty budgets and robust design.
- Multi-objective optimization across mass, cost, performance, energy, manufacturability, repairability and reliability.
- Design of experiments, parameter identification, calibration and test correlation.
- Lifecycle, maintainability, inspection intervals, spares and total cost of ownership.

## N. Engineering application packs

Reusable physics is assembled into domain packs rather than duplicating equations:
- Marine craft: hulls, hydrostatics, seakeeping, propulsion, foils, rigging, stability and marine systems.
- Aircraft and seaplanes: airframe, aero, flight mechanics, propulsion, water takeoff/landing, floats/hull, corrosion and flight safety.
- Automotive/road vehicles: chassis, suspension, tyres, braking, powertrain, crash and thermal management.
- Industrial machinery: frames, drives, shafts, bearings, gears, pumps, pressure systems and process equipment.
- Energy systems: generation, storage, conversion, distribution and thermal management.
- Robotics: mobile, humanoid, manipulator, marine and aerial platforms.
- Consumer/repair engineering: mechanisms, housings, seals, fasteners, replacement parts and manufacturing routes.

## Solver maturity and validation

Every solver record must state:
1. model type (closed-form analytical, reduced-order, empirical, numerical FEM/CFD, co-simulation or data-driven);
2. equations/model references and implementation revision;
3. required inputs, units, coordinate frames and boundary conditions;
4. validity range and known singular/invalid cases;
5. assumptions, simplifications and uncertainty;
6. verification tests (unit, benchmark, convergence, regression);
7. validation evidence against experiments, trusted reference data or accepted standards;
8. intended evidence level and prohibited interpretations.

Do not build a monolithic solver. Prioritize high-reuse, high-value foundations, then add validated solvers in vertical slices. A calculator result must never be presented as a certified design without the required independent review and testing.
