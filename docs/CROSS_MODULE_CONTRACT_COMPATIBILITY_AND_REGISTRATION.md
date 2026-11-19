# Cross-Module Contract Compatibility and Registration

## Status

This document defines the integration boundary for the independent Biological Engineering and Molecular & Genetic Engineering repositories. It is a compatibility specification and registration plan; it does not claim that runtime adapters or automatic dispatch are already implemented.

The coordinator remains the owner of task lifecycle, candidate routing, relevant-discipline selection, review aggregation, proposal decisions and acceptance. Both modules remain independently versioned specialist packs. No parallel worker, scheduler or registry is introduced.

## 1. Current compatibility audit

Both modules use the same conceptual candidate identity:
- `candidate_id`
- positive integer `version`
- `schema_version`
- `origin_module`

Their native Python contracts are not wire-compatible yet.

| Concept | Biological module | Molecular/genetic module | Required canonical field |
|---|---|---|---|
| Evidence identity | source + evidence_kind | evidence_id + evidence_type + source + version | evidence_id, evidence_type, source, version, limitations |
| Review version | no reviewer_version field | reviewer_version | reviewer_version (required) |
| Interface findings | interface_findings | interface_checks | interface_checks |
| Enhancement objective | parent_objective | objective | objective |
| No-proposal reason | no_proposal_rationale | rationale | rationale |
| Assessment type | CrossDisciplinaryAssessment | Assessment | assessment envelope |
| Invalidation input | changed_modules + dependency_map | changed_module + dependency_graph | changed_modules + dependency_map |

The shared meaning is close, but structural similarity is not interoperability. A coordinator must not deserialize one module's native dataclasses as the other's types or silently drop fields.

## 2. Canonical wire schemas

The initial cross-module wire schema namespace is:
- `yj64.cross_module.candidate.v1`
- `yj64.cross_module.evidence.v1`
- `yj64.cross_module.review.v1`
- `yj64.cross_module.enhancement_proposal.v1`
- `yj64.cross_module.contribution.v1`
- `yj64.cross_module.assessment.v1`

All wire payloads are JSON objects with explicit `schema_id` and `schema_version`. Unknown major versions are rejected. Unknown fields may be preserved as extension metadata but must not change the interpretation of known fields.

### Candidate
Required: schema_id, schema_version (wire format version), candidate_id, version, candidate_schema_version (native candidate schema version), origin_module. Optional: intended_scope, input_refs, provenance_refs.

### Evidence
Required: evidence_id, evidence_type, source. Optional: version, limitations, confidence, observed_at, method, applicability, provenance_digest. Confidence is descriptive metadata and is never a substitute for calibrated uncertainty or validation.

### Independent review
Required: candidate reference, reviewer_module, reviewer_version, status, rationale. Status is one of PASS, CONDITIONAL, REJECT, NOT_APPLICABLE, NOT_REVIEWED. Optional collections: evidence, assumptions, uncertainty, interface_checks, hazards, hard_constraints, conditions, unresolved_questions.

CONDITIONAL is blocking until every condition has a recorded disposition by the parent coordinator. `schemas/cross_module/condition-disposition.v1.schema.json` defines a separate, auditable record tied to the exact candidate revision and review. Only `decided_by: parent_coordinator` is accepted. A `satisfied` disposition requires evidence; rejected, deferred and unresolved dispositions remain blocking. The original module review is immutable and is never rewritten to PASS. The Core library exposes `ConditionDisposition`, `ConditionStatus` and `evaluate_condition_dispositions()` in `yj64_engineering_core.cross_module`. The durable `cross_module_assessment` TaskHandler calls the parent-side evaluator and includes condition dispositions in its checkpointed assessment. A trusted host-supplied disposition provider is optional; without complete satisfied dispositions, CONDITIONAL findings remain blocking. Production WorkerRunner assembly and trusted disposition-provider deployment remain outstanding.

### Enhancement contribution
Each relevant module returns either one or more evidence-linked proposals or an explicit no_proposal with rationale. A proposal contains proposal_id, candidate reference, proposing_module, objective, improvement, mechanism, expected_benefit, measurable success_criteria, evidence and optional assumptions, tradeoffs, risks, dependencies and validation_plan.

Parent decisions are ACCEPTED, REJECTED, DEFERRED or NEEDS_EVIDENCE with decision_rationale and decision_version. A proposal is never applied directly by its originating module.

### Assessment
The coordinator records the exact candidate revision, relevant module set, review references, contribution references, missing outputs, blocking findings and final decision. Missing, timed-out, incompatible or unavailable modules are NOT_REVIEWED and cannot be interpreted as approval.

## 3. Published JSON Schemas

The canonical JSON Schema documents are stored in `schemas/cross_module/`:
- `candidate.v1.schema.json`
- `evidence.v1.schema.json`
- `review.v1.schema.json`
- `enhancement-proposal.v1.schema.json`
- `contribution.v1.schema.json`
- `assessment.v1.schema.json`
- `condition-disposition.v1.schema.json`

They use JSON Schema Draft 2020-12. Relative `$ref` links resolve within that directory. These schemas define the wire boundary. Native-to-wire serializers are implemented in both specialist modules; reverse deserialization and production routing remain outstanding.

## 4. Acceptance invariants

1. The origin module must be included in the relevant module set but cannot be the only reviewer.
2. Every relevant module must return both an independent review and an enhancement contribution.
3. Review and contribution records must reference the exact same candidate ID, version and schema.
4. Duplicate or conflicting outputs from one module are surfaced; they are not silently overwritten.
5. REJECT, unresolved hard constraints, missing outputs and unresolved CONDITIONAL findings block acceptance.
6. NOT_APPLICABLE requires a rationale and remains visible to the parent coordinator.
7. A candidate revision invalidates all transitively affected reviews and contributions.
8. Parent acceptance of an enhancement creates a new candidate revision or child task and triggers the affected review cycle again.
9. Module manifests declare capabilities only. Registration does not load code, grant permissions or authorize wet-lab execution.

## 5. Native adapter mapping

Each module may retain its domain-specific internal types. The first adapter increment implements explicit native-to-wire serialization; reverse deserialization and runtime dispatch remain future work and are not claimed as complete:
- Biological `EvidenceRef(source, evidence_kind, confidence)` must receive a stable evidence_id and map evidence_kind to evidence_type. If no stable evidence identity can be supplied, the adapter must reject the payload rather than fabricate provenance.
- Biological `interface_findings` maps to `interface_checks`.
- Biological `parent_objective` maps to `objective`; `no_proposal_rationale` maps to `rationale`.
- Molecular `EvidenceRef` already contains the canonical evidence identity and provenance fields.
- Molecular `interface_checks`, `objective` and `rationale` already use the canonical names.
- Both adapters must include reviewer_version in the wire review; Biological receives it explicitly from the host and rejects an empty value.
- Both specialist-native assessment implementations still fail closed on every CONDITIONAL review. The Core TaskHandler uses the parent-side evaluator: every condition requires a matching disposition for the exact candidate revision and reviewer; satisfied requires stable evidence, while unresolved, rejected, deferred or missing dispositions block the assessment. The provider is injected by the trusted host, never accepted from the queue payload. Production worker assembly remains outstanding.

No adapter may convert missing evidence, missing review, unavailable modules or unresolved conditions into PASS.

## 6. ExtensionRegistry manifests

The two module repositories publish declarative manifests compatible with the existing `ExtensionManifest` and `ExtensionRegistry` structures:
- extension API version: `1.0`;
- extension kind: `discipline_pack`;
- semantic module version: `0.1.0`;
- operations: `review_candidate` and `contribute_enhancements`;
- canonical input/output schema IDs from section 2;
- no permissions;
- no network requirement;
- offline metadata support;
- safety class explicitly marks computational research with biosafety review required.

The manifests are metadata, not executable adapters. Core tests now parse checked-in snapshots through `ExtensionManifest.from_json` and register both in an isolated instance of the existing `ExtensionRegistry`; capability discovery, empty permissions and offline declarations are verified. This is test-only registration: production discovery/routing is not enabled. Do not create a second registry.

## 6A. Durable coordinator task handler

A durable TaskHandler adapter now exists at
src/yj64_engineering_core/automation/cross_module_tasks.py.
It is designed for the existing WorkerRunner handler map under the task type
cross_module_assessment; it does not create a worker loop or a queue.

The host deployment supplies:
- the existing ExtensionRegistry populated from the two reviewed manifests;
- an explicit mapping from canonical reviewer module IDs to extension IDs;
- host-created adapter objects implementing review_candidate(candidate) and
  contribute_enhancements(candidate);
- optionally, a trusted parent-side disposition_provider(candidate, reviews, context).
  The provider must return validated ConditionDisposition objects. Dispositions
  are not accepted from the untrusted queue payload.

The factory create_cross_module_task_handler(...) returns a normal TaskHandler.
The deployment adds it to the same dictionary passed to WorkerRunner:

    handlers["cross_module_assessment"] = create_cross_module_task_handler(
        registry=existing_extension_registry,
        module_bindings=module_bindings,
        adapters=host_adapters,
        disposition_provider=trusted_parent_disposition_provider,
    )
    runner = WorkerRunner(store, worker_id=worker_id, handlers=handlers)

The task payload uses protocol yj64.cross_module.task.v1 and contains the
canonical candidate plus the explicit relevant module list. The handler checks
manifest capabilities and module bindings before calling adapters. It checkpoints
each review and contribution separately, verifies checkpoint integrity and
candidate revision on resume, and writes the final assessment into the existing
task checkpoint. Queue-task completion means only that assessment computation
finished; the assessment's own decision remains authoritative and may be
pending or rejected.

This is an injectable runtime handler and focused-test target. The repository
does not yet expose a single production deployment assembly point that builds
all WorkerRunner handler maps, so this commit does not claim that live workers
have begun claiming cross_module_assessment tasks. Production deployment
registration, task enqueue integration, and parent-consumption of the resulting
checkpoint remain explicit integration steps. No live queue or database was
modified.

## 7. Integration sequence

1. Freeze the canonical wire schema names and acceptance invariants in this document.
2. Add JSON Schema definitions and round-trip/negative tests for the canonical envelopes.
3. Implement native-to-wire adapters and tests; add reverse deserialization and round-trip tests before declaring bidirectional interoperability.
4. DONE: add parent-coordinator condition-disposition aggregation to the Core assessment evaluator and durable TaskHandler; unresolved conditional findings block. Reviewer-version enforcement is performed against the registered extension version.
5. DONE: validate both manifests with the existing ExtensionManifest parser and register them in an isolated test registry.
6. DONE: add a durable TaskHandler factory that routes through the existing WorkerRunner contract and ExtensionRegistry; deployment assembly and task enqueue remain outstanding.
7. Test missing modules, incompatible schema versions, duplicate responses, stale candidate revisions, transitive invalidation, conflicting reviews and replay/restart.
8. Only then enable production discovery/routing. No runtime permissions are added by registration.

## 8. Explicit non-goals

This integration does not implement wet-lab execution, synthesis, transformation, culturing, release or deployment. It does not grant new autonomy, modify the application's supervisory module, change live queues/databases or create a second worker lifecycle.
