# Canonical Engineering Component Model

The core uses a solver-neutral, revisioned component record as the shared identity
for a part, assembly or subsystem. CAD, physics, material and manufacturing
modules should exchange this record (or a serialized representation), rather
than maintaining incompatible copies of component properties.

## Data captured

- Stable `component_id` and positive integer `revision`.
- Name and component type.
- Optional `GeometrySpec` in SI units.
- Material identity and explicitly supplied material data.
- Mass, centre of gravity and optional symmetric inertia tensor.
- Parent assembly membership and pinned dependencies on exact component revisions.
- Named interfaces, including typed connection parameters and target component IDs.
- Manufacturing process constraints with their source.
- Evidence records with type, description, optional source URI and SHA-256.
- Lifecycle state: concept, screened, simulated, reviewed, prototype manufactured,
  bench tested, field tested, qualified, or superseded.

The model stores evidence and state labels; it does not automatically certify a
component. A transition to a more mature state must be supported by the relevant
review, test or qualification evidence in the project workflow.

## Revision and invalidation

`EngineeringComponent.fingerprint()` produces a deterministic SHA-256 digest of
the complete serialized revision. This is suitable for binding calculation
results, CAD exports, drawings and manufacturing artifacts to the exact inputs
that produced them.

Dependencies pin both a component ID and revision. The helper
`stale_component_dependencies()` reports consumers whose dependency revision
has changed or disappeared. The result is a direct dependency check; a project
graph manager must propagate invalidation transitively and mark downstream
artifacts for regeneration.

## Example

```python
from yj64_engineering_core import (
    ComponentDependency,
    ComponentMassProperties,
    EngineeringComponent,
)
from yj64_engineering_core.contracts import GeometrySpec

hull = EngineeringComponent(
    component_id="hull.port.shell",
    revision=1,
    name="Port hull shell",
    component_type="structural_shell",
    geometry=GeometrySpec("surface", {"area_m2": 42.0}),
    material={"family": "glass_fiber_composite"},
    mass_properties=ComponentMassProperties(
        mass_kg=125.0,
        center_of_gravity_m=(4.2, -2.1, 0.8),
    ),
)

crossbeam = EngineeringComponent(
    component_id="crossbeam.port",
    revision=1,
    name="Port crossbeam",
    component_type="primary_structure",
    dependencies=(
        ComponentDependency(
            component_id=hull.component_id,
            revision=hull.revision,
            purpose="hull attachment interface",
        ),
    ),
)
```

## Deliberate limits

This first model is a data contract, not a CAD kernel, materials database,
structural solver, PLM system or certification engine. It does not infer missing
properties, approve manufacturing parameters, prove interface compatibility,
or perform transitive graph invalidation. Unknown values remain absent.
