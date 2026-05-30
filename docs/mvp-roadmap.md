# MVP Roadmap

## Phase 0: Specification

Goal: define the control-plane model.

Deliverables:

- AgentUnit schema
- CapabilityProfile schema
- LegionPlan schema
- MissionSpec schema
- PolicySpec schema
- RuntimeAdapter contract
- example software engineering legion

## Phase 1: Local Planner

Goal: turn a mission into a plan without invoking agents.

Features:

- load AgentUnits
- load LegionPlan
- load PolicySpec
- validate MissionSpec
- rank candidate agents by capabilities
- emit MissionPlan
- emit risk warnings

## Phase 2: Artifact Bus

Goal: structure inter-agent communication.

Features:

- local artifact store
- artifact ids
- content refs
- evidence refs
- producer attribution
- mission/task linkage

## Phase 3: Trajectory / Eval / Regression Spine

Goal: make every future runtime execution auditable and replayable before invoking real agents.

Features:

- local Bronze/Silver/Gold store
- raw trace and raw event preservation
- `TrajectoryRun`
- `TrajectoryStep`
- `ToolCallFact`
- `ScoreFact`
- `RegressionCase`
- `ReplaySnapshot`
- trajectory diff placeholder
- release gate placeholder

Required CLI:

```bash
python3 agentlegion.py init-store
python3 agentlegion.py inspect-store
```

## Phase 4: First Runtime Adapter

Recommended first adapter: DeepAgents.

Why:

- clear `create_deep_agent(...)` entrypoint
- graph-oriented execution
- explicit subagent support
- checkpointer/store support

## Phase 5: Control-Plane Runtime Adapter

Recommended second adapter: OpenClaw.

Why:

- session/gateway runtime
- channel binding
- heartbeat
- sandbox config
- event stream
- subagent registry

## Phase 6: Mission Orchestrator

Goal: execute a fixed software engineering workflow.

Workflow:

```text
research -> plan -> implement -> review -> approve -> apply -> audit
```

## Phase 7: Policy Gate

Goal: enforce default-deny side-effect policy.

Features:

- file write approval
- shell approval
- MCP install approval
- channel send approval
- scheduled run approval
- audit log

## Phase 8: Additional Runtime Adapters

Candidates:

- Claude Code
- Hermes
- open-webui-chat

## Non-Goals for MVP

Do not implement in MVP:

- cross-runtime state migration
- universal session resume
- universal sandbox semantics
- fully autonomous long-running swarm
- MCP installation without approval
- external channel send without approval
