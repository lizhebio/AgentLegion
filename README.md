# AgentLegion

AgentLegion is a control-plane architecture for organizing heterogeneous AI agents into a governed, auditable, task-oriented legion.

It starts from a practical observation:

> Do not try to make all agents the same. Make their capabilities, constraints, runtime adapters, artifacts, policies, and mission workflows explicit.

AgentLegion is not a universal agent manifest. It is a framework for managing many different agents, each with different runtimes, tools, permissions, memory behavior, state semantics, and operational risks.

## Why This Exists

Modern agent systems are becoming fragmented:

- Some agents are graph-native, such as DeepAgents / LangGraph-style systems.
- Some agents are coding specialists, such as Claude Code-style subagents.
- Some agents are gateway/session/channel runtimes, such as OpenClaw-style systems.
- Some agents are local tool runners, such as Hermes-style agents.
- Some systems are not autonomous agents at all, but provide chat surfaces, tools, functions, memory, or UI, such as open-webui.

Trying to flatten all of them into one Helm-like `AgentChart` abstraction hides the most important differences:

- tool result injection
- streaming event format
- approval flow
- sandbox semantics
- memory loading
- context compaction
- session/checkpoint state
- subagent parent-child lifecycle
- hooks, feature flags, and provider-specific schema normalization

AgentLegion takes the opposite approach:

```text
Expose differences.
Model capabilities.
Route missions.
Preserve raw runtime events.
Govern side effects.
Use adapters instead of pretending runtimes are equivalent.
```

## Core Concepts

AgentLegion is built around seven layers:

1. **Agent Registry**: the roster of all agent units.
2. **Capability Profile**: what each agent can do, cannot do, and under what risk level.
3. **Runtime Adapter**: how to invoke each native runtime and normalize events.
4. **Task Router**: how to select the right agent for a task.
5. **Orchestrator / Commander**: how to decompose and coordinate missions.
6. **Artifact Bus**: how agents exchange structured outputs without sharing all internal state.
7. **Policy / Audit / Control Plane**: how permissions, approvals, side effects, and telemetry are governed.

## Repository Structure

```text
docs/
  theory.md              AgentLegion theoretical foundation
  architecture.md        Control-plane architecture
  object-model.md        Core resource model
  adapter-contract.md    Runtime adapter contract
  policy-and-safety.md   Security model and risk controls
  implementation-guide.md Practical implementation sequence
  mvp-roadmap.md         Practical implementation phases
  reviews/               Architecture reviews and critique
  adr/
    0001-agentlegion-not-agentchart.md

schemas/
  agentlegion.types.ts   TypeScript reference types
  agent-unit.schema.yaml Example AgentUnit schema shape
  legion-plan.schema.yaml Example LegionPlan schema shape
  mission-spec.schema.yaml Example MissionSpec schema shape
  policy-spec.schema.yaml Example PolicySpec schema shape
  trajectory-*.yaml       Trajectory and regression schema shapes

examples/
  software-engineering-legion.yaml
  mission-refactor-auth.yaml
  policy-default-deny.yaml
```

## Minimal Resource Set

AgentLegion uses several separate resources instead of one overloaded manifest:

- `AgentUnit`: a single agent in the legion.
- `CapabilityProfile`: machine-readable capabilities and limitations.
- `LegionPlan`: the composition of a legion.
- `MissionSpec`: a task or campaign for the legion to execute.
- `PolicySpec`: global or scoped safety rules.
- `RuntimePlan`: adapter-compiled native execution plan.
- `Artifact`: structured outputs exchanged between agents.
- `TrajectoryRun`, `TrajectoryStep`, `ToolCallFact`, and `ScoreFact`: normalized facts for debugging and evaluation.
- `RegressionCase` and `ReplaySnapshot`: failure assets for replay and release gates.

## Design Principle

The most important design principle is:

> Unify tasks, capabilities, policies, artifacts, and events. Do not unify runtime internals.

This means:

- A DeepAgents subagent is not the same thing as a Claude Code background agent.
- An OpenClaw session is not the same thing as a Hermes child `AIAgent`.
- An open-webui chat pipeline is not the same thing as an autonomous agent runtime.
- A LangGraph `ToolMessage` is not the same thing as an open-webui `sources` entry.

AgentLegion treats these as native runtime semantics and accesses them through adapters.

## Recommended MVP

The recommended MVP should start with:

- one Commander
- one Researcher
- one Coder
- one Reviewer
- one Artifact Bus
- one default-deny Policy Gate
- two runtime adapters: DeepAgents and OpenClaw

The first mission type should be software engineering work:

```text
Analyze -> Plan -> Implement -> Review -> Approve -> Apply -> Audit
```

Before write-capable runtime adapters are enabled, the MVP must initialize the trajectory/evaluation/regression store:

```bash
python3 agentlegion.py init-store
python3 agentlegion.py inspect-store
```

The store follows a Bronze/Silver/Gold layout:

- Bronze: raw runtime events, traces, tool returns, and scores.
- Silver: normalized trajectory facts.
- Gold: regression cases, replay snapshots, trajectory diffs, eval reports, and release gates.

The quality spine also has local commands for the first failure-to-regression loop:

```bash
python3 agentlegion.py write-fixture-events
python3 agentlegion.py ingest-events .agentlegion/fixtures/agent-events.fixture.json --trajectory-id fixture-trajectory-001 --session-id fixture-session-001
python3 agentlegion.py record-score --target-type trajectory_run --target-id fixture-trajectory-001 --score-name task_success --score-type binary --score-value true --evaluator-type human
python3 agentlegion.py promote-regression-case --trajectory-id fixture-trajectory-001 --root-cause-category "Tool Arguments" --severity medium --regression-priority P1 --replay-input "..." --expected-behavior "..."
```

## Read-Only Planner CLI

This repository includes a small read-only planner:

```bash
python3 agentlegion.py validate examples/software-engineering-legion.yaml examples/mission-refactor-auth.yaml examples/policy-default-deny.yaml
```

Generate a mission plan without invoking any agent runtime:

```bash
python3 agentlegion.py plan \
  --legion examples/software-engineering-legion.yaml \
  --mission examples/mission-refactor-auth.yaml \
  --policy examples/policy-default-deny.yaml \
  --output .agentlegion/runtime-plans/refactor-auth-module.json
```

The planner currently:

- loads multi-document YAML resources
- validates minimal resource shape
- indexes AgentUnits, LegionPlans, MissionSpecs, and PolicySpecs
- selects candidate agents by role and capability profile
- explains routing decisions
- performs advisory policy checks for inferred side effects
- emits a read-only `MissionPlan`

It does not invoke agents, install tools, access secrets, run shell commands, or modify workspaces.

## Status

This repository is currently a specification and architecture workspace.

The immediate goal is to validate the theory through a read-only planner and a local trajectory/evaluation/regression spine before implementing runtime adapters and controllers.
