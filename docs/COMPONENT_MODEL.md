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

## Calculation traceability and invalidation

Every dispatched CAD or physics result now carries
`provenance.input_digest_sha256`: a SHA-256 digest over the canonical engineering
request JSON and the explicitly selected operation. Thus a changed load, geometry,
material input, operating condition or operation produces a different digest.
The solver's own name, version and method remain recorded separately.

When a calculation depends on particular project components, create a
`ComponentCalculationRecord` with the result's input digest and pinned
`ComponentDependency` entries. The record may also retain a digest of the result
payload and IDs of generated artifacts. `stale_calculations()` identifies records
whose referenced component revision changed or disappeared.

This is a deterministic traceability primitive, not yet a persistent project
database or automatic scheduler. The caller must supply the component dependencies
and current revision map. Transitive invalidation, automatic reruns and artifact
regeneration will be handled by a later project-graph service. A calculation with
no declared component dependencies is not proof that it is independent of project
geometry; dependency declarations must be explicit and reviewed.

## In-memory project dependency graph

`EngineeringProjectGraph` now provides a first project-level registry:

- Components are registered with stable IDs; duplicate IDs are rejected.
- Parent and dependency links must resolve to registered components.
- Dependency revisions must match the current registered revision.
- Component replacement requires a strictly higher revision.
- Dependency cycles are rejected.
- Staleness propagates transitively: if a hull component changes, a beam
  depending on it becomes stale, and a foil depending on that beam becomes stale.
- Calculations can be registered against exact component revisions. A calculation
  is marked stale if any direct input or any transitive component dependency is stale.

The graph is in-memory only. It does not yet persist project state, coordinate
concurrent edits, schedule automatic reruns, or regenerate CAD/CAM artifacts.
A stale result is flagged, never silently reused as current.
