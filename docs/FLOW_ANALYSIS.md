# YJ64 preliminary aerodynamic and hydrodynamic analysis

## Purpose

This package introduces a common, explicit contract for steady-flow force
screening. It is the first layer of the future coupled sail–hull–foil model.
It does not yet provide CFD, predict force coefficients, or certify a design.

## Current calculation

For a supplied reference area and force coefficients:

- dynamic pressure: q = 0.5 × density × speed²
- lift: L = q × area × CL
- drag: D = q × area × CD
- side force: Y = q × area × CY
- Reynolds number: Re = density × speed × characteristic length / dynamic viscosity

All input quantities use SI units. The caller must provide appropriate
coefficients from validated polars, test data, or a separately justified
engineering source. A solver result is marked screening_only.

## Solver operations

Register both solvers with EngineeringDispatcher:

    from yj64_engineering_core import (
        AerodynamicsSolver, EngineeringDispatcher, HydrodynamicsSolver,
    )

    dispatcher = EngineeringDispatcher()
    dispatcher.register_physics_solver(AerodynamicsSolver())
    dispatcher.register_physics_solver(HydrodynamicsSolver())

Use the explicit operations:

- physics.aerodynamics.coefficient_forces
- physics.hydrodynamics.coefficient_forces

The common EngineeringRequest carries reference_area_m2 and
characteristic_length_m in geometry.parameters; flow speed, density,
dynamic viscosity and force coefficients are carried in
operating_conditions.

## What this does not calculate

The current implementation does not calculate sail polars, apparent-wind
equilibrium, hull resistance, free-surface waves, foil polars, ventilation,
cavitation, unsteady manoeuvres, aeroelasticity, or CFD fields. It must not be
used to claim that a yacht can foil.

## Next development layers

1. Validated coefficient sources and polar import for sails, foils and hull appendages.
2. Apparent-wind and sail-trim equilibrium, including force and moment balance.
3. Hull resistance and hydrostatics, followed by free-surface CFD.
4. Foil lift/drag, cavitation and ventilation screening with validated models.
5. Coupled six-degree-of-freedom transition simulation from displacement mode to foil-borne mode.
6. Structural load transfer into hull shell, crossbeams, mast and foil attachments.
7. Optimisation under cruise accommodation, payload, range, stability and safety constraints.

Each new fidelity level must retain its own provenance, validation evidence and
limitations. A low-order estimate must never be silently presented as CFD.
