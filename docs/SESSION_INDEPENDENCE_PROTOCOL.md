# YJ64 — Session Independence Protocol
Status: **Approved architectural requirement; runtime implementation planned**
Repository: `concreteballs/YJ64-Engineering-Core`
Authorized branch: `main`

## 1. Purpose and non-negotiable rule

The Autonomous Engineering Cycle must not depend on the lifetime, message limit, context window, browser tab, device connection, or existence of any ChatGPT UI conversation.

**The durable task record is the source of truth. A model conversation is a temporary execution session only.** Ending a chat, starting a new model request, exhausting a context window, restarting a worker, or reconnecting after an outage must not erase task state or require the user to press “New chat”.

This protocol does not claim that the current ChatGPT conversation can resume itself, nor that the cloud worker is already deployed. The cloud agent will use a separately configured model API/provider and persistent orchestration.

## 2. Separation of responsibilities

- **User conversation:** interface for instructions, approvals, questions and notifications. It is not the task database or worker runtime.
- **Orchestrator:** selects eligible tasks, manages leases, context budgets, checkpoints, retries, model calls and stop conditions.
- **Durable task store:** authoritative task status, requirements, dependencies, attempts, decisions, approvals, budget, artifact references and next action.
- **Checkpoint store:** versioned, recoverable snapshots at safe boundaries. Checkpoints reference evidence and artifacts; they do not replace them.
- **Model-call session:** one bounded request/response execution. It can be discarded and replaced at any time.
- **Diagnostic event stream:** records session starts/ends, context rollover, checkpoint creation, recovery, retries, uncertain outcomes and stop reasons with task/correlation identity.

## 3. Durable task state

Every autonomous task must have a stable `task_id` and persist at least:

- task specification/version, parent/dependency IDs and current state;
- current stage and last completed safe boundary;
- completed actions and their verified outcomes;
- pending actions and the next permitted action;
- decisions, assumptions and unresolved questions, each linked to evidence or explicitly marked as a hypothesis;
- repository, branch, commit, deployment, workflow and artifact identifiers;
- model/provider/model-version and model-call IDs for audit;
- attempt/retry counters, idempotency keys and uncertain-operation markers;
- approvals, restrictions, safety gates, time/token/cost budgets and stop conditions;
- checkpoint sequence/version, creation time and integrity hash.

The task store is authoritative. Chat transcripts, model summaries, worker memory and logs may assist retrieval but must never be the only copy of essential state.

## 4. Context budget and automatic rollover

1. The orchestrator tracks estimated input/output token use and the provider's context limit.
2. It reserves a safety margin for the model response, tool results and checkpoint generation.
3. Before the safe context threshold is reached, it stops accepting additional broad context and asks the current model session to produce a structured continuation checkpoint.
4. The orchestrator validates and durably stores that checkpoint, then records a `context_rollover` diagnostic event.
5. It opens a fresh model API request/session and reconstructs the minimum task-scoped context from the task record, latest valid checkpoint, referenced source documents and verified artifacts.
6. The new request continues from the saved next action. No user interaction or ChatGPT UI “New chat” action is required.
7. If checkpoint validation or persistence fails, the orchestrator must not discard the previous valid checkpoint or mark the task advanced. It retries within limits or stops visibly as blocked.

A checkpoint must distinguish verified facts, hypotheses, decisions, completed work, pending work and missing evidence. It must preserve exact identifiers and links rather than paraphrasing away critical technical detail.

## 5. Provider limits, rate scheduling and chunked input

The companion [Model Provider Limits and Chunked Request Protocol](MODEL_PROVIDER_LIMITS_AND_CHUNKED_INGESTION.md) is mandatory for every model adapter. The orchestrator must detect and classify rate limits, context overflow, oversized payloads, concurrency limits, transient failures and permanent quota/authentication/configuration errors. It must parse provider retry/reset hints, persist a delayed retry time and release the worker rather than wait indefinitely or blindly repeat the same request.

Large inputs must use a durable ordered chunk manifest with stable IDs, per-chunk and total hashes, idempotent acknowledgements and verified reassembly. A model in accumulation mode must be explicitly instructed not to analyze until a verified FINALIZE marker. Stateless API calls do not accumulate context by implication: the orchestrator must reassemble the complete payload itself or use a provider-supported continuity/file mechanism. Partial or integrity-failed input must never be executed.

## 5. Checkpoint and recovery semantics

- Write checkpoints atomically or with an append-only version plus a verified current pointer.
- Never overwrite the last known-good checkpoint before the new one is validated and committed.
- Use monotonically increasing checkpoint sequence numbers and integrity hashes.
- A worker claims tasks with an expiring lease. Lease renewal and recovery are explicit state transitions.
- On restart, the worker reloads the durable task and latest valid checkpoint, verifies referenced artifacts/commits, and resumes from the last safe boundary.
- A model response received but not durably recorded is an uncertain outcome. Reconcile using provider request IDs, task idempotency keys and observed external state before retrying.
- Repository writes, queue transitions and external actions must be idempotent or have a read-after-uncertain-outcome reconciliation path. Never blindly repeat a possibly completed side effect.
- Corrupt or missing checkpoints produce an explicit recovery failure and diagnostic evidence; the system must not silently start the task from scratch.

## 6. State machine

Minimum task lifecycle:

`queued → leased → running → checkpointed → running`

Terminal or controlled states:

- `completed` — all acceptance checks passed and evidence is persisted;
- `blocked` — required input, permission, dependency or evidence is unavailable;
- `paused` — operator pause has been acknowledged at a safe boundary;
- `cancelled` — authenticated cancellation has been applied;
- `failed` — bounded recovery/repair policy is exhausted or an unrecoverable invariant failed.

A context rollover is a model-session transition, not a task-state reset. It must not reset attempt counters, budget consumption, approvals or safety restrictions.

## 7. Human control and safety

Automatic continuation is allowed only within the task's pre-authorized scope. The cycle must stop for human approval when required by policy, including new permissions, secret exposure, paid services/credits, purchases, external data sharing, destructive changes, ambiguous requirements, and consequential physical operations. Safety interlocks and emergency stops cannot be bypassed by a new model session or checkpoint.

Pause, resume, cancel and kill-switch controls must be authenticated and recorded. A checkpoint does not grant new authority.

## 8. Required diagnostic events

Emit correlated events for at least:

- `task.claimed`, `task.resumed`, `task.checkpointed`, `task.completed`, `task.blocked`;
- `model_session.started`, `model_session.completed`, `model_session.interrupted`;
- `context_rollover.started`, `context_rollover.completed`, `context_rollover.failed`;
- `worker.lease_expired`, `worker.recovered`;
- `operation.outcome_uncertain`, `operation.reconciled`, `operation.retry_suppressed`.

Events use the shared `yj64.diagnostic.v1` contract and carry task/correlation identity, checkpoint sequence, provider request ID where safe, and commit/artifact references. Secrets and raw credentials must never enter checkpoints or diagnostics.

## 9. Acceptance tests — mandatory before calling the cycle autonomous

1. **UI independence:** close the browser/ChatGPT UI and disconnect the phone; the cloud worker continues an already queued task.
2. **Context rollover:** force a task to cross a deliberately small test context budget; it creates a checkpoint and continues through a new model-call session automatically.
3. **No transcript dependency:** disable access to the previous model conversation; the new session resumes correctly from durable task state and referenced artifacts.
4. **Worker restart:** terminate the worker after a checkpoint; a replacement worker resumes from the last valid checkpoint.
5. **Crash-window test:** interrupt before checkpoint commit, after checkpoint commit, and after model response but before response persistence; verify safe recovery.
6. **Idempotency:** replay queue events and model-call completion events; no duplicate task completion or repository side effect occurs.
7. **Checkpoint integrity:** corrupt the newest checkpoint; the system falls back only to a verified prior checkpoint or stops visibly without data loss.
8. **Budget continuity:** context rollover does not reset total task, time, token, repair or cost budgets.
9. **Approval continuity:** a fresh model session cannot bypass a pending approval or previously imposed safety restriction.
10. **Evidence continuity:** final output retains the exact commit, CI run, artifacts, diagnostics and validation evidence across all sessions.

Until these tests pass against the deployed worker and durable store, the capability remains planned/partially implemented. Unit tests for checkpoint utilities alone are not proof of autonomous continuity.

## 10. Implementation order

1. Finalize a versioned task/checkpoint data contract and state-transition invariants.
2. Verify durable queue persistence and restart recovery against the real database.
3. Implement atomic checkpoint persistence, integrity validation and retention.
4. Implement provider-neutral model-session adapter with request IDs, context-budget accounting and bounded output.
5. Implement automatic checkpoint → fresh request → resume orchestration.
6. Implement lease recovery, uncertain-outcome reconciliation and idempotent side-effect boundaries.
7. Add diagnostic events and operator status for session transitions and recovery.
8. Run the acceptance tests above, including forced context rollover and worker crash injection.

