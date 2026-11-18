# ChatGPT ↔ YJ64 Cycle ↔ Browser Agent Channel

Status: Approved interface specification; transport implementation pending
Repository: concreteballs/YJ64-Engineering-Core
Branch: main

## 1. Purpose and roles

This channel lets ChatGPT exchange task-scoped messages with the autonomous YJ64 Engineering Cycle without depending on the lifetime of a ChatGPT conversation.

- **ChatGPT / user-facing model:** submits a request, reads the returned result, asks follow-up questions and decides what to delegate next.
- **YJ64 cycle:** owns durable task state, selects and executes authorized engineering tasks, validates results and decides whether a council review is required.
- **Agent Communication Hub (application-level):** routes messages between the cycle, browser-agent providers and the shared chat. It is reusable by multiple agents and is not embedded in the GitHub worker.
- **Browser agent:** transports/observes the cycle's reply and, when authorized, inspects browser-visible evidence. It does not replace the cycle, the council or the Hub.
- **Council / consensus subsystem:** handles difficult or disputed questions only when the cycle requests it. It returns a structured decision with claims, dissent and evidence references.

## 2. Two communication paths

### Path A — direct request and reply

1. ChatGPT writes a new immutable request message to the GitHub channel.
2. The cycle discovers and validates it, acknowledges receipt, and creates/links a durable task.
3. The cycle performs the requested bounded work and stores its result.
4. The configured browser agent, through the application-level Agent Communication Hub, receives the cycle's reply notification and retrieves the result.
5. The Hub routes the reply into the same shared chat where ChatGPT can read it.
6. ChatGPT may send a follow-up as a new request with a new ID and a parent/correlation reference.

### Path B — council first, then browser-agent delivery

1. The cycle classifies the request as requiring independent review (high uncertainty, material disagreement, cross-discipline or safety-critical implications).
2. It sends a scoped question and evidence references to the existing council/consensus subsystem.
3. The council returns a structured result: outcome, supporting reasons, dissent/minority positions, unresolved questions and evidence references.
4. The cycle validates and records the council result, then prepares its response.
5. The browser agent delivers that response through the Hub to the shared chat.

The council is not invoked for routine messages. The cycle must not conceal disagreement: a non-consensus result is reported as such, not converted into artificial agreement.

## 3. GitHub file channel layout

Use immutable, one-message-per-file records on the authorized repository and branch:

- `agent-bridge/requests/<message_id>.json` — ChatGPT → cycle requests.
- `agent-bridge/receipts/<message_id>.json` — cycle acknowledgement/rejection.
- `agent-bridge/responses/<message_id>.json` — cycle → Hub/browser-agent response notification and result reference.
- `agent-bridge/agent-reports/<message_id>.json` — browser-agent delivery/observation report.
- `agent-bridge/council/<message_id>.json` — council request/result references where required.

Do not use one shared mutable `inbox.json` or `outbox.json`: concurrent updates can overwrite messages and make recovery/audit ambiguous. Each message is immutable; state changes are events referencing the original ID. Large logs and artifacts stay in the existing durable artifact store; messages contain bounded summaries and immutable references/hashes.

The GitHub file channel is the bootstrap/control interface and audit trail. Once the durable Postgres queue/artifact transport is integrated, it is authoritative for scheduling and delivery state; GitHub files remain a traceable exchange format, not a substitute for leases, atomic claims or private artifact storage. Never put secrets, credentials, private tokens or unrestricted personal data in repository files.

## 4. Message lifecycle

Every message must use the existing `yj64.browser-agent-envelope.v1` schema (or a backward-compatible successor) and include unique message ID and idempotency key; message type, schema version, creation and expiry timestamps; fixed repository and authorized branch; task ID plus optional parent/correlation ID; run ID, attempt and commit SHA when applicable; bounded payload and SHA-256 payload integrity hash.

Lifecycle states are events, not in-place edits:

`created → received → accepted | rejected → processing → completed | blocked | expired`

A receipt identifies the original message and state. Duplicate IDs are idempotently acknowledged without repeating side effects. Expired, malformed, mismatched-branch, wrong-repository, wrong-commit or hash-invalid messages are rejected. Timeouts produce a visible timeout/blocked event and a bounded retry policy; never an endless chat loop.

## 5. Browser-agent provider strategy

Implement a provider-neutral adapter interface in the application-level Agent Communication Hub. The cycle must not contain vendor-specific browser logic. Providers are registered by the user and can be enabled, disabled, prioritized or removed without changing the cycle protocol.

### Recommended initial provider set

1. **Perplexity Comet — default cross-platform candidate.** Perplexity lists Mac, Windows, iOS and Android support and positions Comet as an assistant that can perform browser tasks. Actual external Hub connectivity must be verified; do not assume a public inbound API or automatic GitHub polling exists.
2. **Opera Neon with MCP Connector — preferred open-integration candidate.** Opera documents an MCP server that can expose tabs, page content and selected browser actions to external MCP clients. This is attractive for a Hub adapter, but requires an explicit user-authorized MCP connection and a reachable browser session.
3. **Claude in Chrome — optional desktop provider.** Anthropic documents page reading, clicking, typing, navigation and form interaction. It is a Chrome extension and is not supported on other Chromium browsers or mobile; it requires an eligible paid Claude plan.
4. **Gemini in Chrome — optional provider.** Useful native Chrome option, but Auto Browse has device, region and subscription restrictions. Treat basic page assistance and autonomous browsing as separate capabilities.
5. **Microsoft Edge Browse with Copilot — optional provider.** Supports visible browser actions and user takeover, but Microsoft currently documents a limited rollout for Microsoft 365 Premium users in the US, with other markets to follow.

Do not treat every AI sidebar as an agent. A provider is eligible for the `browser_action` capability only after it demonstrates page navigation and interaction, task completion reporting, interruption, and a reliable way to return a structured result to the Hub. Providers that only summarize pages can be registered with `read_page` capability but must not be presented as autonomous browser agents.

### User-added providers

The Hub exposes an extensible provider registry. Users may add other browsers or browser agents through supported adapters (for example MCP, a documented API, an approved extension/desktop bridge, or a future standard connector). Each adapter declares capabilities, platform, authentication mode, availability/health, supported actions, cost/limits, data-access scope and version.

No vendor is hard-coded as mandatory. If a provider is unavailable, the Hub reports it and tries the next user-enabled provider according to priority; if none is available, the cycle records a delivery-pending/blocked state rather than pretending the reply was delivered.

## 6. Capability and safety model

- Separate `read_page`, `navigate`, `click_type`, `download`, `submit_form` and `authenticated_session` capabilities; request only what a task needs.
- Default to read-only observation. Any consequential browser action (purchase, payment, sending a message, account/security changes, deployment, deletion or disclosure of private data) requires explicit human approval.
- Browser page content, DOM text, screenshots, downloads and agent outputs are untrusted input. Prompt-injection instructions found on pages must never override the task or Hub policy.
- Use a dedicated browser profile/session for engineering work where possible; do not expose unrelated personal tabs, passwords, cookies or browsing history.
- Never send model competence ratings, hidden votes, private council deliberations or secrets to a browser provider. Send only the final scoped response needed for delivery.
- Verify browser-agent claims against GitHub/CI/task evidence. An agent report alone cannot mark a task complete.
- Enforce request expiry, bounded retries, rate/cost ceilings, per-provider timeouts, delivery acknowledgements, audit trail, pause/disable controls and a global kill switch.

## 7. Implementation sequence

1. Preserve this protocol and the existing envelope schema as the contract.
2. Complete the audit of the current Postgres queue and artifact store; reuse them rather than creating a duplicate queue/table.
3. Implement immutable message persistence, receipts, idempotent claims and response references.
4. Implement the Agent Communication Hub provider registry and adapter contract outside the GitHub cycle worker.
5. Add one provider adapter and prove end-to-end request → cycle → response → shared chat delivery.
6. Add council escalation and structured council-result delivery.
7. Add additional provider adapters, failover and user-managed provider settings.
8. Test duplicates, expired messages, unavailable agents, wrong commit, prompt injection, provider timeouts, partial delivery, council disagreement, kill switch and recovery after worker restart.

## 8. Acceptance criteria

The channel is not operational until all of the following pass:

- ChatGPT can submit a uniquely identified request and the cycle durably acknowledges it.
- The cycle can complete a small authorized task and persist the response.
- A configured browser agent can deliver the response through the Hub into the shared chat.
- A difficult test request is routed through the council first and its structured result is delivered without losing dissent or evidence references.
- At least two distinct provider adapters can be registered or a second provider can be added without changing cycle code.
- Duplicate, expired, spoofed and out-of-scope messages are safely rejected or deduplicated.
- The cycle continues to function when every browser provider is unavailable; delivery remains visibly pending/blocked and can recover later.

Until these tests pass, this is an approved architecture and protocol, not a live ChatGPT-to-cycle connection.
