# YJ64 Engineering Core — development history

This file records implementation milestones, decisions, verification evidence and known limitations. It supplements, and does not replace, the unified plan and implementation ledger.

## 2026-11-16 — typed solver integration and robotics architecture
- Commit: `7bf5075496334c05708f66b2fde0f353832ea509`.
- Added the typed solver request/response boundary for quantities, coordinate frames, loads, boundary conditions and component dependencies.
- Added an end-to-end integration probe covering dispatch, persistence, provenance and stale-result propagation.
- Added modular biomechanical robotics and artificial-muscle material discovery architecture documents.
- CI run [43913838276](https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/43913838276): **success**. The workflow completed unit tests, FEM/CAD integration tests and 12 m yacht-hull demonstration artifact generation.
- The reference typed solver is a software integration probe, not a physical solver.

## 2026-11-16 — first typed-kernel external FEM adapter
- Connects the typed shared-kernel request to the existing CalculiX T3D2 axial-truss runner.
- Enforces explicit root/tip targets, dimension-checked SI inputs, world-frame force transformation, axial-only loading and tip application-point validation.
- Scope is intentionally one straight axial member; general mesh mapping, distributed loads, multi-member structures and other structural modes remain out of scope.
- Automated tests use a controlled solver double for adapter mapping. The workflow's existing real CalculiX test separately checks execution of the installed external solver.
- CI result for this new commit is pending verification; do not infer success from the preceding run.

## 2026-11-16 — typed CalculiX adapter import correction
- Initial CI run [43916042366](https://github.com/concreteballs/YJ64-Engineering-Core/actions/runs/43916042366) failed during test-module imports because eagerly re-exporting the adapter from the `physics` package created a cycle while `typed_solver` imported shared kernel types.
- Correction: keep the typed adapter available from the top-level public package and its explicit module path, but do not import it eagerly from `physics/__init__.py`. This preserves the shared-kernel import direction.
- Re-run required; no passing result is claimed until observed.
