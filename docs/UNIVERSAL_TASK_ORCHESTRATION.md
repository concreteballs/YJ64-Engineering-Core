# Universal Task Orchestration

## Purpose

The generic task envelope and parent handler extend the existing YJ64 cycle.
They do not create a second queue, worker, Council API, checkpoint store, or
execution engine.

The existing responsibilities remain separate:

- `PostgresCycleStore`: durable queue, leases, idempotency, checkpoints and
  atomic Council resume.
- `WorkerRunner`: claims and executes one explicitly registered queue handler.
- `TaskRequest`: portable, versioned description of any task domain.
- `TaskAdapterRegistry`: explicit allowlist of domain execution adapters.
- `CouncilGatewayClient` and existing Council handlers: asynchronous collective
  analysis and verified parent wake-up.
- `EngineeringDispatcher`: explicit physics/CAD backend dispatch.

## Queue contract

Generic parent requests use the existing queue task type
`execute_task_request`. The payload is:

```json
{
  "task_request": {
    "task_id": "engineering-run-42",
    "task_type": "engineering.analysis",
    "title": "Axial member screening",
    "objective": "Calculate stress and elongation",
    "input_data": {
      "operation": "physics.axial_member",
      "engineering_request": {}
    },
    "constraints": {},
    "requested_capabilities": ["engineering.dispatch"],
    "council_policy": "optional",
    "approval_policy": {},
    "contract_version": "1.0"
  }
}
```

Use `enqueue_task_request(store, request)` to enqueue it. The request ID is the
stable idempotency identity. Reusing that ID with different content is rejected
by the existing PostgreSQL queue.

## Explicit adapter wiring

A deployment constructs its real backends, then uses the runtime factory to
wire the universal parent-task queue handler into the existing worker. The
factory preserves other explicitly supplied handlers and does not create or
guess external backends.

```python
from yj64_engineering_core.automation import create_engineering_worker_runner
from yj64_engineering_core.dispatcher import AxialMemberSolver, EngineeringDispatcher

dispatcher = EngineeringDispatcher()
dispatcher.register_physics_solver(AxialMemberSolver())

# Register real CAD/FEM backends here when their executables, workspaces and
# operating requirements have been configured by the deployment.

runner = create_engineering_worker_runner(
    store,
    dispatcher=dispatcher,
    worker_id="engineering-worker-1",
    additional_handlers={
        # Preserve existing CI/Council worker handlers here.
    },
)
runner.run_once()
```

The factory registers the concrete `engineering.analysis` adapter with the
`engineering.dispatch` capability and wires `execute_task_request` to the
parent handler. Additional task types remain explicit; no browser, repository
write, provider, FEM or CAD execution capability is implied by this registration.
A one-shot worker entry point is provided at
`scripts/run_engineering_task_worker.py`. It requires `YJ64_DATABASE_URL`
and optionally accepts `YJ64_ENGINEERING_WORKER_ID` and
`YJ64_CAD_WORKSPACE`. Without a CAD workspace it registers only the built-in
axial screening solver. With a workspace it additionally registers the
OpenSCAD-source, FreeCAD-macro and SVG-drawing writers. These writers create
files only; they do not execute external CAD applications.

Run it on a worker host after installing the project and applying the existing
PostgreSQL migrations:

```sh
python scripts/run_engineering_task_worker.py
```

This is a one-task invocation, not a background service. Schedule or supervise
it through the deployment platform. No database, server, secret or deployment
configuration is changed by this repository code.

The engineering adapter requires an explicit operation and an
`EngineeringRequest` object in `input_data`. It calls the existing
`EngineeringDispatcher`, stores the structured response in the parent's
integrity-checked checkpoint, and records artifact references. Unknown
operations or unregistered backends are blocked rather than guessed.

## Read-only GitHub execution adapter

The universal registry can compose engineering and GitHub capabilities without
creating another worker or queue. The GitHub adapter is deliberately GET-only:
it can read repository metadata, a commit, workflow-run metadata, a bounded list
of workflow runs, or a bounded UTF-8 repository file. It cannot write files,
create branches or commits, open/merge pull requests, dispatch workflows, or
change repository settings.

Configure a read-only GitHub token in the worker environment and pass it to the
client; never place credentials in a task envelope:

```python
import os

from yj64_engineering_core.automation import (
    GitHubReadOnlyClient,
    create_engineering_task_registry,
    create_universal_task_worker_runner,
    register_github_read_adapter,
)

registry = create_engineering_task_registry(dispatcher)
github_client = GitHubReadOnlyClient(os.environ["YJ64_GITHUB_READ_TOKEN"])
register_github_read_adapter(
    registry,
    github_client,
    allowed_repositories=["concreteballs/YJ64-Engineering-Core"],
)

runner = create_universal_task_worker_runner(
    store,
    registry=registry,
    worker_id="universal-worker-1",
    additional_handlers=existing_handlers,
)
runner.run_once()
```

A GitHub task uses `task_type="github.read"`, requests capability
`github.read`, and selects one of these explicit operations in
`input_data.operation`: `repository.get`, `commit.get`,
`workflow_run.get`, `workflow_runs.list`, or `file.get`. The deployment
must provide a non-empty repository allowlist. File reads are limited to 128
KiB; API responses are limited to 256 KiB. Results are saved in the normal
integrity-checked parent checkpoint and explicitly marked as untrusted evidence.
The adapter never treats repository text, commit messages, or workflow metadata
as instructions or as proof that a task is complete.

This adapter is the first GitHub executor boundary, not a general GitHub
administration interface. Repository writes and workflow dispatch require a
separate adapter, narrower permissions, and explicit human approval.

## Council and approval policies

- `never`: the parent handler wraps the task context and blocks Council
  enqueue/suspend operations.
- `optional`: the registered adapter decides whether to call the existing
  `handoff_parent_task_to_council(...)` helper.
- `required`: only a Council-capable adapter may be registered for the request;
  its first execution must suspend for Council rather than silently complete.
  After the verified resume checkpoint arrives, the adapter receives the
  preserved parent state and Council result artifact reference/hash.

The parent handler verifies checkpoint integrity and resume-event shape before
passing state to an adapter. Council output remains untrusted data; the adapter
must validate it for its domain before acting on it.

`approval_policy` and `constraints` are passed to the adapter and preserved
in task state. They are not a substitute for domain-specific authorization:
each adapter must enforce required human approvals before irreversible or
external actions. The reference engineering adapter performs calculations and
does not perform repository writes or external deployment actions.

## Deliberate non-goals

This change does not add a public task-ingress HTTP endpoint, auto-discover
plugins, create a production adapter factory, launch a background worker, deploy
services, or register provider credentials. Those require explicit deployment
configuration and concrete adapters. Existing CI, Council, CAD and physics
handlers remain separate and are not duplicated by the generic parent handler.
