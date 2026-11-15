# Hydrostatic panel pressure-load generator

**Operation:** `hydrostatics.panel_pressure_loads`

**Implementation state:** executable load-generation solver with automated unit tests. It is not a structural stress solver or a scantling approval.

## Purpose

The solver converts a supplied hull-surface panel mesh into a signed hydrostatic pressure load on each panel. It reports panel pressure, force vector and moment about the global origin, plus the summed force and moment resultants. This provides an explicit interface between hydrostatics and later shell/plate/stiffener/FEM calculations.

## Input contract

Use SI units.

```python
AnalysisRequest(
    analysis_type="hydrostatics.panel_pressure_loads",
    parameters={
        "geometry": {
            "panels": [
                {
                    "panel_id": "bottom-panel-001",
                    "area_m2": 1.25,
                    "centroid_m": [1.0, 0.0, -1.5],
                    "outward_normal": [0.0, 0.0, -1.0],
                }
            ]
        },
        "operating_conditions": {
            "waterline_z_m": 0.0,
            "water_density_kg_m3": 1025.0,
            "gravity_m_s2": 9.80665,
            "internal_gauge_pressure_pa": 0.0,
        },
    },
)
```

Each panel requires a unique non-empty ID, positive area, centroid and outward unit normal. The waterline is expressed in the same global Z coordinate as panel centroids. Water density and gravity must be positive. Internal pressure is gauge pressure relative to the same atmospheric reference as external hydrostatic gauge pressure.

## Calculation

For panel centroid depth below waterline:

`h = max(0, z_waterline - z_centroid)`

`p_external = rho * g * h`

`p_differential = p_external - p_internal_gauge`

With outward unit normal `n`, panel area `A`, and centroid position `r`:

`F_panel = -p_differential * A * n`

`M_panel = r x F_panel`

Positive differential pressure therefore loads the panel inward. Negative differential pressure (internal pressure greater than external) loads it outward. Above-water panels have zero external hydrostatic pressure, but the supplied internal gauge pressure still applies.

## Output

The result includes:
- per-panel depth, external pressure, internal pressure and signed differential pressure;
- per-panel force vector and moment about global origin;
- loading direction (inward, outward or zero);
- total panel area, maximum external hydrostatic pressure;
- total force and total moment about global origin.

The operation is registered through `EngineeringDispatcher` as `physics.hydrostatics.panel_pressure_loads`.

## Current boundaries and next engineering work

The panel pressure is evaluated at each panel centroid and treated as uniform over that panel. Mesh density must therefore resolve depth gradients and curved geometry. The caller is responsible for supplying a consistent surface mesh and correctly oriented normals.

This solver does not:
- generate or validate hull geometry or mesh connectivity;
- solve hydrostatic equilibrium, displacement, trim or heel;
- include waves, acceleration, slamming, impact, grounding or transient flow;
- calculate shell/laminate, stiffener, frame, bulkhead, joint or hull-girder stress;
- create FEM boundary conditions or transfer loads automatically.

The next structural stages are mesh/geometry validation, pressure interpolation or integration over panels, shell/plate and stiffener load mapping, global hull-girder bending/torsion cases, and a validated FEM or analytical structural solver. The existing simplified catamaran displacement solver remains a separate operation; displacement estimation and pressure-load generation are complementary, not interchangeable.

A successful load-generation result is not evidence that the hull structure is strong enough, nor a class or regulatory approval.
