# YJ64 — Model Provider Limits and Chunked Request Protocol
Status: **Approved requirement; partially implemented durable foundations, provider adapters and live transport still planned**
Repository: `concreteballs/YJ64-Engineering-Core`
Authorized branch: `main`

## Runtime implementation status

Implemented foundations include provider failure classification and durable attempt metadata; explicit quota-block reasons and reset timestamps; bounded, idempotent quota recovery; rolling RPM/TPM/input/output/concurrency admission; durable provider/model/endpoint profiles; shared quota scopes across models; profile validity deadlines; atomic request reservations keyed by stable idempotency keys and bound to exact request-payload SHA-256; database-clock rate-window decisions; separate request-body byte ceilings; task and global daily/monthly token/cost/request-count budgets plus absolute task deadlines; bounded capacity deferrals that do not consume model retry attempts; pending-task deadline expiry; lease renewal; and conservative quarantine of ambiguous provider sends. Provider reservations track estimated/actual usage and cost. A sent request with no provider response is retained as `unknown`, not blindly retried or treated as completed. A successful provider response must first be persisted as a durable artifact and referenced by its reservation; a task cannot complete while reservations remain unresolved.

Chunk foundations include deterministic token-counter-driven splitting; stable chunk IDs; per-chunk and total SHA-256 checks; durable manifests, chunks and acknowledgements; and integrity-checked assembly before a payload can become `ready_for_model`. Stateless endpoints must receive one fully reassembled request; independent API calls are not treated as accumulating context.

Supabase migrations `0007`–`0017` for provider profiles, shared quota scopes, payload identity, body-size limits, capacity deferrals, cost-confidence tracking and ambiguous-request reconciliation are deployed. RLS is enabled; anon/authenticated have no table grants; service_role has the required server-side grants. The security advisor reports informational `RLS enabled, no policy` findings for these private tables; this is intentional because direct client roles have no grants and access is reserved for the trusted server role.

A provider adapter interface contract is now defined in `automation/provider_adapters.py`; it binds requests to exact serialized-body hashes, requires model-specific token counting, declares idempotency/lookup capabilities and requires durable response artifacts. It is not a live adapter.

Admission fails closed until at least one explicit global daily/monthly usage ceiling is configured. No provider profiles or global budget rows are currently seeded, so the request-admission path cannot yet send model calls.

Still not implemented: provider-specific API adapters and live limit/pricing discovery; initial verified profile and budget configuration; automatic scheduler invocation of quota recovery, reservation expiry and provider admission; provider-specific rate-window semantics/tokenizers/body-size ceilings; provider-specific adapters that can perform authoritative lookup and produce trusted reconciliation evidence; remote chunk transmission; service-role application round-trip tests; and end-to-end model execution gated on FINALIZE. No worker is running.


## 1. Purpose

The autonomous cycle must treat provider limits as normal, observable scheduling constraints—not as unexplained failed model calls. It must never wait indefinitely for a response that will not arrive, silently archive a rate-limit error, or repeatedly resend an oversized request unchanged.

This protocol complements [Session Independence Protocol](SESSION_INDEPENDENCE_PROTOCOL.md). Provider calls are bounded, replaceable sessions; task state, request payloads, chunk manifests, retry schedules and budgets are durable.

## 2. Limits to discover and track

For each provider, account/project, model and endpoint, maintain a capability/limit profile with source and observation time. Track separately:

- maximum input/context tokens per request;
- maximum output tokens per request;
- requests per minute (RPM) and tokens per minute (TPM);
- daily/monthly request or token quotas where exposed;
- concurrent request limits;
- payload/body-size limits;
- provider-specific batch, file and caching limits;
- model availability, account tier and endpoint-specific restrictions.

Limits can differ by model, endpoint, account tier and time. Do not hardcode one provider's limits as universal. Prefer official response headers, structured error bodies and current provider metadata. Treat learned limits as observations with timestamps and confidence, not permanent facts.

The scheduler maintains a conservative local rate budget and reserves capacity for retries and completion. It accounts for input and output tokens separately where the provider does so.

## 3. Detect and classify outcomes

Every model request has a durable request ID/idempotency key, provider/model identity, attempt number, start/deadline, estimated input/output tokens and task/correlation IDs.

The adapter must distinguish at least:

- **Rate limit / quota window:** HTTP 429 or provider-specific equivalent; parse `Retry-After`, reset headers and structured error code. Distinguish short RPM/TPM throttling from daily/monthly quota exhaustion.
- **Request too large:** HTTP 413 or explicit context/input-token limit error. Do not retry the same payload unchanged.
- **Context overflow:** explicit prompt/context token limit rejection. Rebuild with smaller context or checkpoint and continue.
- **Transient provider/network error:** timeout, connection reset, 408 and retryable 5xx; reconcile uncertain completion before retrying.
- **Concurrency limit:** reduce in-flight requests and schedule a later attempt.
- **Permanent request/configuration error:** invalid model, malformed payload, unsupported feature, authentication/permission or billing/quota-disabled state. Do not loop blindly; block and surface a precise safe reason.
- **Unknown error:** preserve safe structured evidence and classify as unknown; use bounded conservative retries only where outcome is safe.

Record HTTP status, provider error code/type, request ID, retry/reset hints, response headers allowlist, latency and safe diagnostic message. Never persist API keys, authorization headers, raw credentials or unredacted provider payloads. Do not discard the error after logging it: it must drive an explicit scheduler state transition.

## 4. Scheduling, waiting and retry policy

1. Parse provider retry hints and calculate the earliest permitted retry time.
2. If no reliable hint exists, use bounded exponential backoff with jitter and a provider-specific ceiling; do not hammer the endpoint.
3. Persist `next_attempt_at`, failure class, retry count and last observed reset window in the durable task/request record.
4. Release the worker lease or schedule a delayed job. Do not hold a worker thread sleeping for a long rate-limit window.
5. Resume automatically when the scheduler says capacity should be available, then re-check current limits before sending.
6. Update the local rate budget from successful calls and observed throttling. Reduce concurrency or request size when repeated throttles occur.
7. Respect per-task and global attempt, elapsed-time, token and cost ceilings. Daily/monthly hard quota exhaustion becomes `blocked` until reset or an authorized provider/configuration change; do not spin.
8. If the provider accepted a request but the response was lost, reconcile by provider request ID/idempotency key where supported. Never assume timeout means the model did not execute.

Required request states include `queued`, `sending`, `accepted`, `rate_limited`, `retry_scheduled`, `too_large`, `awaiting_chunks`, `assembling`, `completed`, `blocked`, and `failed`. State transitions and diagnostic events must be durable.

## 5. Adaptive request sizing and chunk manifest

When a request is too large, or predicted to exceed a safe budget:

1. Estimate tokens with the provider's tokenizer when available; otherwise use a conservative estimate and safety margin.
2. Choose a chunk size below the current input budget, reserving space for instructions, manifest, tool results and output.
3. Split at semantic boundaries (document/section/paragraph/code block/record) where possible. Preserve exact source text and ordering; never silently truncate or omit content.
4. Create a durable manifest containing `task_id`, `payload_id`, protocol version, total chunk count, ordered chunk IDs, per-chunk content hash, total content hash, encoding, estimated tokens, source/artifact references and assembly policy.
5. Persist every chunk before transmission. Retries resend only missing/unacknowledged chunks using stable chunk IDs and idempotency keys.
6. Validate each acknowledgement against payload ID, chunk index/count and hash. Duplicate chunks are idempotent; out-of-order chunks are stored by index and never treated as complete.
7. The assembler verifies that all chunks are present exactly once logically, indices are contiguous, each hash matches and the reconstructed full payload hash matches the manifest.
8. Only after full verification may the request transition to `ready_for_model` and the model be instructed to begin the task.

Chunk boundaries should retain useful semantic context. Optional small overlap is allowed only when declared in the manifest and excluded from the canonical reassembled payload hash; do not create ambiguous duplicate source text.

## 6. Explicit accumulation protocol for models

For providers/endpoints that support a persistent conversation or file-backed accumulation, send a clear protocol envelope with every part. A representative instruction is:

```text
YJ64 CHUNKED INPUT — ACCUMULATION MODE
task_id: <stable task ID>
payload_id: <stable payload ID>
protocol_version: 1
chunk_index: <1-based index>
chunk_count: <total count>
chunk_sha256: <hash>
total_payload_sha256: <manifest hash>

Do not analyze, solve, summarize, modify, or execute the task yet.
Treat this message as an input fragment only.
Store/retain it as part of the ordered payload if this endpoint supports continuity.
Acknowledge receipt with payload_id, chunk_index and verified chunk hash.
Wait for all chunks and the explicit FINALIZE marker.
If a chunk is missing, duplicated with conflicting content, out of order, or hash-invalid, request retransmission and do not begin work.
```

The final message contains an explicit `FINALIZE` marker, expected chunk count and total payload hash, plus the task instruction. The model may begin only after verifying completeness and integrity.

**Critical provider-neutral rule:** a sequence of independent stateless API calls does not automatically accumulate context inside the model. If the endpoint cannot guarantee conversation/file continuity, the orchestrator—not the model—must assemble the complete verified payload from durable storage and submit it as one fitting request, or use a provider-supported file/batch mechanism. Never claim the model has received the full text merely because all individual chunk calls returned HTTP success.

For payloads that still exceed a model's context window after assembly, use retrieval/section-based task decomposition with explicit dependencies and checkpoints. Do not force the full source into one prompt.

## 7. Diagnostics and operator visibility

Emit common `yj64.diagnostic.v1` events for at least:

- `model.request.queued`, `model.request.sent`, `model.request.accepted`;
- `model.rate_limit.detected`, `model.rate_limit.retry_scheduled`, `model.rate_limit.recovered`;
- `model.request.too_large`, `model.context_overflow.detected`;
- `model.payload.chunked`, `model.chunk.sent`, `model.chunk.acknowledged`, `model.payload.assembled`, `model.payload.integrity_failed`;
- `model.request.blocked`, `model.request.failed`, `model.request.reconciled`.

Include task/correlation/request/payload IDs, provider/model, chunk sequence, safe error class/code, HTTP status, retry time, observed limit window and estimated token counts. Redact secrets and sensitive content. Operator status must show why the agent is waiting, when it is scheduled to retry, what has been transmitted, what remains, and whether the complete payload has been verified.

## 8. Safety and correctness invariants

- No infinite retries, indefinite waits or unbounded chunk counts.
- No repeated identical oversized request after a deterministic size rejection.
- No task execution on partial, missing, conflicting or hash-invalid input.
- No reliance on model memory across independent API calls unless provider continuity is explicitly guaranteed and verified.
- No reset of task budgets, permissions, approval state or safety restrictions during retry/chunking.
- Rate-limit recovery never bypasses authentication, billing, user approval or provider terms.
- Sensitive data is redacted from diagnostics; chunk payload storage follows access controls, retention and encryption policy.
- A permanent quota/billing/auth issue is surfaced as blocked with a clear reason, not hidden behind repeated retries.

## 9. Mandatory acceptance tests

1. Simulated 429 with `Retry-After`: agent records the limit, schedules a delayed retry and does not block a worker by sleeping.
2. Simulated TPM/RPM reset headers: scheduler waits until the earliest safe time and rechecks capacity.
3. Daily quota exhausted: task becomes visibly blocked; no rapid retry loop.
4. Simulated 413/context overflow: payload is split adaptively; unchanged oversized request is not resent.
5. Chunk delivery out of order, duplicate and retry: canonical assembly remains correct and idempotent.
6. Missing/corrupt chunk or wrong total hash: model execution is prevented and retransmission is requested.
7. Accumulation-capable endpoint: model is explicitly told to wait until FINALIZE and acknowledges each verified part.
8. Stateless endpoint: orchestrator reassembles from durable storage and submits a complete fitting request; tests prove no false assumption of model-side accumulation.
9. Provider timeout after possible acceptance: uncertain outcome is reconciled before duplicate execution.
10. Retry/chunk rollover preserves task, time, token, cost and approval budgets and emits diagnostic events.
11. A permanent invalid-model/authentication/billing error is classified and surfaced without infinite retries.
12. End-to-end test verifies that the model begins work only after complete payload integrity validation.

Until these tests pass against real provider adapters, rate-limit detection, scheduling and chunked accumulation remain planned capabilities, not deployed functionality.

## 10. Implementation order

1. Define provider-neutral error, rate-limit and request-state contracts.
2. Implement provider response/header/error classifiers with fixtures from documented providers.
3. Implement durable delayed retry scheduling and a conservative per-provider token/request budget.
4. Implement payload manifest, chunk store, idempotent acknowledgements and integrity-checked assembly.
5. Implement explicit accumulation envelopes for continuity-capable endpoints and local assembly for stateless endpoints.
6. Integrate with Session Independence checkpoints, task budgets and observability events.
7. Run simulated fault tests, then provider-specific integration tests using authorized test credentials and strict cost ceilings.
