# YJ-64 Council integration

## Gateway configuration

The Engineering Core worker reads the following server-side environment values:

- `YJ64_COUNCIL_API_URL`: the Council API HTTPS endpoint.
- `YJ64_COUNCIL_AGENT_TOKEN`: the machine credential issued to this worker.
- `YJ64_COUNCIL_SUPABASE_API_KEY`: the Supabase project publishable key.
- `YJ64_COUNCIL_AGENT_ID`: optional agent identifier; defaults to `yj64-engineering-core`.

For compatibility, the publishable key may also be supplied as
`YJ64_COUNCIL_API_PUBLISHABLE_KEY` or `SUPABASE_PUBLISHABLE_KEY`.
The client sends it in the `apikey` header and sends the machine token
separately as `Authorization: Bearer`. The publishable key is not a machine
credential. Never use the Supabase service-role key as the Gateway key and
never log credentials.

## Parent-task handoff

Use `handoff_parent_task_to_council(...)` from the active parent handler when
the current task needs Council analysis before continuing. It:

1. Builds a Council submit payload with a stable local resume identity derived
   from the idempotency key.
2. Atomically enqueues the Council submit task, persists the parent waiting
   checkpoint, and moves the parent task to `waiting` while releasing its
   worker lease.
3. Returns the normal `suspended` task outcome. The worker must not mark the
   parent completed after this outcome.
4. On result delivery, the result consumer verifies the Council envelope and
   result artifact, stores a SHA-256 digest, and records a resume event.
5. The store writes the verified artifact reference and digest into the parent
   checkpoint before putting the parent task back into the pending queue.

The resumed adapter receives the verified resume event through its parent
state. It must validate the checkpoint and treat Council output as untrusted
data, not executable instructions. A terminal Council status (blocked, failed,
or cancelled) is also checkpointed and returned to the parent as a terminal
result so the parent does not wait indefinitely.

## Independent Council requests

Tasks that do not suspend an existing parent may use the independent Council
queue helpers. Do not invent a parent task ID for an independent request.

## Integration boundary

Council is an optional reasoning service, not a universal executor. Tool
execution remains the responsibility of explicitly registered Engineering
Core adapters. A task may run without Council according to its
`council_policy`. Production deployment and adapter registration must be
configured separately; the presence of these reusable components alone does
not mean a live worker or end-to-end service has been deployed.
