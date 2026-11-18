# YJ64 Council Gateway Integration

## Purpose and ownership

The Council Gateway is the authenticated external-agent client and durable handoff layer in YJ64 Engineering Core. The YJ-64 application remains the sole owner of its model router, participants, Consensus/Critique protocols, rounds, votes, private ratings, and council session state.

The Gateway does not create a second council, select individual models, call model-provider APIs, or reproduce internal discussion logic.

Application source audited for this integration:
- Repository: `concreteballs/yj64-clean-bial2modFun5`
- Audited ref: `main`
- Main application flow: `main.py`
- Participant dispatch: `message_distributor.py`
- Provider router: `llm_api.py`
- Local chat persistence: `chat_workspace.py`
- Application integration plan: `docs/YJ64-CLOUD-DEPLOYMENT-AND-INTEGRATION-PLAN.md`, section 8.2`

## Verified application-side state and integration blocker

The current application source has a local `MessageDistributor` that dispatches to configured participants through `llm_api.generate_response`. `main.py` owns sequential multi-participant dialogue rounds, a separate group-dialogue loop, a prompt-based critique mode, stop controls, and the UI. `chat_workspace.py` stores chat messages in app-private JSON files.

The audit did not find a separate formal consensus decision engine, a structured critique/voting state machine, or a machine-readable consensus result lifecycle. The current `consensus_reached` flag and `[CONSENSUS: APPROVE/OBJECT]` prompt marker do not by themselves establish a verified consensus protocol. The planned Consensus/Critique/Voting/Decision Integrity work is described in the application integration plan, but documentation is not implementation evidence.

The audited source also does not expose a cloud HTTP API for an external agent, a server-side machine identity, durable remote council request/session records, or a remote polling/result endpoint. The configured diagnostic bridge is Android Content Provider IPC and is not a council API. The application README states that no cloud reporting endpoint is configured.

Therefore the Gateway client and durable Engineering Core workflow can be implemented independently, but a real end-to-end council exchange cannot be claimed until the YJ-64 application implements the API contract below, connects it to its actual native multi-model workflow, and implements the agreed Consensus/Critique result semantics. The Gateway must not relabel an ordinary sequential chat as a completed consensus. A mock server is not proof of that integration.

## Proposed versioned API contract

Protocol: `yj64.council-api.v1`

The paths below are the concrete proposed defaults used by `CouncilGatewayClient`. They must be implemented by the YJ-64 application or explicitly mapped through the environment-configured API base path before production use.

| Operation | Method and path | Purpose |
|---|---|---|
| Submit | `POST /api/v1/external-agents/council/requests` | Accept one request and return `request_id` and `session_id` |
| Status | `GET /api/v1/external-agents/council/requests/{request_id}` | Return execution state and optional progress |
| Result | `GET /api/v1/external-agents/council/requests/{request_id}/result` | Return the structured result only when completed |
| Cancel | `POST /api/v1/external-agents/council/requests/{request_id}/cancel` | Request cancellation subject to owner, scope, and state checks |

All operations require a dedicated machine identity using a server-side Bearer token and the `yj64.council.submit`, `yj64.council.read`, and `yj64.council.cancel` scopes as applicable. The application must authorize every request against `agent_id` and request ownership. The token must never be exposed to Android UI, browser code, repository files, task payloads, or logs.

### Submit request

The request schema is `schemas/council-api-v1.schema.json`. It contains:
- `protocol_version`, `agent_id`, `correlation_id`, and `idempotency_key`;
- `mode`: `consensus` or `critique`;
- task title, prompt, bounded context, and evidence references;
- bounded round, execution-time, and output-token limits plus an explicit early-stop policy;
- optional voting controls (`enabled`, `weighted`). Voting is opt-in; when enabled, the API may return only an aggregate voting summary, never individual ballots or private competence ratings.

The application must return the same remote request/session for a repeated idempotency key belonging to the same authorized agent. It must not create a second discussion on retry.

### Execution and substantive outcome are separate

Execution statuses:
`accepted`, `running`, `completed`, `blocked`, `failed`, `cancelled`.

Substantive outcomes, available only for a completed discussion:
`consensus`, `qualified_consensus`, `unresolved_disagreement`, `insufficient_evidence`.

The application must preserve material dissent and uncertainty. It must never turn a timeout, blocked request, or lack of evidence into consensus.

### Result payload

The result includes request/session identity, execution status, substantive outcome, summary, claims, participant positions, dissent, evidence references, unresolved questions, assumptions, limitations, rounds completed, completion reason, and available test/simulation results. Hidden competence scores, private messages, hidden individual ballots, provider credentials, and internal prompts are excluded.

## Engineering Core implementation

Files:
- `src/yj64_engineering_core/automation/browser_agent_bridge.py` — builds and validates the existing `yj64.browser-agent-envelope.v1` messages for `council_request` and `council_result`.
- `src/yj64_engineering_core/automation/council_gateway.py`: HTTPS client, machine authentication, bounded payloads, protocol validation, request/session identity checks, and result validation.
- `src/yj64_engineering_core/automation/council_tasks.py`: durable queue entrypoint, submit/poll handlers, checkpointing, result artifact persistence, and result-ready handoff.
- `scripts/run_council_gateway_worker.py`: one-task worker entrypoint.
- `.github/workflows/scheduled-council-gateway-worker.yml`: bounded scheduled workers; one task per worker invocation.
- `schemas/council-api-v1.schema.json`: protocol schema.

The existing PostgreSQL task queue is reused. New allowlisted task types:
- `submit_council_request`
- `poll_council_request`
- `council_result_ready` (handoff for the engineering-agent consumer; intentionally not consumed by the Gateway worker).

Lifecycle:
1. The GitHub agent sends a `council_request` message using the existing `yj64.browser-agent-envelope.v1`. `enqueue_council_request_from_envelope(...)` validates repository/branch scope, expiry, message type, idempotency key, and payload hash before placing the request in the queue. The envelope hash protects integrity but does not authenticate the sender; the receiving boundary must authenticate and authorize the agent.
2. An internal engineering workflow may call `enqueue_council_request(...)` directly when it already has an authorized task context.
3. The submit task sends one authenticated request. The same key is reused on a retry after an ambiguous transport failure.
4. The Gateway checkpoints the returned request/session IDs, enqueues a poll task, and completes the submit task. It does not hold a worker while the discussion runs.
5. Each poll task performs one status request. If still running, it enqueues the next generation and completes itself.
6. On completion, the structured result is validated, stored in the existing private content-addressed Supabase artifact store, and referenced by a `council_result_ready` queue item. The handoff also contains a `council_result` browser-agent envelope bound to the original task reference.
7. The engineering-agent workflow consumes that handoff through `load_council_result_artifact(...)`, which validates the result envelope and request/session identity before loading the private artifact. The agent independently verifies claims against repository state, tests, and CI, and resumes its parent engineering task.

The Gateway never treats the council's conclusion as proof that a patch is correct. The consumer must validate the result and preserve the distinction between consensus, qualified consensus, unresolved disagreement, and insufficient evidence.

## Runtime configuration

Configure these GitHub Actions repository secrets:
- `YJ64_DATABASE_URL`
- `YJ64_COUNCIL_API_URL` — HTTPS origin of the YJ-64 external-agent API.
- `YJ64_COUNCIL_AGENT_TOKEN` — dedicated machine token with minimum scopes.
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` — server-side only, used to persist private result artifacts.

Optional variable:
- `YJ64_COUNCIL_AGENT_ID` (defaults to `yj64-engineering-core`).

The scheduled workflow polls every five minutes and runs at most three single-task workers in parallel. Polling is durable and bounded by `max_poll_count`; no worker sleeps while waiting for a discussion.

## Verification and release gate

Automated client and task-handler tests cover request authentication, idempotency header, payload limits, protocol/status/outcome validation, session identity matching, durable poll scheduling, artifact persistence, and result handoff.

Production readiness still requires the YJ-64 application to:
1. implement the API and machine identity described above;
2. connect API submissions to its existing native council/dialogue lifecycle rather than a parallel model loop;
3. persist remote request/session state and recover it after service restart;
4. implement per-agent authorization, idempotency, rate/resource limits, cancellation, and audit events;
5. pass real integration tests for both modes, dissent, polling, cancellation, unauthorized access, replay, and restart recovery.

Until those conditions pass, the Engineering Core component is an implemented client/orchestration layer with a pending application-side API dependency, not a completed live council connection.
