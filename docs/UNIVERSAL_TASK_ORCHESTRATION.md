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

A deployment constructs its real backends, then registers the adapter and
parent handler. The following is a minimal example using the existing reference
axial solver; it does not auto-enable unconfigured CAD, FEM, browser, or remote
services.

```python
from yj64_engineering_core.automation import (
    EngineeringDispatcherTaskAdapter,
    PARENT_TASK_QUEUE_TYPE,
    TaskAdapterRegistry,
    create_parent_task_handler,
)
from yj64_engineering_core.automation.worker import WorkerRunner
from yj64_engineering_core.dispatcher import AxialMemberSolver, EngineeringDispatcher

dispatcher = EngineeringDispatcher()
dispatcher.register_physics_solver(AxialMemberSolver())

registry = TaskAdapterRegistry()
registry.register(
    "engineering.analysis",
    EngineeringDispatcherTaskAdapter(dispatcher),
    capabilities=("engineering.dispatch",),
)

handlers = {
    PARENT_TASK_QUEUE_TYPE: create_parent_task_handler(registry),
    # Keep the deployment's other existing handlers here.
}
runner = WorkerRunner(
    store,
    worker_id="engineering-worker-1",
    handlers=handlers,
    allowed_task_types=[PARENT_TASK_QUEUE_TYPE],
)
runner.run_once()
```

The engineering adapter requires an explicit operation and an
`EngineeringRequest` object in `input_data`. It calls the existing
`EngineeringDispatcher`, stores the structured response in the parent's
integrity-checked checkpoint, and records artifact references. Unknown
operations or unregistered backends are blocked rather than guessed.

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
