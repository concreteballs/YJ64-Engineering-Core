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
Required: candidate_id, version, schema_version, origin_module, intended_scope, input_refs, provenance_refs.

### Evidence
Required: evidence_id, evidence_type, source. Optional: version, limitations, confidence, observed_at, method, applicability, provenance_digest. Confidence is descriptive metadata and is never a substitute for calibrated uncertainty or validation.

### Independent review
Required: candidate reference, reviewer_module, reviewer_version, status, rationale. Status is one of PASS, CONDITIONAL, REJECT, NOT_APPLICABLE, NOT_REVIEWED. Optional collections: evidence, assumptions, uncertainty, interface_checks, hazards, hard_constraints, conditions, unresolved_questions.

CONDITIONAL is blocking until every condition has a recorded disposition by the parent coordinator. The disposition must be explicit and auditable; modules cannot mark their own conditions satisfied by changing the review status.

### Enhancement contribution
Each relevant module returns either one or more evidence-linked proposals or an explicit no_proposal with rationale. A proposal contains proposal_id, candidate reference, proposing_module, objective, improvement, mechanism, expected_benefit, measurable success_criteria, evidence and optional assumptions, tradeoffs, risks, dependencies and validation_plan.

Parent decisions are ACCEPTED, REJECTED, DEFERRED or NEEDS_EVIDENCE with decision_rationale and decision_version. A proposal is never applied directly by its originating module.

### Assessment
The coordinator records the exact candidate revision, relevant module set, review references, contribution references, missing outputs, blocking findings and final decision. Missing, timed-out, incompatible or unavailable modules are NOT_REVIEWED and cannot be interpreted as approval.

## 3. Acceptance invariants

1. The origin module must be included in the relevant module set but cannot be the only reviewer.
2. Every relevant module must return both an independent review and an enhancement contribution.
3. Review and contribution records must reference the exact same candidate ID, version and schema.
4. Duplicate or conflicting outputs from one module are surfaced; they are not silently overwritten.
5. REJECT, unresolved hard constraints, missing outputs and unresolved CONDITIONAL findings block acceptance.
6. NOT_APPLICABLE requires a rationale and remains visible to the parent coordinator.
7. A candidate revision invalidates all transitively affected reviews and contributions.
8. Parent acceptance of an enhancement creates a new candidate revision or child task and triggers the affected review cycle again.
9. Module manifests declare capabilities only. Registration does not load code, grant permissions or authorize wet-lab execution.

## 4. Native adapter mapping

Each module may retain its domain-specific internal types. Its adapter must translate to/from the canonical wire schemas without loss:
- Biological `EvidenceRef(source, evidence_kind, confidence)` must receive a stable evidence_id and map evidence_kind to evidence_type. If no stable evidence identity can be supplied, the adapter must reject the payload rather than fabricate provenance.
- Biological `interface_findings` maps to `interface_checks`.
- Biological `parent_objective` maps to `objective`; `no_proposal_rationale` maps to `rationale`.
- Molecular `EvidenceRef` already contains the canonical evidence identity and provenance fields.
- Molecular `interface_checks`, `objective` and `rationale` already use the canonical names.
- Both adapters must include reviewer_version in the wire review, even if the internal biological review model must first be extended.
- Both assessment implementations must use the same acceptance invariants and explicit condition-disposition model before production routing.

No adapter may convert missing evidence, missing review, unavailable modules or unresolved conditions into PASS.

## 5. ExtensionRegistry manifests

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

The manifests are metadata, not executable adapters. They must be parsed through `ExtensionManifest.from_json` and registered through the existing registry only after schema and adapter compatibility tests are added. Do not create a second registry.

## 6. Integration sequence

1. Freeze the canonical wire schema names and acceptance invariants in this document.
2. Add JSON Schema definitions and round-trip/negative tests for the canonical envelopes.
3. Implement a lossless adapter in each module and test native-to-wire-to-native conversion.
4. Add reviewer-version and condition-disposition handling to both modules; reject unresolved conditional findings.
5. Validate both manifests with the existing ExtensionManifest parser and register them in an isolated test registry.
6. Add coordinator-side routing through the existing universal task lifecycle and ExtensionRegistry.
7. Test missing modules, incompatible schema versions, duplicate responses, stale candidate revisions, transitive invalidation, conflicting reviews and replay/restart.
8. Only then enable production discovery/routing. No runtime permissions are added by registration.

## 7. Explicit non-goals

This integration does not implement wet-lab execution, synthesis, transformation, culturing, release or deployment. It does not grant new autonomy, modify the application's supervisory module, change live queues/databases or create a second worker lifecycle.
