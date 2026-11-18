# Browser-Agent Feedback Bridge — GitHub Autonomous Cycle Implementation Plan

Status: Planned; first deliverable is the protocol contract
Repository: concreteballs/YJ64-Engineering-Core
Branch: main

## Boundary
The browser agent is an external observer/executor that watches GitHub Actions, inspects available test environments and reports evidence. ChatGPT/engineering worker selects and implements roadmap tasks. The browser agent does not implement a second consensus/rating/round-supervision engine; it may send a case to an existing user-controlled council when requested. A browser-chat interaction is a transport channel, not durable project memory.

## Proposed feedback loop
1. Engineer reads reconciled roadmap and repository state, selects one bounded task and commits a change.
2. CI runs against the exact commit.
3. Browser agent observes run completion, verifies run/attempt/commit identity, checks whether test files or an executable test environment are available, and executes only authorized tests in an isolated/virtual environment when possible.
4. Agent sends a typed evidence report to the durable bridge: run status, commit, executed tests, outcomes, safe log excerpts, test-environment limitations and whether next-task advancement is safe.
5. Cycle worker validates the message and cross-checks GitHub evidence itself. Agent assertions alone never mark tasks complete.
6. If CI fails, worker schedules a bounded diagnosis/repair task using exact logs and source commit. If CI is green and acceptance criteria are satisfied, it audits roadmap completion and advances. If uncertain, it requests targeted verification or blocks.
7. If the browser agent cannot decide, it may submit a council request with exact question, claims, evidence and desired response; the council's final outcome is returned as structured data. Do not relay entire chat history unnecessarily.
8. At the project goal, browser agent runs the final acceptance suite and reports final evidence; the cycle stops, writes a final protocol, and does not self-restart.

## Message transport design
Use GitHub durable artifacts/files with a versioned envelope, request_id, session/task/run/attempt/commit identity, type, created/expiry timestamps, payload hash, state, and idempotency key. Avoid a single mutable mailbox that can lose or overwrite concurrent messages. Use immutable messages plus a durable state transition/acknowledgement record or an existing queue abstraction; audit the current Postgres queue and private artifact storage before adding tables.

Suggested message categories: ci_observation, test_report, verification_request, verification_response, council_request, council_result, blocked_notice, cycle_complete. Keep payloads bounded, sanitize secrets, treat logs and agent messages as untrusted data, validate all IDs and scope, and retain links rather than duplicating large log bodies.

## Guardrails
- Exact run/attempt/commit and authorized repository/workflow/branch must match.
- Deduplicate by request/event ID; reject stale or mismatched messages.
- Test execution is sandboxed, time/resource bounded, read-only by default; no external effects, secrets, paid requests or physical actions.
- The agent cannot change plan/roadmap completion based on its own assertion. CI and task-specific acceptance evidence are cross-checked.
- Repair attempts, agent requests, council calls, token/cost/time and maximum tasks are bounded; no identical retry without changed evidence.
- Completed cycle cannot restart itself; final status must be durable.
- When agent/council evidence is contradictory or incomplete, route to verification or blocked; fail closed.

## Step-by-step delivery
1. Audit and map current event/task/checkpoint, artifacts, CI ingestion and worker code; identify reusable queue/store and external browser-agent boundary. This has started as the current repo inspection.
2. Specify envelopes and lifecycle for agent request/response, identity, hash, state, expiry, deduplication and acknowledgements.
3. Implement durable bridge primitives using existing queue/artifact infrastructure where possible, no redundant database table unless audit proves necessary.
4. Implement report validator to enforce repository, branch, workflow, run/attempt, commit identity and evidence fields.
5. Integrate CI observer path: only completed exact run, capture validated metadata and bounded logs/test evidence; create request only for tests/verification not available to existing workers.
6. Integrate worker continuation: verified success advances via roadmap auditor; failure creates bounded repair/diagnosis; ambiguity requests targeted check/council or blocks.
7. Add browser-agent instruction/prompt contract (if its host supports files/skills): narrow instructions, task-scoped messages, no infinite chat, no self-restart, write structured report to bridge, never leak model ratings/secret votes.
8. Test lifecycle and adversarial cases: duplicate/stale messages, wrong commit, spoofed result, missing evidence, redacted logs, timeout, repeat failures, council non-consensus, budget exhaustion, completion terminal state.
9. End-to-end acceptance: browser observation → verified message → worker decision → next task/repair → exact commit CI → terminal stop. Do not claim operational until tested end-to-end.

## Current implementation checkpoint
The versioned envelope schema and initial validation primitives now exist: schema version, allowlisted repository/branch, message type, ID, task/run identity, commit SHA, timestamps/expiry, payload object, and payload SHA-256 integrity. The validator rejects unknown fields, invalid identities, expired messages and tampered payload hashes. This is not yet durable message storage, browser control, or a live feedback loop; CI validation is pending.

## Immediate first step
Protocol/schema and envelope validation have been delivered as an additive foundation. Next audit the current queue and artifact store to decide how immutable messages and acknowledgements can reuse durable storage. Do not claim browser-agent integration until the end-to-end acceptance sequence passes.
