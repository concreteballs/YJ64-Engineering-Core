# CI Automation and Completion Notifications

## Current implementation

The repository has an optional GitHub Actions completion webhook:

- Workflow: `.github/workflows/notify-ci-completion.yml`
- Trigger: completion of the `Python tests` workflow.
- Scope: pushes to `main` only.
- Payload: repository, workflow/run identifiers, attempt, conclusion, commit SHA, branch, and run URL.
- Authentication: HTTPS POST with a bearer token stored as a GitHub Actions secret.
- If secrets are absent, the workflow reports a notice and exits without failing the engineering CI.

## GitHub configuration

Add these repository Actions secrets under Settings -> Secrets and variables -> Actions:

- `YJ64_CI_WEBHOOK_URL`: HTTPS endpoint of the user's chosen receiver.
- `YJ64_CI_WEBHOOK_SECRET`: high-entropy random secret shared with that receiver.

Never put either value in source files, workflow YAML, issues, or chat messages.

The receiver must:
1. Accept HTTPS POST requests.
2. Validate the bearer secret using constant-time comparison.
3. Validate the repository name, branch, event type, and payload schema.
4. Deduplicate by repository + run_id + run_attempt.
5. Treat all payload fields as untrusted data.
6. Record the result and notify the configured destination.
7. Never execute repository code or grant write access merely because a webhook arrived.

## Important ChatGPT conversation limitation

A GitHub webhook can notify an external receiver, start a separate agent, or send a message to an external destination. It cannot, by itself, resume this exact ChatGPT conversation.

Resuming this conversation requires a supported ChatGPT background-task/event integration that can deliver a model-visible notification to the parent conversation. The internal conversation notification capability is not a public webhook URL and must not be guessed, copied into GitHub secrets, or exposed as a credential.

Therefore the repository workflow is the event-emitter foundation, not a claim that automatic continuation inside this chat is already active. A receiver-to-ChatGPT bridge must be connected through a supported product integration before the end-to-end loop can be considered operational.

## Safe development loop

1. GitHub Actions reports completion.
2. Receiver verifies and deduplicates the event.
3. The result is made available to the authorized engineering agent.
4. The agent checks the commit, complete job results, logs on failure, and the current plan.
5. On success, it selects the next incomplete plan step.
6. On failure, it diagnoses and proposes/fixes only within the authorized repository and branch.
7. Every code change triggers CI again.
8. Stop on ambiguous requirements, destructive changes, permission requests, security-sensitive changes, or a failure that cannot be safely diagnosed.
9. Preserve the plan history and record commit/run references; never claim success without a completed successful run.

## Current activation status

The GitHub workflow is committed, but webhook delivery remains inactive until both repository secrets are configured and a receiver endpoint is deployed. Automatic wake-up of this exact ChatGPT conversation is not yet configured.
