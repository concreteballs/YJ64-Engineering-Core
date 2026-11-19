# Universal Task Assembly, Cross-Domain Engineering and Biohybrid Systems

## Status and intent

This document defines an architectural target for YJ64 Engineering Core. It does not claim that the described coordinators, discipline packs, biological systems or safety controls are already implemented. Implementation must proceed incrementally through versioned contracts and tests.

The common task lifecycle is universal. Engineering, research, software, procurement, biological, medical-adjacent and other task semantics belong to replaceable specialist handlers and discipline packs—not to separate incompatible task engines.

## 1. Three distinct architectural layers

### 1.1 Universal task lifecycle

The universal task orchestrator owns task identity and lifecycle, not domain meaning. It must provide:

- task registration, stable identity, type and version;
- objective, constraints, acceptance criteria and provenance;
- dependency and parent/child relationships;
- context selection and evidence references;
- handler capability discovery and compatibility checks;
- checkpointing, lease/retry/recovery and idempotent result delivery;
- result validation, artifact references and audit history;
- policy evaluation before protected actions;
- explicit suspension, resumption, cancellation and terminal states.

The orchestrator must not embed discipline-specific scientific assumptions, equations, safety thresholds or execution logic. It must not infer that two task types are interchangeable merely because their payloads are both JSON.

### 1.2 Specialist task handlers and discipline packs

A handler implements the shared task-handler contract while owning the semantics of one task type or coherent family of task types. A discipline pack declares its models, inputs/outputs, units, assumptions, operating envelope, evidence requirements, dependencies, validation status, resource needs and applicable safety constraints.

Handlers may be specialised; their lifecycle, checkpoint, provenance, policy and result interfaces must remain compatible with the universal orchestrator. A new discipline should be addable without forking the worker loop or creating a parallel task lifecycle.

### 1.3 Cross-domain coordinator

A cross-domain coordinator decomposes a goal into typed subtasks and connects independent discipline modules. It maintains a dependency graph, identifies affected domains and checks compatibility at interfaces. Modules remain separately versioned and deployable; integration does not merge their internal implementations.

Example: designing an artificial muscle for a humanoid robot may involve materials science, mechanics, chemistry, biology, electrical/control engineering, manufacturing, reliability, human factors and occupational/environmental safety.

A local success in one discipline is not global success. A material can satisfy strength, elasticity and cost targets while failing toxicity, sensitisation, infection-control, degradation or end-of-life requirements. A safety constraint discovered in one discipline must propagate to all dependent tasks and candidate designs. The originating module cannot self-certify system-level acceptability.

## 2. Task graph and shared information contracts

Represent a project as a typed directed graph, not as one long prompt or a rigid hierarchy. Nodes may represent objectives, requirements, assumptions, decisions, experiments, components, calculations, hazards, evidence, artifacts and tasks. Edges declare typed relationships such as:

- supports / contradicts / derived_from;
- depends_on / blocks / enables;
- decomposes_into / contributes_to;
- constrains / verifies / invalidates;
- supersedes / revises.

The graph may have multiple parents and cross-links. Cycles must be rejected for dependency edges that require an execution order, while explicitly declared feedback loops may be represented as iterative workflows with bounded convergence and stopping criteria.

Each task record should distinguish:
- immutable task identity and version;
- objective and acceptance criteria;
- parent and dependency references;
- selected context profile and source references;
- declared capabilities and required capabilities;
- constraints, hazards and policy requirements;
- input/output schemas and units;
- handler identity/version;
- state, checkpoints, result and artifact provenance.

A handler receives a lease-scoped context and returns a typed decision/result. It does not receive unrestricted authority merely because it is registered. The existing WorkerRunner/TaskContext pattern is the starting lifecycle integration point; do not create a second scheduler or worker loop.

## 3. Context layers and goal horizons

Context is structured information with traceable links, not only progressively shorter summaries.

Three selectable presentation levels:

1. **Postulates** — compact foundational principles and explicitly scoped axioms. Distinguish philosophical/metaphysical commitments from experimentally testable claims and project policy.
2. **Thesis summary** — concise project model: key theses, goals, decisions, constraints, open questions and their relationships.
3. **Full context** — source documents, evidence, detailed arguments, history, alternatives, dissent, assumptions and limitations.

Store canonical records and links between levels. A summary must retain source references, version, scope, confidence/status and the ability to expand to its supporting material. Summaries are not authoritative replacements for source evidence. Conflicts between old and new context must be surfaced, not silently flattened.

Goals are separate typed graph nodes, not postulates. They may be long-term, medium-term or short-term and may decompose into multiple dependent goals. A task selects the minimum sufficient context profile for its purpose; full context is not automatically better. Goal verification may use a concise objective/acceptance profile, while foundational review or safety analysis may require postulates, summaries and selected primary evidence. The selection policy remains configurable and auditable.

## 4. Risk, autonomy and permission architecture

Risk classification and autonomy are separate dimensions.

A task risk assessment considers at least severity, likelihood, exposure, reversibility, detectability, affected people/ecosystems, scale, uncertainty and downstream dependencies. Risk classes and thresholds must be versioned, domain-reviewed and conservative where evidence is weak.

Autonomy levels describe what the system may do within a policy:
- L0: analyse and recommend;
- L1: prepare a proposed action; a human authorises execution;
- L2: execute only a bounded, pre-authorised allowlist under resource and scope limits;
- L3: operate autonomously within a formally defined envelope, with monitoring, audit, stop conditions and independent verification.

These labels are policy profiles, not universal permission grants. A high autonomy level never overrides a prohibited action, a hard safety constraint, missing evidence, or a domain-specific approval requirement. Critical/high-consequence actions may remain human-authorised at every autonomy level.

The Council may analyse risks and recommend a policy change, but it cannot approve, mint, expand or self-assign its own permissions. Policy evaluation and enforcement remain outside model-generated content. The model's output is untrusted input; only a separately authorised policy engine can issue scoped, expiring capabilities. Capability checks occur at the actual execution boundary, not only during planning. Denials, policy versions, approvals and execution outcomes are auditable.

## 5. Cross-domain safety and hazard propagation

Safety is a first-class graph concern. Each relevant design/task can carry hazard records with source, affected entities, exposure routes, severity, likelihood, uncertainty, controls, residual risk, owner and evidence. Hazards propagate across dependencies and interfaces. A material selection therefore carries downstream checks for manufacture, handling, operation, maintenance, failure, cleaning, disposal and foreseeable misuse.

The coordinator must support hard constraints and stop conditions, not only weighted optimisation. A candidate that violates a non-negotiable human/ecological safety constraint cannot compensate by scoring highly on performance or cost.

A specialist oversight module may provide independent review. This document defines only the Engineering Core integration boundary; it does not attempt to specify the application's supervisory module.

## 6. Biological Engineering Module — independent module boundary

The Biological Engineering Module is a first-class optional, independently versioned module connected through shared contracts to materials, mechanics, robotics, chemistry, electronics, manufacturing, reliability and biosafety. It owns biological materials, biohybrid systems and biological surface/contamination questions. It does not own molecular/genetic design. Its inclusion is a research and modelling capability, not permission to culture, engineer, release or deploy organisms.

Potential research categories:

- biological and bio-derived materials, including extracellular matrices, mycelium-derived structures and biofabricated composites;
- biohybrid actuators and living/tissue-based actuation, with mechanical and control performance compared against non-biological alternatives;
- microbial and fungal interactions with material surfaces, including unwanted colonisation, degradation and biofouling;
- controlled surface-protection and cleaning concepts;
- contamination monitoring, sampling strategy and validated decontamination;
- environmental persistence, material ageing, waste handling and end-of-life assessment.

### 6.1 Biohybrid actuator hypothesis

The hypothesis that a living microbial or fungal community could generate useful collective contraction under electrical or magnetic stimulation is an exploratory research question, not an established actuator design.

Evaluation must begin with literature review and non-living or computational baselines. It must separately assess force, stroke, speed, efficiency, controllability, fatigue, repeatability, response time, lifetime, environmental stability, nutrient and waste logistics, containment and failure modes. The fact that organisms can grow on a nutrient medium does not establish that a system is low-maintenance or mechanically reliable.

Compare against conventional elastomers, electroactive polymers, shape-memory materials, pneumatic/hydraulic systems and established biohybrid tissue approaches. Do not assume a biological approach is simpler, safer, more efficient or more robust before evidence supports that conclusion.

### 6.2 Robot hygiene and infection-control threat model

A robot operating around people, patients, animals or contaminated environments may act as a mechanical carrier even if it cannot become clinically ill. The threat model must include external surfaces, seams, porous materials, internal cavities, air/liquid paths, tools, connectors, filters, service access and transport between zones.

Requirements should include cleanability, inspectability, drainage, material compatibility, access for maintenance, contamination indicators, validated disinfection/sterilisation procedures appropriate to the intended environment, and traceable service history. Design out inaccessible cavities where feasible. Use replaceable sealed modules or barriers where appropriate. A biological cleaning concept must never substitute for validated infection-control procedures.

Bacteriophages are narrow-host-range biological agents that target particular bacteria; they are not universal disinfectants and do not address viruses generally. Their use would require organism-specific evidence, resistance assessment, compatibility review, containment and independent biosafety approval. No assumption should be made that phages can safely or reliably sterilise hidden robot cavities.

### 6.3 Biosafety boundaries

Biological work must be risk-assessed by qualified biosafety expertise and conducted only in appropriately authorised, contained facilities. Prefer well-characterised, non-pathogenic organisms and non-replicating or non-living alternatives where possible. Do not design for environmental persistence, uncontrolled spread, host-range expansion, pathogenicity, immune evasion or resistance to containment. Do not use a robot as an open environmental delivery or propagation platform.

Any proposed biological cleaning, coating or actuator system requires a containment strategy, exposure assessment, monitoring, validated kill/inactivation and waste route, emergency response, and evidence that foreseeable failures do not expose people or the environment. Where these cannot be demonstrated, the biological approach is rejected in favour of non-biological engineering.

This architecture does not specify organism construction, genetic modifications, culture conditions, propagation protocols or operational procedures for biological agents.

## 6A. Molecular & Genetic Engineering Module — independent module boundary

Molecular & Genetic Engineering is a separate optional module, not a subcomponent of Biological Engineering or the Engineering Core. It owns computational molecular design/analysis and genetic-system representation/design/analysis, including molecular component libraries, interaction modelling, phenotype prediction, stability assessment, uncertainty and biosafety evidence. It publishes versioned candidate records through shared contracts. It does not execute wet-lab operations, authorize synthesis or release, or certify downstream biological systems. Detailed scope is in [MOLECULAR_GENETIC_ENGINEERING_MODULE.md](MOLECULAR_GENETIC_ENGINEERING_MODULE.md).

## 6B. Mandatory cross-module validation protocol

Every module output is a candidate result. The coordinator constructs an impact map from the output's declared dependencies, interfaces, intended use and foreseeable lifecycle effects, then requests reviews from all relevant modules. A review result is one of: **pass**, **conditional**, **reject**, or **not applicable with rationale**. Silence, timeout, missing integration or unavailable module is **not reviewed**, never approval.

The review set may include physics, chemistry, materials, mechanics, electrical/control, manufacturing, biological, molecular/genetic, robotics, human factors, occupational/clinical safety, cybersecurity, environmental impact, reliability, maintenance, legal/compliance and lifecycle/end-of-life modules as relevant. The set is task-specific; it is not a requirement to invoke every installed module for every trivial task.

Each review returns the candidate/version reviewed, scope, assumptions, evidence and provenance, uncertainty, interface checks, hazards, hard constraints, conditions, unresolved questions and reviewer/module version. Conflicting reviews are preserved and escalated; the coordinator must not average away a hard constraint or hide dissent. Hard constraints and unacceptable residual hazards block acceptance regardless of performance/cost scores.

Acceptance requires all relevant reviews to be complete, no unresolved blocking constraint, and explicit handling of conditional findings. The original module may revise its candidate and resubmit; all downstream reviews invalidated by the revision must be repeated. Review dependencies and results are stored in the task/project graph. This protocol applies to all modules, not only biological technologies.

## 7. Evidence and acceptance gates

Keep these evidence levels separate:
- conceptual hypothesis;
- literature-supported plausibility;
- analytical/model result;
- software/numerical verification;
- contained laboratory evidence;
- independent replication;
- application-specific validation;
- operational qualification/certification.

A model consensus is not validation. A successful simulation or software test does not establish biological safety, actuator performance or infection-control effectiveness. Every result records the exact model/solver/handler version, inputs, assumptions, uncertainty, limitations and evidence level.

## 8. Incremental implementation sequence

1. Complete the existing Council-to-parent resume path and test it through the same WorkerRunner.
2. Formalise the generic task-handler contract and capability manifest without changing the existing worker lifecycle.
3. Add typed task/project graph records and context provenance; keep postulates, thesis summaries, full context and goals distinct.
4. Add declarative risk/autonomy policy models in non-enforcing design/test mode first; no new runtime permissions are granted by this step.
5. Add cross-domain decomposition, dependency/interface validation and hazard propagation.
6. Define independent Biological Engineering and Molecular & Genetic Engineering module manifests/contracts and evidence/biosafety gates; do not implement autonomous biological execution capabilities.
7. Implement mandatory cross-module review orchestration and independent tests for missing reviews, conflicts, hard-constraint propagation, stale downstream approvals, policy bypass, missing evidence, dependency cycles, replay and worker restart.
8. Only after the policy engine and execution boundary are independently tested should bounded executor capabilities be enabled.

Each increment must preserve backward compatibility or provide explicit versioned migrations. Do not modify the YJ64 application repository or live queues/databases as part of this Engineering Core work.
