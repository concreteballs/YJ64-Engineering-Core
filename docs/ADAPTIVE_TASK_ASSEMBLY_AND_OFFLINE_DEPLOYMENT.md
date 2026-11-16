# Adaptive Task Assembly and Offline Deployment

## Purpose

YJ64 should be able to assemble a task-specific workflow from independent discipline packs, operational modules, external tools, local data and user-provided resources. It must not become a monolith or assume that every device has every module installed.

## Task model

Represent a task with:
- objective, success criteria and urgency;
- user context and skill/authorization constraints;
- available tools, materials, components, energy and devices;
- location, environment, time and connectivity when known;
- physical, legal, medical, operational and resource constraints;
- hazards, reversibility and consequence of failure;
- required outputs and acceptable uncertainty.

Missing information remains explicitly unknown. The system asks only for details that materially change feasibility or safety.

## Capability discovery and assembly

Each module publishes a versioned manifest describing its domain, operations, input/output schemas, required data, units/frames/time scales, dependencies, resource profile, network requirements, licence, permissions, safety class, evidence level and offline capability. The task planner matches requirements to available modules and tools, checks compatibility and builds a reviewable dependency graph.

A workflow may combine, for example, chemistry, materials identification, woodworking, energy, communications and navigation. The planner must explain why each module was selected, what data it contributes and what remains unsupported. It should compare alternatives and prefer the simplest adequately supported solution.

The planner may configure approved tools and deterministic workflows but must not execute arbitrary LLM-generated code inside the core, bypass module permissions, silently download restricted data or initiate hazardous physical actions. User approval is required for external data sharing, purchases, device control or consequential actions.

## Results and evidence

Each assembled plan records module/tool versions, source references, assumptions, inputs, transformations, outputs, hazards, uncertainty and review state. Separate generated suggestions from deterministic calculations, formal proofs, numerical simulation, observational evidence and expert-reviewed procedures. Re-run or invalidate dependent results when a module, source dataset or upstream input changes.

## Offline deployment profiles

Support selectable deployment profiles rather than forcing the entire platform onto a phone:
- **Online:** connected LLMs, providers, repositories, live data and remote compute subject to permissions.
- **Limited offline:** local model plus selected cached knowledge, deterministic calculations and available device sensors.
- **Fully offline field kit:** local runtime, selected discipline modules, verified knowledge bundles, cached maps/ephemerides/reference data and essential procedures; no network assumption.

A bundle may contain an optional local LLM, task router, deterministic calculation libraries, selected discipline modules, language packs, maps, navigation data, medical/first-aid references, chemistry/materials manuals and technical documentation. Device profiling must consider RAM, storage, CPU/GPU/NPU, battery, thermal limits and expected task latency. Modules can be added/removed independently.

## Data integrity and freshness

Every offline package records source, licence, publisher, version, region, language, issue/review date, checksum/signature, dependencies and known omissions. Updates are staged and verified before replacing a bundle; preserve rollback. Clearly show stale charts, expired medical guidance, old weather data and unavailable live services. Never present cached data as current. Use signed manifests and integrity checks; support a reproducible export/import of a selected field kit.

## Privacy and permissions

Location, health, device, contacts and environmental data are permission-scoped and purpose-limited. Explain what is read, why it is needed, whether it leaves the device and how long it is retained. Offline processing is preferred for sensitive data where practical. A connected device is not automatically trusted; validate identity, data provenance and integrity.

## Acceptance criteria

- A task can be assembled from multiple independently versioned modules using declared contracts.
- Missing capabilities and data are exposed before execution; incompatible units/schemas/permissions are rejected.
- Plans include alternatives, prerequisites, hazards, stop conditions, evidence and uncertainty.
- Offline profiles can install and run selected bundles without network access.
- Bundle integrity, provenance, freshness and rollback are verifiable.
- Local model deployment is optional and device-resource-aware; core and modules remain useful without an LLM.
- No arbitrary generated code or unauthorized external action is executed by the task planner.

## Status

Planned. No adaptive task planner, module-manifest registry, local LLM package manager or offline field-kit installer is claimed as implemented.
