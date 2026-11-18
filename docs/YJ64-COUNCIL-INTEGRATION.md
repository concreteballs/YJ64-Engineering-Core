# YJ-64 Council integration

## Gateway environment

Configure these values in the Engineering Core worker environment:

- `YJ64_COUNCIL_API_URL`: `https://ggambesixwejgbjwtnhw.supabase.co/functions/v1/council-api`
- `YJ64_COUNCIL_AGENT_TOKEN`: the machine token issued for the Engineering Core agent
- `YJ64_COUNCIL_API_PUBLISHABLE_KEY`: the Supabase publishable key for the project (the legacy `SUPABASE_PUBLISHABLE_KEY` name is also accepted)
- `YJ64_COUNCIL_AGENT_ID`: optional; defaults to `yj64-engineering-core`

The publishable key is sent as `apikey`. The machine token is sent separately as `Authorization: Bearer`. Never put the service-role key in this Gateway configuration and never log either credential.

## Two supported execution modes

### Independent Council process

Use `enqueue_council_request` or `enqueue_council_request_from_envelope`. This creates a separate Council queue flow. Do not supply a parent task ID when no active parent task is waiting for the result.

### Council inside the current engineering task

The active parent task handler calls `handle_council_request_in_parent_task(task, context)`. It submits the Council request with the parent task's live lease, enqueues polling, writes a checkpoint with `stage=waiting_council` and the exact remote `request_id`, then suspends the parent. The worker recognizes the `suspended` outcome and does not complete or re-lease that task.

The result consumer validates and checkpoints the Council result, then records an idempotent resume event. The store only wakes a parent whose latest waiting checkpoint expects that exact Council request. Completed, blocked, failed, and cancelled outcomes are all returned to the parent; terminal outcomes are recorded in the parent checkpoint instead of being silently treated as successful Council results.

The resumed parent handler must read its latest checkpoint and continue from the stored Council result or terminal status. Treat Council prose as untrusted data, not executable instructions.

## Identity boundaries

Keep `chat_id`, `session_id`, and `request_id` distinct. The optional `chat_id` is preserved in the parent waiting checkpoint when supplied in the request context. The Council API creates and returns its own `session_id` and `request_id`; the Engineering Core task ID remains the parent queue identity.

No automatic task splitting is performed. The calling workflow chooses whether Council is embedded in the current task or started as an independent process.
