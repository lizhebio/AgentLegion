# Dependency-Aware Executor

`execute-mission` is the first mission-level execution simulator.

It reads a `CompiledRuntimePlan`, builds a DAG from each step's `dependsOn`, validates the graph, records scheduler batches, checks artifact readiness, and only then delegates runnable tasks to the safe runtime simulator.

## Why It Exists

`execute-plan` is intentionally narrow: it executes one selected runtime plan without reasoning about the wider mission graph.

`execute-mission` adds the missing orchestration rule:

```text
a task cannot execute until its dependencies have reached a satisfied phase
```

This keeps AgentLegion's control plane honest. A coder step cannot run if the planning step is still waiting for approval, and a review step cannot run if implementation failed or was blocked.

## DAG Preflight

Before attempting execution, the command validates:

- each runtime plan has a `taskId`
- there is only one runtime plan per `taskId` in the MVP scheduler
- every `dependsOn` entry points to an existing task
- the dependency graph is acyclic

If preflight fails, no runtime is invoked. The executor writes a `preflight_failed` execution record and includes diagnostics in the mission execution report.

## Scheduler Batches

The scheduler emits topological batches:

```json
{
  "batchIndex": 0,
  "taskIds": ["research"],
  "parallelizable": false
}
```

If a batch has more than one task, it is marked `parallelizable: true`.

The MVP still executes sequentially for audit simplicity. `--max-parallel-tasks` records the desired scheduler limit and whether throttling would be needed; it does not start parallel worker processes yet.

## Satisfied Dependency Phases

The MVP treats these phases as dependency-satisfied:

- `ready_dry_run`: a read-only dry-run step is considered available as a planning placeholder.
- `executed`: the simulator completed the step.
- `approved_not_executed`: the operator approved the step, but the safe simulator refused to invoke that runtime.

These phases are not dependency-satisfied:

- `pending_approval`
- `approved_ready`
- `blocked`
- `rejected`
- `execution_failed`
- `dependency_blocked`

This is simulator semantics, not a claim that all runtime states are portable. A production adapter can tighten the rule per runtime and per mission type.

## Execute A Mission

Approve the DeepAgents planning step:

```bash
python3 agentlegion.py approve-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json \
  --task-id plan \
  --decision allow \
  --reason "Approve DeepAgents planning dry-run." \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json
```

Run the dependency-aware mission executor:

```bash
python3 agentlegion.py execute-mission \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.mission-executed.json
```

By default, `execute-mission` attempts only `approved_ready` steps. It does not automatically execute every `ready_dry_run` step.

To also execute ready DeepAgents local smoke steps:

```bash
python3 agentlegion.py execute-mission \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json \
  --include-ready-dry-run \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.mission-executed.json
```

## Safety Boundary

The mission executor uses the same safe runtime boundary as `execute-plan`:

- DeepAgents `local_smoke` can run.
- Hermes is not invoked.
- Arbitrary shell commands are not invoked.
- External LLM providers are not called.
- Workspace files are not modified by AgentLegion.

If a Hermes step is approved and dependency-satisfied, the executor records it as:

```text
approved_not_executed
```

The `nativeConfig.commandPreview` remains available for audit, but `hermes chat -q ...` is not run.

## Control Records

The command writes:

```text
.agentlegion/control/execution-records/
.agentlegion/control/audit-events/
.agentlegion/artifacts/mission-execution-report-*.json
```

For dependency failures it writes an `ExecutionRecord` with:

- `status: dependency_blocked`
- `blockedDependencies`
- `phaseBefore`
- `runtimePlanId`
- `taskId`
- `agentUnitId`
- `runtimeClass`

The compiled plan is updated with:

- `metadata.missionExecutionSimulator`
- `missionExecutionReportRef`
- `scheduler.topologicalOrder`
- `scheduler.batches`
- `scheduler.artifactReadiness`
- recomputed `summary.dependencyBlocked`

## Current Limitation

The MVP now validates and schedules a DAG, but runtime execution is still sequential. This is intentional: the controller should produce auditable scheduling facts before it starts truly concurrent side-effecting work.

A later controller should add a full DAG scheduler with:

- parallelism limits
- retry policy
- interrupt/cancel behavior
- runtime-specific dependency satisfaction rules
