# Shared Physics Kernel — Foundation v0.1

## Architecture

The physics platform is one shared kernel with independently versioned discipline packs. The kernel owns reusable data and conventions; a discipline pack owns its governing equations, domain-specific assumptions and validity limits.

The first kernel slice establishes two cross-domain registries/models:

- **Material evidence library:** material identity plus multiple traceable property records. A property datum retains SI value/unit, test method, source, source date, temperature, orientation/product direction and uncertainty.
- **Environmental property models:** dry-air density from the ideal-gas equation and atmospheric-pressure seawater density from UNESCO 1983 EOS-80.

The library does not invent missing properties, average incompatible test results, infer a material grade from a generic family, or silently select a direction/temperature. Solvers must request evidence appropriate to their own model and operating conditions.

## Package layout

- physics/kernel/materials.py: material identities, property evidence and in-memory library.
- physics/kernel/environment.py: shared air and seawater density models.
- physics/<discipline>.py: specialist solver packs that consume shared kernel data.

The initial in-memory library is a foundation, not yet a persistent database or an automatically populated commercial-material catalogue.

## Environmental models and limits

### Dry air

dry_air_density_ideal_kg_m3(T, p) calculates rho = p / (R_d * T), where R_d = 287.05287 J/(kg K). The implemented input envelope is 180–330 K and 30–120 kPa. Air is treated as dry and ideal. Humidity, non-ideal high-pressure gas behaviour, viscosity, thermal conductivity, speed of sound and altitude profiles are not yet included.

### Seawater

seawater_density_eos80_kg_m3(T, S) implements the UNESCO 1983 EOS-80 atmospheric-pressure density polynomial. The implemented input envelope is 0–40 °C and 0–42 PSU. It does not apply pressure compressibility correction. Deep-water calculations must not treat this atmospheric-pressure value as a complete pressure-dependent equation of state.

## Evidence and validation rules

- Unknown properties stay absent; no guessed default strength, stiffness, fatigue limit, corrosion rate or thermal property.
- Values are SI and their unit is retained explicitly.
- Different product forms, conditions, orientations, temperatures and sources remain separate records.
- The in-memory library rejects duplicate material identifiers.
- The EOS-80 and ideal dry-air functions are tested against reference states and reject inputs outside the declared implementation envelope.
- Passing unit tests verifies software behaviour only. It does not qualify a material batch or validate a finished engineering design.

## Next kernel increments

1. Add pressure-aware seawater thermodynamics, viscosity and conductivity only with documented equations, limits and reference tests.
2. Add humid-air properties and atmospheric profiles.
3. Add unit-aware quantity types, coordinate-frame transforms, geometry primitives and common load/boundary-condition schemas.
4. Add material dataset import/export with source licensing, revision history and batch/product-form traceability.
5. Refactor discipline solvers incrementally to consume kernel records without breaking existing public operations.
