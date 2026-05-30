# Implementation Guide

This guide describes how to turn the AgentLegion specification into a working system.

## 1. Start With Read-Only Planning

The first implementation should not invoke agents.

Build a planner that can:

1. load `AgentUnit` resources
2. load a `LegionPlan`
3. load a `PolicySpec`
4. load a `MissionSpec`
5. validate schemas
6. match mission steps to agent capabilities
7. emit a `MissionPlan`
8. report unsupported fields and side-effect risks

This gives immediate value without runtime risk.

## 2. Implement the Agent Registry

The registry can start as a local YAML loader.

Minimum operations:

- `listUnits()`
- `getUnit(id)`
- `findByRole(role)`
- `findByCapability(query)`
- `validateUnit(unit)`

Later it can become a database-backed service.

## 3. Implement Capability Matching

Capability matching should be explicit and explainable.

Recommended scoring factors:

- domain match
- required action match
- input type compatibility
- output type compatibility
- trust level
- side-effect risk
- current availability
- mission policy compatibility

The router should return not only the selected agent, but also why it was selected.

## 4. Implement the Artifact Bus

Start with a local directory:

```text
.agentlegion/
  artifacts/
  events/
  missions/
  runtime-plans/
```

Every artifact should have:

- id
- type
- producer
- mission id
- task id
- content reference
- evidence references
- status

## 5. Implement the Trajectory / Eval / Regression Spine

Before invoking real runtimes, initialize the local quality store:

```text
.agentlegion/
  bronze/raw-events/
  bronze/raw-traces/
  bronze/raw-scores/
  silver/trajectory-runs/
  silver/trajectory-steps/
  silver/tool-call-facts/
  silver/score-facts/
  gold/regression-cases/
  gold/replay-snapshots/
  gold/eval-reports/
  gold/release-gates/
```

Minimum rule:

```text
raw trace -> trajectory_run -> trajectory_step -> tool_call_fact -> score_fact -> regression_case
```

Runtime adapters must preserve raw runtime payloads in Bronze and emit normalized facts in Silver. Gold objects are curated assets used for replay, release gates, and quality reports.

Use:

```bash
python3 agentlegion.py init-store
python3 agentlegion.py inspect-store
python3 agentlegion.py ingest-events events.json --trajectory-id <id> --session-id <id>
python3 agentlegion.py record-score --target-type trajectory_run --target-id <id> --score-name task_success --score-type binary --score-value false --evaluator-type human
python3 agentlegion.py promote-regression-case --trajectory-id <id> --root-cause-category Planning --severity high --regression-priority P0 --replay-input "..." --expected-behavior "..."
```

## 6. Implement the First Adapter: DeepAgents

DeepAgents is the best first adapter because its runtime entrypoint maps cleanly to a plan:

- model
- tools
- system prompt
- subagents
- skills
- memory
- permissions
- backend
- interrupt_on
- checkpointer
- store

The first adapter can support only:

- read-only research tasks
- file search/read tools
- report artifacts
- normalized message/tool/error events

## 7. Implement the Second Adapter: OpenClaw

OpenClaw is the best second adapter because it exercises the control plane:

- persistent sessions
- channel bindings
- heartbeat
- sandbox config
- subagent policy
- event stream

Do not enable channel sends or heartbeat by default. Require policy approval.

## 8. Add Policy Gates Before Side Effects

Before any adapter can perform a side effect, it must ask the policy gate.

Controlled side effects:

- filesystem write
- patch apply
- shell execute
- network egress
- MCP install
- secret read
- external channel send
- schedule create
- subagent spawn

The policy gate returns:

- allow
- deny
- ask

If the answer is `ask`, the mission enters `pending_approval`.

## 9. Preserve Raw Events

Every adapter should emit normalized events and store raw runtime payloads.

Do not debug from normalized events alone.

## 10. Do Not Implement Cross-Runtime Resume in MVP

Runtime-local resume is allowed.

Cross-runtime resume should be treated as a separate research project. For MVP, export summaries and artifacts, not full runtime state.

## 11. Suggested CLI Shape

```bash
agentlegion validate examples/software-engineering-legion.yaml
agentlegion init-store
agentlegion inspect-store
agentlegion plan examples/mission-refactor-auth.yaml --legion examples/software-engineering-legion.yaml --policy examples/policy-default-deny.yaml
agentlegion run .agentlegion/runtime-plans/refactor-auth-module.json
agentlegion status refactor-auth-module
agentlegion artifacts refactor-auth-module
```

The current repository includes the first cut as a Python script:

```bash
python3 agentlegion.py validate examples/software-engineering-legion.yaml examples/mission-refactor-auth.yaml examples/policy-default-deny.yaml

python3 agentlegion.py init-store
python3 agentlegion.py inspect-store

python3 agentlegion.py plan \
  --legion examples/software-engineering-legion.yaml \
  --mission examples/mission-refactor-auth.yaml \
  --policy examples/policy-default-deny.yaml \
  --output .agentlegion/runtime-plans/refactor-auth-module.json
```

The generated plan is intentionally read-only. It is safe to inspect because no RuntimeAdapter is invoked.

## 12. Success Criteria for MVP

The MVP is successful when it can:

- load a legion
- explain which agent should do each mission step
- reject unsafe side effects by default
- produce a runtime plan
- invoke at least one read-only agent
- produce structured artifacts
- preserve raw events
- normalize trajectory facts
- convert failures into regression cases
- produce an audit trail
