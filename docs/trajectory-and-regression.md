# Trajectory and Regression Spine

AgentLegion cannot be a serious multi-agent control plane if it only routes work. It must also turn every run into evidence, facts, and reusable regression assets.

This document defines the minimum quality spine that must exist before real runtime adapters are allowed to execute write-capable missions.

## Source Principle

The local Agent development handbook gives the minimum production loop:

```text
raw trace
  -> trajectory_run
  -> trajectory_step
  -> tool_call_fact
  -> score_fact
  -> regression_case
```

AgentLegion adopts this as an engineering invariant:

```text
No runtime execution without a trajectory id.
No side-effecting tool without a tool_call_fact.
No failed run without a score or root-cause path.
No production release without replaying active regression cases.
```

## Bronze / Silver / Gold Layout

The local store uses a lakehouse-style layout:

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
  artifacts/
  runtime-plans/
```

Bronze is the evidence layer. It stores raw runtime payloads, raw events, raw traces, raw scores, and raw tool returns. Adapters must preserve the native payload even when a normalizer exists.

Silver is the fact layer. It stores normalized trajectory facts used for attribution, debugging, comparison, and regression mining.

Gold is the asset layer. It stores curated regression cases, replay snapshots, eval reports, release gates, and trajectory diffs.

## Minimum Silver Objects

`TrajectoryRun` records one full run. It binds native trace/session identifiers to `agentUnitId`, `runtimeClass`, versions, model, prompt, tool schema, status, outcome, cost, latency, and the raw trace reference.

`TrajectoryStep` records ordered behavior. It is not message history. It captures the step index, turn index, type, status, parent step, input/output references, latency, and error class.

`ToolCallFact` is mandatory for every tool invocation. It records the tool name, namespace, args hash, validation result, result summary, error status, retry index, side-effect class, approval status, and source step.

`ScoreFact` records evaluation results. Scores can target runs, steps, tool calls, artifacts, or regression cases. Evaluators can be human, LLM, rule-based, unit-test, or integration-test.

## Regression Objects

`RegressionCase` converts a failure into a reusable test asset. It must include source trajectory id, root-cause category, failed step id when known, severity, owner, priority, replay input reference, expected behavior reference, and replay snapshot reference when available.

The root-cause taxonomy is intentionally short:

```text
Intent
Planning
Tool Selection
Tool Arguments
Observation Use
Retrieval
State
Recovery
Artifact
Policy / Safety
Infrastructure
Evaluation
```

`ReplaySnapshot` stores the task world, not just the prompt: user input, initial state, memory snapshot, tool space, tool schema, retrieval corpus version, permission context, external API fixtures, clock, feature flags, model config, prompt version, and expected behavior.

`TrajectoryDiff` compares behavior paths across versions. It should flag changes in final outcome, tool selection, tool arguments, observation use, latency, and cost.

`ReleaseGate` aggregates regression and quality thresholds. Severe root-cause recurrence should default to zero tolerance.

## Adapter Obligations

Every RuntimeAdapter must eventually implement the same write path:

1. Allocate a `trajectoryId` before invocation.
2. Store raw runtime events under Bronze.
3. Normalize events into Silver objects.
4. Store every tool invocation as `ToolCallFact`.
5. Attach `ScoreFact` to failed or evaluated runs.
6. Convert accepted failures into `RegressionCase`.
7. Generate replay snapshots before active regression cases are used for release gates.

Adapters may preserve runtime-specific semantics in raw payloads. AgentLegion standardizes the audit spine, not the runtime internals.

## CLI

Initialize the local store:

```bash
python3 agentlegion.py init-store
```

Inspect the expected layout:

```bash
python3 agentlegion.py inspect-store
```

The store commands do not invoke agents. They only prepare the filesystem contract that future adapters must write into.

## Normalizer CLI

`ingest-events` provides the first concrete normalizer path. It accepts a JSON array or JSONL file of `AgentEvent`-like objects, writes every raw event to Bronze, and writes normalized facts to Silver.

Create a fixture:

```bash
python3 agentlegion.py write-fixture-events
```

Ingest it:

```bash
python3 agentlegion.py ingest-events \
  .agentlegion/fixtures/agent-events.fixture.json \
  --trajectory-id fixture-trajectory-001 \
  --session-id fixture-session-001 \
  --agent-version fixture-agent/v0 \
  --task-type fixture
```

The current normalizer supports these event types:

- `started` -> `TrajectoryRun`
- `message` -> `TrajectoryStep` + `MessageEvent`
- `tool_call` -> `TrajectoryStep` + `ToolCallFact`
- `tool_result` -> updates `ToolCallFact` when possible + records a result step
- `artifact` -> `TrajectoryStep` + `ArtifactFact`
- `completed`, `failed`, `cancelled` -> final `TrajectoryRun` state + terminal step

Unknown event types are preserved as Bronze raw events and represented as generic workflow steps in Silver. This is deliberate: runtime-specific semantics should not be dropped just because the portable schema does not yet understand them.

## Score and Regression CLI

`record-score` writes a `ScoreFact`. Scores can target a full trajectory, a step, a tool call, an artifact, or an existing regression case.

```bash
python3 agentlegion.py record-score \
  --trajectory-id fixture-trajectory-001 \
  --target-type trajectory_run \
  --target-id fixture-trajectory-001 \
  --score-name task_success \
  --score-type binary \
  --score-value true \
  --evaluator-type human \
  --evaluator-version local-review/v0 \
  --rationale "Fixture run completed successfully."
```

`promote-regression-case` converts a source trajectory into a `RegressionCase` and a minimal `ReplaySnapshot`.

```bash
python3 agentlegion.py promote-regression-case \
  --trajectory-id fixture-trajectory-001 \
  --root-cause-category "Tool Arguments" \
  --root-cause-detail "Tool args did not match the expected file path." \
  --failed-step-id fixture-trajectory-001-step-0002 \
  --severity medium \
  --fix-owner runtime-adapter \
  --regression-priority P1 \
  --replay-input "Read README.md before producing findings." \
  --expected-behavior "The adapter should call read_file with the requested path and summarize the result."
```

This deliberately keeps score recording and regression promotion outside the event normalizer. The normalizer extracts observed facts; scoring and promotion represent evaluation or human triage decisions.
