# YJ64 Roadmap Completion Auditor Protocol

Status: Approved requirement for the Autonomous Engineering Cycle
Repository: concreteballs/YJ64-Engineering-Core
Branch: main

## Purpose
On every cycle, independently audit the roadmap against the repository's current implementation so the cycle does not repeat work simply because a roadmap checkbox/status was not updated, or because an LLM incorrectly believes a task is unfinished or complete.

## Mandatory per-cycle gate
Run this audit before selecting or enqueueing the next engineering task, and again before marking any task complete:
1. Load the authoritative execution roadmap, IMPLEMENTATION_STATUS.md, strategic plan/checklists, relevant acceptance criteria, and the latest durable task/checkpoint state.
2. Inspect current repository evidence at the target commit: source, tests, workflow/configuration, migrations, docs, and relevant CI runs/artifacts. Use targeted inspection and search; do not assume file presence equals implementation.
3. For every roadmap item or subtask, classify independently as:
   - verified_complete
   - partially_implemented
   - not_implemented
   - uncertain_or_conflicting
4. Record evidence references (commit SHA, exact paths and symbols/line ranges where possible, test IDs and CI run URLs). Separate implementation evidence from test evidence and deployment/runtime evidence.
5. If an item is already implemented to its acceptance criteria, suppress duplicate execution and report a stale roadmap status. Recommend or prepare a status-only reconciliation that preserves the roadmap's intended scope and limitations.
6. If implementation is partial, derive a task only for the missing acceptance criteria. Do not regenerate or redo completed portions.
7. If evidence is insufficient or conflicting, mark uncertain_or_conflicting and request bounded verification. Do not automatically claim completion or create a duplicate implementation task.
8. Re-run the audit after changes and before selecting the next task to detect regressions or a stale status.

## Evidence and decision safeguards
- The roadmap's completion marker is not implementation proof; code presence alone is not proof either.
- LLM assessment is advisory and must not be sole authority. Prefer deterministic checks and tests, and use independent review/second pass for important claims.
- Use task-specific acceptance tests and CI results for behavioral claims. For deployed/live claims, require live verification; a passing unit test does not prove deployment.
- Completion requires evidence satisfying the acceptance criteria, not a generated summary, planned design, stub, interface, or placeholder.
- When the audit cannot confidently decide, fail closed to uncertain and do not suppress required work indefinitely; create a bounded verification task rather than an implementation duplicate.
- Never delete, weaken, or silently rewrite requirements to make an item appear complete.
- Preserve the distinction between verified prototype, partial capability, production/deployed integration, and independently validated capability.

## Plan reconciliation
The auditor must emit a durable discrepancy report with:
- roadmap item ID/title and source location;
- current roadmap status;
- auditor classification and confidence/reason;
- evidence references;
- recommended action (status reconcile, verify, implement remaining criteria, or no action);
- timestamp, audited commit, and auditor version.

A roadmap status update may be proposed or applied only when its evidence is reviewable and acceptance criteria are satisfied. Keep an auditable change history. Do not let an LLM rewrite the roadmap wholesale.

## Task selector integration
The selector must consume the auditor's reconciled task map. It must exclude verified-complete tasks, avoid duplicates already queued/in progress, respect dependencies and budget/authorization limits, and select the next eligible incomplete task. If the auditor reports unresolved ambiguity on a candidate, choose a bounded verification task or stop as blocked.

## Acceptance tests
- Roadmap marks an item incomplete while code and required tests already satisfy its acceptance criteria: auditor detects it, suppresses duplicate work, reports stale status.
- Roadmap marks complete but implementation/test evidence is absent or broken: auditor detects the discrepancy and does not trust the marker.
- Partial implementation: generated task covers only missing criteria.
- Conflicting/weak evidence: item remains uncertain and is routed to verification.
- Repeated audit on unchanged commit produces stable classifications and does not enqueue duplicates.
- After implementation changes, audit runs again before selector advances.
- Auditor failure or unavailable evidence: cycle fails closed, does not blindly execute an item, and records the reason.

## Operating rule
The roadmap auditor is a separate control/checking responsibility from the LLM task selector. It guards against omissions and confusion but does not replace human approval gates, CI, or the existing zero-cost/provider-budget and repository-scope restrictions.
