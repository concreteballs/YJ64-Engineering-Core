# Mathematical Notation and Symbolic Workspace

## Purpose

YJ64 needs a shared mathematical language across every discipline. LaTeX is the primary human-readable notation and authoring format for equations, derivations, reports and technical documentation. It is not itself a numerical solver or a complete semantic model of an equation.

The mathematical workspace is a cross-cutting platform capability: marine, structural, thermal, electrical, control, robotics, aerospace and future discipline packs must be able to exchange, inspect, render and evaluate mathematical expressions without inventing incompatible notation systems.

## Architectural separation

Keep four responsibilities distinct:

1. **Authoring and source notation — LaTeX.** Preserve the exact source expression, macros, labels, equation numbering and document context. Support inline and display equations, aligned derivations, matrices, tensors, vectors, Greek symbols, integrals, derivatives, differential equations and piecewise expressions.
2. **Rendering — MathJax or an equivalent replaceable renderer.** Convert supported LaTeX/TeX notation into accessible browser output (HTML/CSS or SVG). Rendering is presentation only; a rendered formula is not proof that it is mathematically or physically valid.
3. **Semantic representation — structured expression model.** Where machine evaluation is required, parse a supported subset into a typed expression tree / intermediate representation. Preserve variable identity, operators, functions, domains, assumptions, units, dimensions, coordinate frames and links to source text. Keep the original LaTeX as an immutable source representation.
4. **Computation — replaceable math engines.** Use an isolated symbolic/numerical backend behind YJ64 contracts. SymPy is a strong first candidate for a Python symbolic-mathematics adapter, not a mandatory dependency of the kernel and not a replacement for specialist numerical solvers.

LaTeX, MathML, the semantic expression model and solver-native representations are related but not interchangeable. MathML may be used as an interchange/rendering representation where useful; retain the original LaTeX and the semantic model separately.

## Formal proof assistants and theorem-prover ecosystem

Formal mathematical proof is separate from formula rendering and computer algebra. YJ64 must provide a common, versioned integration contract for multiple proof assistants and automated reasoning engines rather than hard-coding one prover.

### Proof-assistant candidates

- **Lean 4 + Mathlib** — first candidate for the initial formal-mathematics pilot; interactive theorem proving, dependent type theory, extensive mathematical library and a small proof-checking kernel.
- **Rocq (formerly Coq)** — proof assistant based on the Calculus of Inductive Constructions; retain awareness of legacy Coq naming in projects and package metadata.
- **Isabelle/HOL** — higher-order-logic theorem proving and a mature mathematical library ecosystem.
- **Agda** — dependently typed programming and constructive formalization.
- **Metamath** — compact formal proof language and independently checkable proof corpus.
- **HOL Light and HOL4** — theorem-proving systems based on higher-order logic.
- **PVS** — specification and verification environment with a rich type system and proof support.
- **ACL2** — logic and theorem-proving environment with support for executable models and verification.

This is an extensible candidate list, not a claim that every system is integrated or that their logical foundations are interchangeable.

### Adjacent automated reasoning engines

Keep automated theorem provers, SAT/SMT solvers and computer-algebra systems as distinct adapter categories. Evaluate candidates such as Z3 and cvc5 for bounded proof obligations and constraint solving. Their output must not be mislabeled as a proof checked by a proof assistant's trusted kernel unless a verifiable proof certificate is produced and checked by an explicitly trusted checker.

### Common YJ64 proof integration contract

Each adapter declares engine identity and exact version/build; formal foundation and supported theories; input language and translation limitations; imported libraries and revisions; dependencies and licences; axioms, assumptions, hypotheses and admitted goals/placeholders; proof/checker result and diagnostics; resource limits and reproducibility metadata; proof artifact/certificate and validating checker/kernel; links to source equation/specification revisions, engineering model, variables, units, coordinate frames and provenance.

A result distinguishes: not attempted; translation failed; proof search incomplete/timeout; counterexample or failed obligation; proof term generated; proof checked by the named kernel; externally certified result; and engineering validation still outstanding.

Never merge distinct logics or silently translate between them. Cross-prover exchange requires explicit, reviewable translations or independently checkable certificates, with assumptions and lost semantics reported. Preserve original source and native proof artifacts.

### Engineering use cases and trust limits

Formal proof assistants can verify mathematical lemmas, algebraic identities, invariants, bounds, control/software properties, selected model properties and proof obligations generated from engineering specifications. They do not automatically prove that a physical model matches reality, that measurements are accurate, or that a manufactured object is safe. Physical validity still requires model applicability review, numerical verification, experiments and engineering qualification.

### Integration sequence additions

- Define a prover-neutral proof-obligation and result schema with explicit logic/foundation metadata.
- Implement Lean 4 as the first bounded pilot; do not make it mandatory for the core.
- Add adapter conformance tests and evaluate Rocq/Coq, Isabelle/HOL, Agda, Metamath, HOL Light/HOL4, PVS and ACL2 as independent integrations.
- Add optional SAT/SMT adapters as a separate category, including certificate-checking rules.
- Test negative cases: missing assumptions, untrusted axioms, admitted goals/placeholders, timeouts, failed translation, mismatched units and stale source revisions must never be reported as proved.
- Preserve native artifacts and allow multiple engines to independently check related obligations.

## Core capabilities

- Render equations consistently in project views, technical documents, reports, calculation sheets, logs and generated documentation.
- Preserve equation source, numbering, labels, references and derivation order.
- Provide a safe editor with preview, syntax diagnostics, supported-macro profile and accessible text alternatives.
- Support structured symbols and variables with names, descriptions, mathematical type, scalar/vector/matrix/tensor shape, domain, assumptions and source.
- Attach YJ64 typed quantities and dimensional metadata to variables and expression nodes. Validate dimensional consistency before accepting a formula for a physical calculation.
- Distinguish absolute temperatures from temperature differences, vectors from scalars, coordinate-frame-dependent quantities from frame-free values, and exact constants from approximations.
- Support symbolic operations where the chosen engine can justify them: substitution, simplification, differentiation, integration, algebraic equation solving, systems, matrix operations and supported differential equations.
- Support numerical evaluation through suitable numerical engines, with explicit tolerances, convergence status, precision, domain, solver settings and failure diagnostics.
- Link equations to physical models, component parameters, boundary conditions, solver inputs, calculated results, evidence and source references.
- Preserve assumptions and applicability limits; show whether a result is symbolic, approximate, numerical, experimentally fitted or externally supplied.
- Export equations in Markdown/LaTeX and appropriate document formats while retaining source and provenance.

## Safety, correctness and trust boundaries

- Never execute arbitrary LaTeX macros, embedded TeX code, Python or generated expressions as trusted code.
- Use a restricted, documented LaTeX math profile for rendering untrusted input; sanitize and resource-limit parsing and rendering.
- Parsing LaTeX into a computation tree must be explicit and fail closed on unsupported or ambiguous constructs. Do not guess operator precedence, implicit multiplication, variable meaning, units or domains.
- A formula that renders successfully is not thereby parsed, dimensionally valid, mathematically correct or physically validated.
- Symbolic equivalence and simplification are engine-dependent. Preserve the original expression and record transformations.
- Numerical answers must record precision, tolerances, convergence, solver version and input assumptions. Do not silently replace exact values with floating-point approximations.
- Dimensional analysis is necessary but not sufficient for physical correctness. Discipline packs remain responsible for constitutive laws, sign conventions, coordinate frames, boundary conditions and validation.
- A CAS result is not a substitute for numerical verification, experimental validation or engineering review.

## Candidate technology roles

- **MathJax 4:** preferred initial browser-rendering candidate for TeX/LaTeX, MathML and AsciiMath. It is a display engine, not a CAS. Its TeX input implements a supported subset rather than the complete LaTeX distribution; define and test the supported macro profile.
- **SymPy:** preferred first candidate for a Python symbolic mathematics adapter. Evaluate exact supported release, licence/dependencies, parsing boundary, operation coverage, performance and reproducibility before adoption. Keep it behind an adapter so other engines can be added or substituted.
- **Lean 4 + Mathlib:** preferred first proof-assistant pilot candidate, not an exclusive platform dependency.
- **Rocq/Coq, Isabelle/HOL, Agda, Metamath, HOL Light, HOL4, PVS and ACL2:** extensible proof-assistant evaluation catalogue; each requires its own adapter and conformance review.
- **Z3, cvc5 and related SAT/SMT engines:** optional automated-reasoning adapters, separate from proof assistants; proof claims require certificate validation by a trusted checker.
- **MathML:** optional structured interchange/rendering format. Do not treat presentation-oriented MathML as a complete semantic engineering model.
- **NumPy/SciPy and specialist solvers:** remain candidates for numerical computation where appropriate; symbolic algebra should not be forced into numerical workloads or vice versa.

Official references:
- MathJax documentation: https://docs.mathjax.org/en/stable/
- MathJax TeX/LaTeX input: https://docs.mathjax.org/en/stable/input/tex/index.html
- MathJax supported browser rendering: https://docs.mathjax.org/en/stable/web/start.html
- SymPy documentation: https://docs.sympy.org/
- SymPy equation-solving guidance: https://docs.sympy.org/latest/guides/solving/index.html

## Integration sequence

1. **Notation baseline:** define supported LaTeX math delimiters, macro profile, equation IDs/labels, source preservation and rendering tests.
2. **Rendering adapter:** integrate MathJax behind a replaceable presentation interface; test inline/display equations, matrices, aligned systems, Greek symbols, vectors, tensors, multiline derivations, malformed input and accessibility.
3. **Expression contract:** define a versioned, solver-neutral expression schema with typed symbols, operators, units/dimensions, domains, assumptions and provenance. Do not make LaTeX strings the only machine-readable representation.
4. **Dimensional validation:** connect expression variables to the existing Quantity/unit registry and reject inconsistent equations before physical evaluation.
5. **Symbolic adapter pilot:** evaluate and, if approved, connect SymPy for a narrow set of deterministic operations with isolated execution, resource limits and structured diagnostics.
6. **Numerical hand-off:** route numerical problems to appropriate numerical or discipline-specific solvers through existing solver contracts; record solver configuration and evidence.
7. **Engineering integration:** connect equations to discipline models, reports, project revisions, source documents and traceable calculation results.
8. **Proof-assistant framework:** define a prover-neutral proof-obligation/result contract; pilot Lean 4; then add independently versioned adapters for other proof assistants and SAT/SMT engines after conformance, trust and reproducibility checks.
9. **Expanded notation and domain packs:** add specialist notation/macros only with tests and documented support; preserve portability and graceful fallback when a renderer lacks a macro.

## Acceptance criteria

- The same stored LaTeX source renders consistently in supported project, document and report views.
- Original source is preserved byte-for-byte or as an immutable versioned artifact; rendering never overwrites it.
- Unsupported macros and malformed expressions produce visible diagnostics rather than silently altered equations.
- A parsed expression retains typed symbols, operators, assumptions, units/dimensions and provenance.
- Dimensional mismatch is detected before physical evaluation.
- Symbolic and numerical backends are replaceable and optional; the kernel remains usable without them.
- Every computed result records expression revision, engine/version, settings, assumptions, diagnostics and validation evidence.
- Tests distinguish rendering success, parse success, dimensional validity, mathematical verification and physical validation.

## Current status

Planned architectural capability. This document defines the target and candidate technologies; it does not claim that MathJax, a LaTeX parser, a symbolic engine, a proof assistant adapter or a mathematical editor is already integrated into YJ64.


## Mathematical-to-physical verification and independent model checking

The mathematical workspace must support a traceable path from a formal hypothesis to a physical/engineering model and, where available, comparison with measurements. This is a cross-disciplinary workflow, not a claim that a theorem prover can validate nature.

- Represent each hypothesis and model as versioned typed expressions/specifications with explicit variables, units, dimensions, frames, domains, assumptions, boundary/initial conditions and provenance.
- Generate reviewable proof obligations for independent proof-assistant adapters. Compare results only after establishing that both systems formalized equivalent statements and compatible assumptions; preserve each native proof and trusted checker. Two systems using the same mistaken specification are not independent confirmation.
- Use CAS and numerical engines for symbolic transformations, parameter sweeps, sensitivity, uncertainty propagation, counterexample search and numerical consistency checks. A failure to find a counterexample is not proof.
- Translate a reviewed semantic model into discipline-specific simulation inputs through validated adapters. Record model reductions, approximations, discretization, solver settings, convergence and applicability bounds.
- Compare predictions with independent analytical references, public observations and physical experiments. Keep formal proof, numerical verification, empirical fit, experimental validation and engineering qualification as separate evidence states.
- Preserve competing hypotheses, negative results, falsifying observations and model revisions; do not silently tune parameters against the same dataset used for final validation.

Initial adjacent application: celestial mechanics and cosmological hypothesis testing. Detailed requirements: CELESTIAL_MECHANICS_AND_COSMOLOGY.md.
