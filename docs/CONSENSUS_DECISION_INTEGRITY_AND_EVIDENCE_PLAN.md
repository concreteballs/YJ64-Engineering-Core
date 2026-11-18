# Consensus, Decision Integrity and Evidence-Based Engineering — Implementation Plan

Status: Planned architecture, approved for staged implementation
Repository: concreteballs/YJ64-Engineering-Core
Branch: main

## Scope and boundaries
This plan covers reusable consensus, voting, competence evaluation, evidence integrity and practical-validation contracts for the Engineering Core. The autonomous GitHub cycle is responsible only for executing bounded tasks, observing CI/runtime evidence, communicating with the browser agent when information is missing, and continuing or stopping safely. Do not duplicate the application's supervisory module: round limits, participant instruction injection, repetition detection and session stop enforcement remain app-level responsibilities.

Before each stage, audit existing Engineering Core math, physics, chemistry, solver, evidence, testing, diagnostics and persistence components. Reuse directly or via adapters; no duplicate engines.

## 1. Consensus and Critique protocol
- Configurable round ceiling, mandatory critical review in autonomous deliberation, early stop when stable consensus is supported.
- Criticism must address actual claims/arguments, never manufacture disagreement.
- Consensus is not required. Outcomes may be: supported consensus, qualified consensus, unresolved disagreement, insufficient evidence, or invalid/incomplete session.
- Never pressure a model to change position just to finish.
- Consensus is not truth. Preserve minority objections and supporting evidence.
- Consensus and Critique are separate modes: consensus evaluates proposed decisions; critique examines an object and converges on a critique protocol, without falsely implying the object itself is disproven.
- No automatic restart of a finished session. A user/authorized controller may start a new session.

## 2. Voting Engine
- Extract/normalize atomic claims from the discussion and accept user-added ballot questions.
- Give all participants the same ballot statements; independent, private votes: FOR, AGAINST, ABSTAIN, CONDITIONAL.
- Lock votes before aggregate results are shown; prevent leakage through interim counts, ordering, coordinator prompts, rankings or exposed metadata.
- Calculate simple majority and competence-weighted results separately. Show disagreements and reliability/uncertainty.
- If voting is enabled, conduct it after consensus or after round exhaustion/unresolved disagreement. If disabled, emit the deliberation protocol without ballots.
- Majority does not establish correctness.

## 3. Competence model and private ratings
Ratings are private system metadata; models must not see ratings, numeric scores, ranking comparisons, or hints designed to influence voting. Do not include rating data in prompts, shared chat, public result text to models, or ordering that leaks ranking.

Maintain separate, domain-specific and global metrics:
- independently verified task correctness;
- practical/experiment/simulation/test outcome agreement;
- majority alignment (descriptive, not truth);
- critique quality (validated actionable defects found, false-positive burden, severity);
- prediction calibration;
- abstention and conditional-vote quality where evidence supports scoring.

A minority vote that matches a verified result must be credited for correctness and evidence; a majority-aligned incorrect vote must be penalized by error severity. Do not reward contrarianism: disagreement receives no bonus by itself; wrong predictions/votes receive a penalty; verified correctness is credited regardless of majority. A model should not know its rating exists or be able to optimize behavior against it.

Ratings must include sample count, confidence/uncertainty, task difficulty, verification independence, recency/decay and topic specificity. Avoid large score shifts from tiny samples. No majority-derived label may be treated as ground truth. Provide a private, scoped API for agents to receive only the domain-relevant probabilistic reliability estimates, not unnecessary cross-domain profile data.

The rating's purpose is decision support: estimate likelihoods with uncertainty and guide where to investigate or which model is useful for a domain. It is not a truth oracle and must never be the sole selection or decision mechanism.

## 4. Decision Integrity Engine
An algorithmic checker, separate from the LLM deliberation, validates evidence relationships and machine-checkable claims. It is context-aware and does not equate formal presence with validity.
- Claims are atomized and traceable to speaker/source.
- Evidence contains exact repo path/line or symbol, commit/version/hash, test or calculation identifiers, and scope/assumptions.
- Verify quote existence and source version, citation-to-claim link, tests targeting the claimed behavior, type/contracts, dimensional/unit consistency, formal proof obligations when available, boundary conditions and machine-checkable constraints.
- Track repetition/no-progress, contradictions, retries and limits, plus evidence completeness in the final record.
- Preserve speaker attribution; never invent or paraphrase a participant's position as a claim they did not make.
- Abstract/non-code claims require a minimal reproducible example, model, pseudocode or explicit testable sequence when feasible.
- Claim statuses: verified, partially verified, hypothesis, unverified, refuted; preserve counterevidence and scope.

## 5. Evidence hierarchy and virtual validation
Evidence is typed, scoped and not treated as a universal ranking:
1. Physical experiment (if feasible, suitable, ethical/safe, and quality-controlled).
2. Independent empirical data/observation relevant to the claim.
3. Validated virtual/model result with applicability, assumptions, solver and uncertainty documented.
4. Formal proof (strong only for the propositions/assumptions actually covered).
5. Deterministic tests, contracts, dimensional/type checks and numerical calculations.
6. Model arguments, consensus and votes.
Ordering is context-dependent: a proof can outrank an experiment for a formal proposition, and an experiment may be weaker than a well-validated model if precision/measurement limitations are material. The engine must record the evidence's scope and limitations rather than blindly use a fixed ranking.

For most engineering problems, simulation/calculation is the practical final validation stage when physical experimentation is unavailable or unjustified. Do not label simulation as experimentally verified. Record "physical experiment not conducted"; update the result only when relevant new experimental data or observations arrive, even indirectly. Never assert that simulation confirms physical reality without model-validation evidence.

## 6. Practical feedback and outcome review
After a recommendation, the authorized agent may test feasibility, implement an approved bounded change, run deterministic tests, calculations, simulations, or experiments. Results return to deliberation as evidence. Compare initial predictions, votes and confidence with outcome evidence; update rating statistics only after outcome labels meet the independent-verification requirements. Record model validity, solver validity and result validity separately.

## 7. Virtual experiment workflow
For physical, chemical or multidisciplinary questions:
1. state hypothesis and variables;
2. specify parameters, assumptions, conditions and constraints;
3. select an existing model/solver or adapter;
4. check dimensions, boundaries and applicability;
5. select solver and version;
6. run bounded simulation/test and sensitivity/uncertainty analysis;
7. return evidence and limitations to participants;
8. allow bounded position/vote revision;
9. record provenance and experiment status.
Use existing physics, math, chemistry and solver facilities. No new simulation engine until audit identifies a capability gap.

## 8. Implementation feasibility / negative result protocol
If the agent cannot implement a consensus recommendation: preserve exact recommendation, identify current limitation, provide file/contract/calculation/log evidence, check alternatives, bound retries, prevent identical retry loops, and record unresolved/blocked status. Do not generalize an environment limitation into universal impossibility.

## 9. Competence test bench
Idle-time testing is bounded by task, token, cost, time and resource ceilings. Include independently scored domain tests, blind voting, critique validation, calibration, deterministic calculations and virtual experiments. Keep a held-out control set out of rating updates. Store task provenance, difficulty, labels and validation independence; don't run indefinitely or spend paid quotas without explicit budget.

## 10. Agent-facing rating interface
Expose only scoped domain reliability estimates, uncertainty, evidence counts, and rating version to authorized agents. Treat values as hints, not authority. Never reveal private ballots or ratings to participant models.

## 11. Session evidence record
Persist task/session IDs, model/version identifiers, round count, mode, atomic claims, critique, revisions, secret ballots in protected storage, aggregates, simple and weighted vote, uncertainty/sample reliability, predictions, calculation/test/simulation/experiment evidence, source commit/path references, consensus or dissent outcome, user decision and limitations. Models receive only the session-visible content, not ratings or private ballot records.

## 12. Staged implementation and acceptance
1. Audit reusable components and APIs; map each requirement to existing code or a gap.
2. Implement shared Claim/Evidence/Decision records and serialization.
3. Implement bounded Consensus/Critique protocol and termination outcomes.
4. Implement private independent ballots, aggregation and leakage tests.
5. Implement scoped ratings with uncertainty, sample-size guards, minority-correct credit, anti-contrarian incentive checks and held-out validation.
6. Implement algorithmic Decision Integrity checks and provenance.
7. Integrate existing mathematical/formal/physics/chemistry tools via contracts.
8. Implement outcome feedback and calibration update workflow.
9. Add bounded idle benchmark/test bench.
10. Integrate authorized agent interfaces.
11. Validate false consensus, minority-correct, majority-wrong, insufficient evidence, untested simulation, source mismatch, ballot leakage, repeated/no-progress, context-limited impossibility, and session-budget exhaustion.

No stage may be marked complete without task-level acceptance tests and evidence. Implement small additive increments, preserve current interfaces, and update IMPLEMENTATION_STATUS.md only when code is actually delivered.
## 13. Interdisciplinary Module Connections and Comprehensive Engineering Safety Assessment

### 13.1. Purpose and rationale
Scientific and engineering disciplines are not isolated. Real processes often depend on multiple domains simultaneously, with nonlinear, layered, and non-obvious interactions.

A design optimized for strength, mass, cost, energy consumption, or performance may be unsuitable for real-world use because chemical, biological, environmental, or other consequences were not considered.

Engineering Core should therefore evolve from isolated specialist modules into a system that can gradually form, expand, and use interdisciplinary connections. This is intended to identify consequences that cannot be seen from a single-discipline perspective.

For example, developing a robotic artificial muscle may require:
- Engineering: design, strength, service life, manufacturability.
- Physics: forces, dynamics, thermal conditions, energy.
- Chemistry: material composition, reactions, stability, toxicity.
- Biology: molecular mechanisms, biocompatibility, microbial growth.
- Mathematics: modelling, optimization, uncertainty analysis.
- Ecology: environmental impact, waste, lifecycle.

Connections should be discovered by the system, not depend solely on a user or model remembering to request another discipline.

### 13.2. Universal intermodule interaction architecture
Provide an architecture for multiple interaction patterns. Do not limit it to hard-coded pairs of modules. It must support new connections, disciplines, and complex collaborative workflows without rewriting the core.

Support:
1. Consultation requests between specialist modules.
2. Sharing evidence and data: calculations, research, observations, verified facts.
3. Coordinated analysis by multiple modules from different perspectives.
4. Event-triggered review, where one result automatically initiates another check.
5. Analysis chains, where one discipline's result becomes input to several others and results return to the shared analysis.
6. Mutual validation of assumptions, limitations, and conclusions.
7. Conflict detection for incompatible conclusions, assumptions, and uncertainties.
8. Dynamic discovery and invocation of additional disciplines as new factors emerge.

Connections must be extensible, versioned, and auditable. Each intermodule request and response must carry a task ID, context, input data, subject/design version, constraints, status, evidence, and result. Modules must not be forced into agreement; each retains the ability to report contradictions, insufficient data, or an unsupported conclusion.

### 13.3. Automatic detection of interdisciplinary analysis needs
Engineering Core should determine which knowledge domains a task requires. For a new material, consider not only mechanical properties but also potential hazardous reactions, harmful emissions under heat/wear/aging, moisture and microbial-growth conditions, human or animal exposure, environmental contamination, and degradation during use.

When a factor falls outside the current module's competence, initiate an appropriate cross-module request. This must work in reverse as well: chemistry, biology, or physics may trigger a review of the engineering design.

### 13.4. Required chemical assessment of engineering materials
When chemical properties matter for materials, coatings, liquids, polymers, composites, or similar objects, Engineering should invoke Chemistry as appropriate.

Assess composition and properties; known hazards and toxicology; reactivity and incompatibilities; corrosion and breakdown; aging/degradation/wear products; environmental releases; exposure pathways; and production, use, maintenance, and disposal conditions.

The objective is to identify hazards before recommending practical use.

### 13.5. Required biological assessment
Invoke Biology when biological exposure, biocompatibility, contamination, microbial growth, or interactions with living organisms may matter.

Consider molecular structure where relevant to function; surface properties and contamination retention; moisture, stagnant zones, and temperature; biofilm potential; cleaning, disinfection, and maintenance; exposure pathways for people, animals, and ecosystems; and evidence and uncertainty.

Biology must explain mechanisms, not merely flag risk. It must distinguish theoretical possibility, conducive conditions, confirmed growth of a specific organism, and demonstrated disease risk. Presence of certain substances alone does not establish pathogen presence or infection.

### 13.6. Molecular explanations, formulas, and mechanisms
Chemistry and Biology should explain molecular structure and component function at the appropriate level when needed, including structures, functional groups, bonds, interactions, component roles, reaction mechanisms, and relevant physicochemical conditions.

Use formulas, equations, reaction notation, quantitative models, and calculations when useful. Define variables and units; state assumptions; check dimensional consistency; explain what the formula establishes; state applicability limits; and distinguish calculated results from experimentally verified findings.

Formulas must clarify mechanisms and causality, not serve as decoration.

### 13.7. Comprehensive safety assessment
Where relevant, evaluate chemical, biological, physical, toxicological, environmental, operational, and human/animal impacts.

Consider normal operation and scenarios involving damage, overheating, wear, aging, contamination, repair, cleaning, and disposal. Significant risks should be able to trigger redesign, safer alternatives, additional testing, independent review, or restrictions/blocks on practical-use recommendations until material uncertainties are resolved.

### 13.8. User-facing risk explanation
A final engineering answer must not merely list substances, biological factors, metrics, or warnings. Explain each significant risk:
1. What was detected?
2. Why/how does it occur (mechanism)?
3. Under what conditions does it become significant?
4. Who or what could be affected?
5. What are the practical consequences?
6. How can it be reduced or eliminated?
7. How confident are we, and what sources, calculations, experiments, simulations, and limitations support that confidence?

Technical explanations, formulas, and mechanisms must be accompanied by plain-language consequences. Do not imply safety simply because a check did not detect a hazard.

### 13.9. Assessment statuses
Use clear statuses:
- Assessed within stated scope; no significant issue identified.
- Risk identified.
- Risk reduction or mitigation required.
- Further research or independent review required.
- Insufficient data.
- Not assessed.

“No risk identified” is not a guarantee of absolute safety.

### 13.10. Gradual evolution of the connection network
Start with core intermodule interfaces and essential connections, then gradually add disciplines, interaction types, methods, and evidence-sharing mechanisms.

Avoid chaotic connection growth, duplicated functionality, or uncontrolled module invocation. Consider connection utility, result quality, resource cost, repeated calls, and cycles. Interdisciplinary workflows must be controlled, resource-bounded, and auditable.

### 13.11. Implementation acceptance criteria
Implementation is acceptable when:
- Engineering Core detects when other disciplines are needed.
- The architecture supports varied interaction patterns and extensibility.
- Modules and connection types can be added without rewriting the core.
- Engineering tasks can automatically request Chemistry and Biology assessments.
- Intermodule results preserve provenance, versions, limitations, and uncertainty.
- Identified hazards can trigger design review.
- Chemical and biological mechanisms are explained accurately, with molecular structures/formulas as appropriate.
- User-facing results explain practical consequences.
- Safety claims cannot be justified solely by absence of warnings.
- Intermodule conflicts, errors, missing responses, and insufficient data remain visible.
- The architecture can gradually expand into a complex interdisciplinary network.

Core principle: build an evolving network of connected knowledge, not isolated tools, capable of accounting for consequences beyond a single discipline.
