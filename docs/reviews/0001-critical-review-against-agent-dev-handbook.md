# Critical Review 0001: AgentLegion Against Agent Development Handbook

## Review Basis

This review compares the current AgentLegion repository against:

`/Users/pengwanli/Downloads/agent_exp/Agent开发经验手册.md`

The handbook's central thesis is:

> Do not only develop agent capability. Develop observability, reproducibility, trajectory, regression, and data governance from day one.

Current AgentLegion is strong on:

- heterogeneous agent modeling
- capability profiles
- mission planning
- side-effect policy
- adapter boundaries
- raw event preservation as a principle

But it is still weak on the handbook's production-grade agent engineering loop:

- trajectory model
- eval model
- regression case lifecycle
- replay environment snapshot
- versioning
- normalizer testing
- data governance
- quality dashboards

## Executive Judgment

AgentLegion currently answers:

```text
Which agents exist?
Which agent should do this mission step?
Which side effects might require approval?
Which runtime adapter would be used?
```

It does **not yet** answer:

```text
What exactly did the agent do?
Why did it choose that action?
Where did it drift?
Can we replay this failure?
Did the next version avoid the same failure?
Which behavior changed between versions?
```

That means AgentLegion is currently a **legion planning and governance shell**, not yet a production-grade **agent quality and regression system**.

This is acceptable for the current phase, but it must be corrected before runtime adapters are allowed to execute real agents.

## A. Findings

| Severity | Finding | Current Evidence | Handbook Requirement | Risk |
|---|---|---|---|---|
| P0 | No first-class trajectory model | `schemas/agentlegion.types.ts` defines `AgentEvent`, `Artifact`, `RuntimePlan`, but no `TrajectoryRun`, `TrajectoryStep`, `ToolCallFact`, or `ScoreFact`. | Handbook sections 4, 7, 20 require Task / Episode / Step / Action / Observation / Score and minimum tables: `trajectory_run`, `trajectory_step`, `tool_call_fact`, `score_fact`. | Once real adapters run, failures will be stored as loose events/artifacts rather than analyzable behavior. |
| P0 | MissionPlan is not a trajectory | `agentlegion.py` emits `MissionPlan` with selected agents and policy checks, but no ordered runtime steps, action/observation pairs, state deltas, or scores. | Handbook sections 2, 3, 4 emphasize that final plans/logs are not enough; trajectory must record behavior path. | A plan can explain intended routing, but cannot debug actual execution drift. |
| P0 | Tool calls do not have a canonical fact schema | `AgentEvent` has `tool_call` / `tool_result`; policy docs mention exposed tools, but there is no schema for args, args hash, validation, result summary, retry index, side-effect type, approval status. | Handbook section 8 requires every tool call to be structurally recorded. | High-risk tool failures cannot be aggregated or turned into regression cases. |
| P0 | No regression case lifecycle | No `RegressionCase` type, no CLI command, no docs for failure -> root cause -> replay -> trajectory diff -> release gate. | Handbook sections 11, 12, 19, 20 require online failures to become regression cases and release gates. | The system may observe failures but will not convert them into durable engineering assets. |
| P0 | No replay environment snapshot | `MissionSpec.context` has workspace/files/artifacts/variables, but no memory snapshot, tool schema snapshot, permission context, feature flags, clock, model config, retriever corpus version. | Handbook section 13 says replay is re-creating the task world, not re-running a user input. | Future replay will be flaky or impossible. |
| P1 | Versioning is too thin | `RuntimePlan.adapterVersion` exists, but no required `agent_version`, `prompt_version`, `model_params`, `tool_schema_version`, `memory_version`, `normalizer_version`, `evaluator_version`, `dataset_version`. | Handbook section 10 says versioning is a lifeline. | Failures cannot be attributed to prompt/model/tool/normalizer changes. |
| P1 | Raw/Silver/Gold data layers are not modeled | Docs mention raw events and audit logs, but no Bronze/Silver/Gold architecture. | Handbook section 6 recommends Bronze raw, Silver normalized trajectory facts, Gold eval/regression marts. | AgentLegion may become a log pile without durable analytics layers. |
| P1 | Normalizer is named but not specified | `architecture.md` has Event Normalizer, but no normalizer contract, fixture tests, idempotency tests, unknown field passthrough, migration policy. | Handbook section 17 says normalizer is the compiler of the agent quality data platform. | Bad normalization will corrupt all downstream quality analysis. |
| P1 | Eval/score model is missing | `Artifact` has status, but there is no `ScoreFact`, rubric, evaluator type, rationale ref, or target id. | Handbook sections 3, 4, 7 require eval distinct from trace and trajectory. | Mission success will remain subjective or final-output-only. |
| P1 | Root cause taxonomy is missing | No `root_cause_category`, `failed_step_id`, severity, owner, regression priority. | Handbook section 14 requires root cause taxonomy. | Failures will be unaggregated text notes. |
| P1 | Sensitive data governance is underspecified | `policy-and-safety.md` mentions redaction and secret refs, but no field-level access control, retention, trainable flag, deletion policy, legal hold, encryption model. | Handbook section 16 treats trace store as one of the most sensitive data pools. | Runtime traces may capture secrets, PII, file content, and tool args without lifecycle controls. |
| P1 | Planner scoring is transparent but not versioned or testable | `agentlegion.py` uses hard-coded keyword scoring and role-domain maps. | Handbook sections 10 and 17 require versioned normalizers/evaluators and tests. | Routing behavior can drift silently as heuristics change. |
| P2 | Artifact model lacks quality status depth | `Artifact.status` has draft/final/rejected/superseded, but no `quality_status`, evaluator refs, acceptance criteria, or lineage. | Handbook sections 7 and 12 include `artifact_fact` and artifact property checks. | Artifact quality cannot become a release gate. |
| P2 | No dashboard-oriented metrics | Docs mention audit but no metrics such as approval rate, side-effect count, tool error top list, root cause distribution, regression pass rate. | Handbook section 18 lists role-specific dashboards. | Platform users cannot see whether the legion is improving. |
| P2 | No release gate model | No schema for release gates or regression pass thresholds. | Handbook section 19 defines release checks. | Agent/runtime changes may ship without historical failure validation. |

## B. What AgentLegion Gets Right

### 1. It Avoids Universal Agent Abstraction

This aligns with the handbook's warning against treating message logs or final outputs as sufficient evidence. AgentLegion preserves runtime differences and does not flatten everything into one manifest.

### 2. It Has Early Policy Awareness

`docs/policy-and-safety.md` already treats shell, file write, network, MCP, secrets, channel sends, schedules, and subagent spawning as controlled actions. This aligns strongly with the handbook's warning that the most dangerous agent failure is an incorrect side-effectful tool call.

### 3. It Preserves Raw Events in Principle

`docs/architecture.md` says normalized events must preserve raw runtime payloads. This matches the handbook's Bronze layer idea.

### 4. It Uses Artifacts Instead of Full Shared Chat History

AgentLegion's Artifact Bus is a good fit with the handbook's advice that message history is raw material, not the analysis model.

### 5. It Starts With Read-Only Planning

The current `agentlegion.py` planner does not invoke runtimes. This is the right engineering posture. It reduces risk while validating mission decomposition, routing, and policy checks.

## C. Architectural Gap: Mission Planning vs Behavior Accounting

Current AgentLegion has strong concepts for **before execution**:

```text
AgentUnit
CapabilityProfile
LegionPlan
MissionSpec
PolicySpec
MissionPlan
```

The handbook requires equally strong concepts for **during and after execution**:

```text
TrajectoryRun
TrajectoryStep
Action
Observation
LLMCallFact
ToolCallFact
StateTransitionFact
ArtifactFact
ScoreFact
RegressionCase
ReplaySnapshot
TrajectoryDiff
ReleaseGate
```

This is the central gap.

Without this second half, AgentLegion can dispatch a legion, but cannot learn from it.

## D. Required Object Model Additions

### P0: Add Trajectory Objects

Add TypeScript/schema objects:

```ts
type TrajectoryRun = {
  trajectoryId: string;
  missionId: string;
  taskId?: string;
  traceId?: string;
  sessionId?: string;
  agentUnitId: string;
  runtimeClass: string;
  agentVersion: string;
  promptVersion?: string;
  model: string;
  modelParamsRef?: string;
  toolSchemaVersion?: string;
  memoryVersion?: string;
  normalizerVersion: string;
  taskType: string;
  status: "running" | "completed" | "failed" | "cancelled";
  finalOutcomeRef?: string;
  cost?: number;
  latencyMs?: number;
};
```

```ts
type TrajectoryStep = {
  stepId: string;
  trajectoryId: string;
  parentStepId?: string;
  stepIndex: number;
  turnIndex?: number;
  stepType:
    | "intent"
    | "planning"
    | "llm_call"
    | "tool_call"
    | "observation"
    | "state_transition"
    | "approval"
    | "artifact"
    | "evaluation"
    | "recovery";
  name: string;
  status: "running" | "completed" | "failed" | "blocked";
  inputRef?: string;
  outputRef?: string;
};
```

### P0: Add ToolCallFact

```ts
type ToolCallFact = {
  stepId: string;
  toolName: string;
  namespace?: string;
  argsRef: string;
  argsHash: string;
  validationResult?: "valid" | "invalid" | "unknown";
  resultRef?: string;
  resultSummaryRef?: string;
  isError: boolean;
  errorType?: string;
  latencyMs?: number;
  retryIndex?: number;
  sideEffectType:
    | "read_only"
    | "write_internal"
    | "write_external"
    | "user_visible_publish"
    | "payment_or_financial"
    | "permission_change"
    | "irreversible";
  approvalStatus?: "not_required" | "requested" | "approved" | "denied" | "unavailable";
  sourceStepId?: string;
};
```

### P0: Add ScoreFact and RegressionCase

```ts
type ScoreFact = {
  scoreId: string;
  targetType: "run" | "step" | "tool_call" | "artifact";
  targetId: string;
  scoreName: string;
  scoreType: "binary" | "numeric" | "categorical" | "rubric";
  scoreValue: string | number | boolean;
  evaluatorType: "human" | "llm" | "programmatic";
  evaluatorVersion?: string;
  rationaleRef?: string;
};
```

```ts
type RegressionCase = {
  caseId: string;
  sourceTrajectoryId: string;
  rootCauseCategory:
    | "Intent"
    | "Planning"
    | "Tool Selection"
    | "Tool Arguments"
    | "Observation Use"
    | "Retrieval"
    | "State"
    | "Recovery"
    | "Artifact"
    | "Policy / Safety"
    | "Infrastructure"
    | "Evaluation";
  rootCauseDetail: string;
  failedStepId?: string;
  severity: "low" | "medium" | "high" | "critical";
  replayInputRef: string;
  replaySnapshotRef: string;
  expectedBehaviorRef: string;
  regressionPriority: "p0" | "p1" | "p2";
  createdFromFailureAt: string;
};
```

## E. Required CLI Additions

Current CLI:

```bash
agentlegion.py validate
agentlegion.py plan
```

Recommended next commands:

```bash
agentlegion.py normalize --raw RAW_EVENTS.jsonl --out .agentlegion/trajectories/RUN.json
agentlegion.py score --trajectory RUN.json --rubric RUBRIC.yaml
agentlegion.py regression create --trajectory RUN.json --root-cause "Tool Arguments"
agentlegion.py replay --case CASE.json --adapter deepagents --dry-run
agentlegion.py diff --old OLD_TRAJECTORY.json --new NEW_TRAJECTORY.json
```

Do not implement runtime replay first. Start with schemas and offline fixtures.

## F. Data Layer Recommendation

Adopt handbook's three-layer model:

```text
Bronze: raw runtime events, raw messages, raw tool returns, raw scores
Silver: normalized trajectory facts
Gold: eval sets, regression cases, dashboards, release gates
```

Suggested local layout:

```text
.agentlegion/
  bronze/
    raw-events/
    raw-scores/
  silver/
    trajectory-runs/
    trajectory-steps/
    tool-call-facts/
    score-facts/
  gold/
    regression-cases/
    eval-reports/
    release-gates/
  artifacts/
  runtime-plans/
```

## G. Planner-Specific Critique

The current planner is useful, but it should not be mistaken for production routing intelligence.

Issues:

1. **Hard-coded role-domain matching** in `agentlegion.py:213-223`.
2. **Keyword action matching** in `agentlegion.py:235-248` is transparent but brittle.
3. **Side-effect inference** is heuristic, not policy-proof.
4. **Planner version is not recorded** in generated `MissionPlan`.
5. **No route evaluation** exists. We cannot score whether the router made good choices.

Recommended fixes:

- Add `plannerVersion`.
- Add `routingStrategy`.
- Add `routingFeatures`.
- Add `rejectedCandidates`.
- Add `plannerScoreFact` after mission outcome is known.
- Add fixture tests for routing.

## H. Revised MVP Roadmap

### Current MVP Roadmap

The current roadmap moves from planner to artifact bus to DeepAgents/OpenClaw adapters.

### Recommended Revision

Insert a trajectory foundation before real adapters:

1. **Read-only planner**: already done.
2. **Trajectory schema**: add run/step/tool/score/regression types.
3. **Bronze/Silver/Gold local store layout**.
4. **Normalizer fixture harness**: no runtime needed yet.
5. **Artifact bus**.
6. **DeepAgents read-only adapter**.
7. **Trajectory capture for DeepAgents adapter**.
8. **Regression case creation from failed trajectories**.
9. **OpenClaw adapter**.
10. **Policy gate enforcement**.

This matches the handbook's minimal landing plan:

```text
raw trace -> trajectory_run -> trajectory_step -> tool_call_fact -> score_fact -> regression_case
```

## I. Release Gate Recommendation

Before any real adapter is allowed to mutate files, run shell, send messages, or install MCP:

- forbidden tool use must be zero
- high-risk side effect without approval must be zero
- raw event preservation must be enabled
- trajectory id must be assigned
- tool call facts must be emitted
- approval facts must be emitted
- secrets must be redacted

## J. Final Review Judgment

AgentLegion is directionally strong, but currently incomplete for production-grade agent engineering.

It has a good control-plane spine:

```text
AgentUnit -> CapabilityProfile -> MissionSpec -> PolicySpec -> MissionPlan
```

But it lacks the quality spine:

```text
Trajectory -> Eval -> Root Cause -> Regression -> Replay -> Release Gate
```

The handbook makes clear that production agent systems fail not because they lack another routing abstraction, but because they cannot explain, reproduce, and prevent failures.

Therefore:

> Do not proceed directly from read-only planner to runtime execution. First add trajectory and regression primitives.

That is the main architectural correction.

