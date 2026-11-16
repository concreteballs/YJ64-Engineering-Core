# Shared Physics Kernel — Foundation

## Architecture

The physics platform is one shared kernel with independently versioned discipline packs. The kernel owns reusable data and conventions; a discipline pack owns its governing equations, domain-specific assumptions and validity limits.

Current shared-kernel foundations:
- **Material evidence library:** material identity plus multiple traceable property records. A property datum retains SI value/unit, test method, source, source date, temperature, orientation/product direction and uncertainty.
- **Environmental property models:** dry-air density from the ideal-gas equation and atmospheric-pressure seawater density from UNESCO 1983 EOS-80.
- **Physical quantities and unit registry:** finite numeric quantities, seven-base-dimension SI exponent vectors, explicit named-unit conversions, offset temperature conversion and an extensible registry. Force, moment and pressure dimensions are exposed for typed engineering conditions.
- **Coordinate frames:** a single-root frame tree, right-handed orthonormal rigid transforms, point/vector mapping, inverse transforms and frame-to-frame composition.
- **Geometry primitives:** frame-aware points/vectors, segments, planes, axis-aligned bounding boxes, spheres and cylinders with finite-value, degeneracy and frame-consistency validation.
- **Loads and boundary conditions:** force/moment vectors and fixed, displacement, rotation, pressure and temperature conditions with unit-dimension and frame checks. These are input contracts, not a structural or multiphysics solver.

The library does not invent missing properties, average incompatible test results, infer a material grade from a generic family, or silently select a direction/temperature. Solvers must request evidence appropriate to their own model and operating conditions.

## Package layout

- `physics/kernel/materials.py`: material identities, property evidence and in-memory library.
- `physics/kernel/environment.py`: shared air and seawater density models.
- `physics/kernel/quantities.py`: `Quantity`, `UnitDefinition`, `UnitRegistry`, physical dimension constants and `DEFAULT_UNIT_REGISTRY`.
- `physics/kernel/coordinate_frames.py`: `CoordinateFrame`, `CoordinateFrameRegistry` and `RigidTransform`.
- `physics/kernel/geometry.py`: reusable frame-aware geometry primitives.
- `physics/kernel/conditions.py`: `AppliedLoad` and `BoundaryCondition` contracts.
- `physics/<discipline>.py`: specialist solver packs that consume shared kernel data.

The initial material registry is in-memory, not yet a persistent database or an automatically populated commercial-material catalogue. The quantity registry uses explicit named units; arbitrary unit-expression parsing and quantity algebra are not implemented.

## Quantity and unit model

A `Quantity` couples a finite numeric value to a registered unit. A unit declares:
- a seven-element SI base-dimension vector (mass, length, time, electric current, thermodynamic temperature, amount of substance, luminous intensity);
- a positive scale to SI;
- an optional offset to SI, used for affine temperature scales.

Conversion is allowed only between units with identical dimension vectors. Unknown units, non-finite values, invalid dimensions and duplicate unit registrations are rejected. The default registry currently includes common SI base/derived units and selected practical units (for example mm, kN, MPa, bar, litre, degrees and degrees Celsius). This is a foundational explicit registry, not a complete standards catalogue.

The registry can be extended by application or discipline packages. Any extension must use unambiguous symbols and correct dimension/scale/offset definitions. Persisted project schemas must eventually pin the registry/schema version used by each artifact.

## Coordinate, geometry and load model limits\n\nCoordinate frames form a single-root tree. Each child pose maps local coordinates into its parent using a proper right-handed orthonormal rotation and metre translation. Arbitrary affine transforms, scale, reflection, deformable frames and moving-frame time histories are not implemented. Geometry primitives are basic validated references, not a CAD topology kernel or mesh representation. Loads and boundary conditions validate target identifiers, frames, unit dimensions and component counts; they are not automatically mapped onto mesh entities and do not establish solver-specific sign conventions.\n\n## Environmental models and limits

### Dry air

`dry_air_density_ideal_kg_m3(T, p)` calculates rho = p / (R_d * T), where R_d = 287.05287 J/(kg K). The implemented input envelope is 180–330 K and 30–120 kPa. Air is treated as dry and ideal. Humidity, non-ideal high-pressure gas behaviour, viscosity, thermal conductivity, speed of sound and altitude profiles are not yet included.

### Seawater

`seawater_density_eos80_kg_m3(T, S)` implements the UNESCO 1983 EOS-80 atmospheric-pressure density polynomial. The implemented input envelope is 0–40 °C and 0–42 PSU. It does not apply pressure compressibility correction. Deep-water calculations must not treat this atmospheric-pressure value as a complete pressure-dependent equation of state.

## Evidence and validation rules

- Unknown properties stay absent; no guessed default strength, stiffness, fatigue limit, corrosion rate or thermal property.
- Values are stored/communicated with explicit units; SI is the internal target convention.
- Different product forms, conditions, orientations, temperatures and sources remain separate records.
- The in-memory material library rejects duplicate material identifiers.
- Unit conversions are explicit and dimension checked.
- The EOS-80 and ideal dry-air functions are tested against reference states and reject inputs outside the declared implementation envelope.
- Passing unit tests verifies software behaviour only. It does not qualify a material batch or validate a finished engineering design.

## Next kernel increments

1. Connect the new coordinate-frame, geometry and typed load/condition records to existing solver interfaces without breaking legacy SI request payloads.
2. Add mesh/entity references and explicit solver-specific load mapping, including sign conventions and supported boundary-condition capabilities.
3. Add operating-state and environment-reference schemas.
4. Implement pressure-aware seawater thermodynamics, viscosity/conductivity, humid-air properties and atmospheric/ocean profiles, each with documented equations, limits and reference tests.
5. Add material dataset import/export with source licensing, revision history and batch/product-form traceability.
6. Add persistent project/artifact provenance and registry/schema version pinning.
7. Refactor discipline solvers incrementally to consume shared kernel records without breaking existing public operations.
