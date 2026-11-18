# Agent Communication Hub — Shared Browser-Agent Architecture

Status: Proposed modular architecture; integration contract to be implemented separately.
Scope: Shared app infrastructure, not GitHub Engineering Core internals.

## Purpose
Browser agents are reusable participants and tools. They should connect to the application through a shared Agent Communication Hub, not be hard-coded into a particular GitHub agent or workflow. The Hub routes agent messages to a selected shared chat/session and stores an auditable history.

## Components and responsibilities
- **Application Agent Communication Hub:** registration/connectivity, identity, capability metadata, authorization, routing, chat association, durable message history, delivery/ack state, retries, health status, disconnect handling, and user-visible events.
- **Browser Agent Adapter:** transport-specific connection and browser operation. It may open/read/write an authorized browser session, but does not own consensus, hidden model ratings, round limits, or the application's supervisory policy.
- **GitHub Engineering Agent:** emits task-scoped requests and accepts validated browser-agent reports. It cannot depend on the browser agent being connected to make its own state durable.
- **Shared Chat:** receives browser-agent reports as ordinary attributed messages, with provenance (agent identity, event/run/task/commit IDs, timestamp, links, evidence type). Reports are visibly distinguished from model-generated messages.
- **Bridge/Transport:** a typed, versioned message interface. Use the existing queue, durable state and artifact infrastructure after audit. Do not create a competing mailbox/table/store if a current component can be extended.

## Required interaction
1. Agent connects and registers its capabilities and health.
2. Hub validates identity, authorization, chat/session routing and capability scope.
3. GitHub worker publishes a task-scoped request or CI event to the durable bridge.
4. Browser agent receives the request, performs only authorized bounded operations, and submits a structured report.
5. Hub appends the report to the routed shared chat with provenance and also stores the structured result.
6. The engineering worker independently cross-checks GitHub/CI facts before using the report to advance or repair a task.
7. If ChatGPT or another model is asked to reply, the browser agent may transport the response back to the bridge. The worker consumes a structured, correlated response, not arbitrary chat text as an instruction.
8. All messages include correlation IDs, expiry, idempotency, explicit lifecycle state and acknowledgment. Keep a task-scoped exchange; do not create uncontrolled chat loops.

## Browser-to-ChatGPT fallback prototype
A temporary prototype may use a browser automation agent logged into ChatGPT:
- On a verified CI completion, GitHub workflow posts a small event to a durable bridge.
- A running/hosted browser agent retrieves it, opens the specifically authorized ChatGPT chat, and posts a compact report with exact commit/run links and test result.
- The agent can read the model response and write a correlated reply into the bridge's inbox for the GitHub worker.
- GitHub worker validates the correlation and reply envelope, cross-checks repository state, and then continues or blocks.
This is a proof-of-concept transport only. Browser DOM automation is fragile; do not treat ChatGPT web UI as a stable machine API. Keep prompts, reply size, number of exchanges, task scope, timeouts and retries bounded. The Hub is the durable record.

## Connection failure modes and graceful behavior
Handle explicitly:
- agent not installed, not registered, disconnected, unavailable or offline;
- browser process stopped/suspended, device sleep, mobile background kill, network loss;
- ChatGPT login expired, MFA/reauth required, access denied, or target chat missing/read-only;
- browser UI/DOM changes, page load timeout, send/read operation failure, wrong chat selected;
- message delivery ambiguous, duplicate event, duplicate report, stale/expired reply;
- CI still running, failed, cancelled, or report/run/commit mismatch;
- rate limits, quotas, budget limits, oversized report or unsafe log content;
- browser agent returns malformed, untrusted, contradictory, incomplete or unsupported report;
- response timeout or no model reply;
- bridge backend unavailable or durable write/ack failure.

Behavior:
- Persist event/request before attempting delivery.
- Use bounded retries with exponential backoff and idempotency; never retry indefinitely or replay an uncertain send blindly.
- Mark message/task state as pending, delivered, acknowledged, failed, expired or blocked.
- When the agent is unavailable, the engineering cycle pauses at the dependency or continues only if the task does not require browser verification. CI and queue history remain intact.
- Provide a visible status/notification and a resume path after reconnection.
- Fail closed on identity, scope, commit, evidence, or authorization mismatches.
- Never expose credentials in chat/logs or allow arbitrary agent text to trigger privileged actions.
- Preserve a direct GitHub/CI path so browser connectivity is not a single point of failure.

## MVP versus later
**MVP:** connect/register one browser agent, one authorized shared chat, one message type for CI completion/test report, structured bridge inbox/outbox, status/ack/retry/timeout, provenance in chat, and one bounded request-response exchange.

**Later:** multiple agents, capability routing, chat selection, richer notifications, offline queue, user controls, agent health dashboards, cross-agent workflows.

## Phone/background behavior
The phone does not need to remain online if the browser agent and bridge are hosted on an always-on cloud runner or server. If the browser agent runs only on the phone, Android background restrictions, sleep, app closure and network loss make reliable monitoring unlikely. A hosted persistent runner is preferred for continuous operation. A desktop browser session may also require the computer to stay awake unless hosted elsewhere.

## Integration rule
The Hub belongs to the application architecture and is developed in a separate workstream/chat. GitHub Engineering Core only implements its client adapter and task-specific use of the Hub contract. Keep the two workstreams synchronized through this architecture document and versioned contract.
