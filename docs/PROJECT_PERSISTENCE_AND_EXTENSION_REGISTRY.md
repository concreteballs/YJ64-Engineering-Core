# Project Persistence and Extension Registry

## Scope and separation

This milestone adds two independent, opt-in infrastructure services. Existing request/response contracts, dispatcher, pipeline, CAD backends, physics solvers and component graph are not changed by these services.

## Persistent project store

\`ProjectStore\` uses Python's standard-library SQLite implementation. Projects have append-only, immutable snapshots with monotonically increasing revisions, canonical JSON and SHA-256 digests. Snapshot writes require an expected current revision (optimistic concurrency); conflicting writers are rejected rather than silently overwriting one another. Transactions use SQLite write locking, foreign keys and WAL/FULL synchronous mode for file-backed databases.

The store persists calculation records with solver identity/version, operation, input digest, result payload/digest and explicit component revision dependencies. It stores artifact references, media types, optional content digests, metadata and links to calculations; artifact bytes remain in caller-owned storage and are not copied into SQLite.

When a new snapshot changes or removes a component revision, calculations pinned to that component become stale. Staleness propagates through declared component dependencies in the snapshot. Linked artifacts are marked stale too. Historical snapshots and results are retained; stale results are never silently overwritten or promoted back to current.

## Extension manifests and registry

\`ExtensionManifest\` declares extension identity, semantic version, extension kind, API version, operations, input/output schema identifiers, supported unit systems, coordinate frames and time scales, dependencies, licence, permissions, safety class, network/offline requirements, resource requirements and provenance.

\`ExtensionRegistry\` validates API compatibility, duplicate identities, declared dependencies and capability requirements. It is a metadata registry only: it does not import, install, execute or trust plugin code. Runtime loading, sandboxing, worker isolation, signing/trust policy and process supervision remain later work.

## Deliberate limits

- SQLite stores project snapshots and traceability metadata, not large CAD/FEM binaries or arbitrary external files.
- Snapshot payloads are caller-defined JSON; component staleness uses optional \`components\` records with \`component_id\`, \`revision\` and pinned \`dependencies\`.
- A caller must declare calculation dependencies correctly. An omitted dependency cannot be inferred reliably.
- Current/stale status is a traceability signal, not a statement of engineering validity.
- Manifest compatibility is declarative. It does not prove that a solver implementation is correct, safe or trustworthy.
- No existing solver is automatically registered or loaded through the new registry.

## Acceptance criteria

- Project snapshots survive process restart and retain immutable revision history.
- Concurrent stale writes fail through expected-revision checking.
- Canonical payloads reject NaN/Infinity and receive deterministic SHA-256 digests.
- Calculation and artifact provenance is persistent and queryable.
- Changed or missing component revisions stale dependent calculations and linked artifacts, including transitive component dependencies.
- Extension manifests round-trip through JSON and are fingerprintable.
- Incompatible API versions, duplicate operations/IDs, invalid dependencies and mismatched capability requirements are rejected or reported.
- No existing solver/CAD code path changes as a side effect of registering metadata.
