# AgentLegion Current Status And Usage

This document summarizes the current AgentLegion MVP state and gives a practical local usage guide.

## 1. Stage Summary

AgentLegion has moved away from the earlier idea of a universal `AgentChart` manifest.

The current thesis is:

```text
AgentLegion manages a heterogeneous legion of agents through tasks, capabilities,
policies, approvals, artifacts, execution plans, events, trajectories, and audit records.

It does not pretend that every runtime has the same internal semantics.
```

The working control-plane path is now:

```text
AgentUnit / LegionPlan / MissionSpec / PolicySpec
-> MissionPlan
-> CompiledRuntimePlan
-> ApprovalDecision
-> DAG preflight scheduler
-> safe execution simulator
-> raw runtime events
-> normalized trajectory facts
-> mission execution report
-> audit and regression assets
```

## 2. What Exists Now

### Architecture and Resource Model

Implemented design documents:

- `docs/theory.md`
- `docs/architecture.md`
- `docs/object-model.md`
- `docs/adapter-contract.md`
- `docs/policy-and-safety.md`
- `docs/implementation-guide.md`
- `docs/mvp-roadmap.md`
- `docs/adr/0001-agentlegion-not-agentchart.md`

Core resources:

- `AgentUnit`: one concrete agent runtime member.
- `LegionPlan`: the roster and role mapping.
- `MissionSpec`: the mission goal, workflow, dependencies, and expected artifacts.
- `PolicySpec`: default-deny / ask / allow policy rules.
- `MissionPlan`: read-only routing plan.
- `CompiledRuntimePlan`: runtime-specific dry-run plan.
- `ApprovalDecision`: simulated operator approval.
- `ExecutionRecord`: auditable execution or skip/preflight record.
- `MissionExecutionReport`: mission-level scheduler and execution report.
- `TrajectoryRun`, `TrajectoryStep`, `ToolCallFact`, `ScoreFact`: normalized quality spine.
- `RegressionCase`, `ReplaySnapshot`: failure-to-regression assets.

### Local MVP Legion

Current local MVP uses:

- Hermes as local coding runtime.
- DeepAgents as local research / planning runtime.

Configured in:

```text
examples/mvp-local-legion.yaml
```

Important safety boundary:

- Hermes is health-checked with `hermes --help`.
- Hermes is not invoked through `hermes chat`.
- DeepAgents is executed only through `scripts/deepagents_smoke.py`.
- DeepAgents smoke uses a fake local tool-binding model.
- No external LLM provider is called by the MVP smoke/execution path.
- No arbitrary shell command execution is enabled by AgentLegion.
- No workspace patching is enabled by AgentLegion.

### CLI Commands Implemented

Current `agentlegion.py` commands:

```text
validate
plan
compile-runtime-plan
init-store
inspect-store
ingest-events
write-fixture-events
record-score
promote-regression-case
mvp-smoke
approve-plan
execute-plan
execute-mission
```

### Quality Spine

The local data store uses a Bronze/Silver/Gold layout:

```text
.agentlegion/
  bronze/
    raw-events/
    raw-traces/
    raw-scores/
  silver/
    trajectory-runs/
    trajectory-steps/
    message-events/
    llm-call-facts/
    tool-call-facts/
    retrieval-facts/
    state-transition-facts/
    artifact-facts/
    score-facts/
  gold/
    regression-cases/
    replay-snapshots/
    trajectory-diffs/
    eval-reports/
    release-gates/
  control/
    approval-decisions/
    audit-events/
    execution-records/
  artifacts/
  runtime-plans/
```

`.agentlegion/` is runtime data and should not be committed.

## 3. Current Capabilities

### Validation

AgentLegion can validate local YAML resources:

```bash
python3 agentlegion.py validate \
  examples/mvp-local-legion.yaml \
  examples/mission-refactor-auth.yaml \
  examples/policy-default-deny.yaml
```

Expected result:

```json
{
  "ok": true,
  "resourceCount": 5,
  "diagnostics": []
}
```

### Read-Only Mission Planning

AgentLegion can route mission steps to candidate agents without invoking runtimes:

```bash
python3 agentlegion.py plan \
  --legion examples/mvp-local-legion.yaml \
  --legion-name mvp-local-legion \
  --mission examples/mission-refactor-auth.yaml \
  --policy examples/policy-default-deny.yaml \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.plan.json
```

This produces a `MissionPlan`.

### Runtime Plan Compilation

AgentLegion can compile a mission into runtime-specific dry-run plans:

```bash
python3 agentlegion.py compile-runtime-plan \
  --legion examples/mvp-local-legion.yaml \
  --legion-name mvp-local-legion \
  --mission examples/mission-refactor-auth.yaml \
  --policy examples/policy-default-deny.yaml \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json
```

This produces a `CompiledRuntimePlan`.

The compiled plan contains:

- selected agent unit
- runtime class
- native dry-run config
- command preview
- permission checks
- approval requirements
- sandbox plan
- dependencies
- input artifacts
- expected artifacts
- warnings

Current example phases:

```text
research   deepagents  ready_dry_run
plan       deepagents  pending_approval
implement  hermes      pending_approval
review     deepagents  ready_dry_run
decide     hermes      pending_approval
```

### Approval Simulation

AgentLegion can approve or reject pending runtime plans.

Approve the DeepAgents planning step:

```bash
python3 agentlegion.py approve-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json \
  --task-id plan \
  --decision allow \
  --reason "Approve DeepAgents planning dry-run." \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json
```

Approve the Hermes implementation step as a dry-run handoff only:

```bash
python3 agentlegion.py approve-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json \
  --task-id implement \
  --decision allow \
  --reason "Approve implementation dry-run handoff only." \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.implement-approved.json
```

Approval writes:

```text
.agentlegion/control/approval-decisions/
.agentlegion/control/audit-events/
```

### Safe Single-Step Execution

`execute-plan` can execute selected approved runtime plans through the safe simulator.

Only DeepAgents `local_smoke` is executable today:

```bash
python3 agentlegion.py execute-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json \
  --task-id plan \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-executed.json
```

Hermes plans are never invoked by the simulator. If an approved Hermes plan is selected, AgentLegion records it as skipped / `approved_not_executed` with a command preview.

### Mission-Level DAG Execution

`execute-mission` is the current mission-level controller.

It performs:

- DAG construction from `dependsOn`
- missing task checks
- duplicate task checks
- missing dependency checks
- cycle detection
- topological order generation
- scheduler batch reporting
- artifact readiness checks
- dependency blocking
- safe runtime execution
- mission execution report creation

Run it after approving a step:

```bash
python3 agentlegion.py execute-mission \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json \
  --max-parallel-tasks 2 \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.mission-executed.json
```

Output includes:

```text
summary
scheduler.ok
scheduler.diagnostics
scheduler.topologicalOrder
scheduler.batches
scheduler.executedBatches
scheduler.artifactReadiness
results
```

If a dependency graph contains a cycle, the command writes a `preflight_failed` execution record and exits non-zero.

### Local Smoke Test

Run:

```bash
python3 agentlegion.py mvp-smoke
```

This checks:

- Hermes CLI health through `hermes --help`
- DeepAgents SDK execution through `.venv/bin/python scripts/deepagents_smoke.py`
- event ingestion into Bronze/Silver

Expected high-level result:

```json
{
  "ok": true,
  "checks": [
    {
      "runtime": "hermes",
      "ok": true
    },
    {
      "runtime": "deepagents",
      "ok": true
    }
  ]
}
```

## 4. First-Time Local Setup

From the repository root:

```bash
cd /Users/pengwanli/Downloads/agent_exp/AgentLegion
```

Create the Python environment:

```bash
uv venv --python 3.11 .venv
uv pip install -e ../deepagents/libs/deepagents
```

Initialize local store:

```bash
python3 agentlegion.py init-store
python3 agentlegion.py inspect-store
```

Run validation:

```bash
python3 agentlegion.py validate \
  examples/mvp-local-legion.yaml \
  examples/mission-refactor-auth.yaml \
  examples/policy-default-deny.yaml
```

Run smoke:

```bash
python3 agentlegion.py mvp-smoke
```

## 5. Recommended End-To-End MVP Flow

### Step 1. Compile Runtime Plan

```bash
python3 agentlegion.py compile-runtime-plan \
  --legion examples/mvp-local-legion.yaml \
  --legion-name mvp-local-legion \
  --mission examples/mission-refactor-auth.yaml \
  --policy examples/policy-default-deny.yaml \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json
```

### Step 2. Approve DeepAgents Planning Step

```bash
python3 agentlegion.py approve-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json \
  --task-id plan \
  --decision allow \
  --reason "Approve DeepAgents planning dry-run." \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json
```

### Step 3. Execute Mission Through DAG Controller

```bash
python3 agentlegion.py execute-mission \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json \
  --max-parallel-tasks 2 \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.mission-executed.json
```

### Step 4. Inspect Store

```bash
python3 agentlegion.py inspect-store
```

### Step 5. Optional: Execute One Approved Step Directly

```bash
python3 agentlegion.py execute-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json \
  --task-id plan \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-executed.json
```

## 6. Quality / Regression Flow

Write fixture events:

```bash
python3 agentlegion.py write-fixture-events
```

Ingest fixture events:

```bash
python3 agentlegion.py ingest-events \
  .agentlegion/fixtures/agent-events.fixture.json \
  --trajectory-id fixture-trajectory-001 \
  --session-id fixture-session-001
```

Record a score:

```bash
python3 agentlegion.py record-score \
  --target-type trajectory_run \
  --target-id fixture-trajectory-001 \
  --score-name task_success \
  --score-type binary \
  --score-value true \
  --evaluator-type human
```

Promote a failed trajectory to a regression case:

```bash
python3 agentlegion.py promote-regression-case \
  --trajectory-id fixture-trajectory-001 \
  --root-cause-category "Tool Arguments" \
  --severity medium \
  --regression-priority P1 \
  --replay-input "Replay the same task input." \
  --expected-behavior "The agent should call the correct tool with valid arguments."
```

## 7. Current Safety Rules

Do not run:

```bash
hermes-agent --help
```

That command previously launched a default live task.

Safe Hermes health check:

```bash
hermes --help
```

Do not enable real Hermes execution until a stricter adapter exists.

The current simulator must not run:

```bash
hermes chat -q ...
```

## 8. What Is Not Implemented Yet

Not implemented yet:

- real Hermes execution adapter
- OpenClaw runtime adapter
- Claude Code adapter
- open-webui adapter
- real external LLM calls through AgentLegion
- workspace patch application
- runtime-level sandbox enforcement
- secrets injection
- true parallel execution
- retry policy
- interrupt / cancel
- resume from runtime handles
- artifact content bus
- release gate automation

## 9. Current Technical Risk

P0:

- Real write-capable runtime execution needs sandboxing, approval enforcement, and workspace isolation.
- Runtime adapters need strict event normalization contracts.
- Artifact readiness currently checks declared producer phases, not artifact content existence.

P1:

- Dependency satisfaction semantics may need to become runtime-specific.
- Mission scheduler currently records parallelizable batches but executes sequentially.
- Role fallback in `mvp-local-legion.yaml` intentionally creates role mismatch warnings.

P2:

- Better CLI UX.
- More schema validation.
- Richer mission reports.
- Visual DAG reports.

## 10. Recommended Next Step

The next engineering step should be retry and failure policy:

```text
retryPolicy
failure classification
retryable vs non-retryable phases
retry execution records
replay seed
mission-level failure report
```

This would turn the current DAG executor from "safe ordered execution" into a real controller that can manage failure.
