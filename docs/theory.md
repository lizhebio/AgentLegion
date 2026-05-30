# AgentLegion Theory

## 1. Thesis

AgentLegion is based on a deliberately constrained thesis:

> A multi-agent system should not attempt to erase runtime differences. It should coordinate heterogeneous agents through explicit capabilities, policies, task contracts, artifacts, and runtime adapters.

This is different from a universal agent manifest. A universal manifest tries to represent all agents with one shared object model. AgentLegion instead assumes that agent runtimes are heterogeneous and often incompatible at the semantic level.

## 2. Why Universal Agent Abstraction Fails

A universal abstraction fails because real agent runtimes differ in ways that are not cosmetic:

- **Streaming**: runtimes emit different event grammars and timing.
- **Tool results**: a result can be a LangGraph `ToolMessage`, an OpenAI-style `tool_result`, a citation source, or a runtime-specific callback payload.
- **Permissions**: approval can mean UI prompt, remote control request, ACL check, sandbox policy, or graph interrupt.
- **Memory**: memory can be DB rows, prompt fragments, vector search, ephemeral user-message injection, or session summary.
- **State**: session history, checkpoint, compacted context, file cache, and subagent relation are not portable.
- **Subagents**: child agents can be graph nodes, forked sessions, background tasks, remote sessions, or isolated child processes.
- **Security**: MCP/tool/server installation, shell execution, file writes, channel sends, and cron are side-effect surfaces.

Therefore the correct abstraction boundary is not "agent internals". The correct boundary is "task, capability, artifact, policy, and adapter".

## 3. The Legion Metaphor

A legion is not a clone army. It is a coordinated organization of specialized units.

Each unit has:

- a role
- capabilities
- limitations
- a chain of command
- rules of engagement
- communication protocols
- reporting formats
- deployment constraints

That is the right mental model for multi-agent systems.

## 4. Key Distinctions

### Agent Unit vs Runtime

An `AgentUnit` is a registered participant in the legion.

A runtime is the native system that executes the unit.

For example:

```text
AgentUnit: repo-reviewer
Runtime: claude-code
Native semantics: AgentDefinition + runAgent + query + sidechain transcript
```

The AgentUnit does not replace the runtime. It describes how the legion can use that runtime safely.

### Capability vs Tool

A tool is a concrete function exposed to a model.

A capability is a higher-level operational claim:

```text
read_files
write_files
run_shell
spawn_subagents
bind_channels
schedule_tasks
review_code
produce_patch
```

Routing should be based on capabilities, not raw tool names.

### Artifact vs Conversation History

Agents should not share full conversation histories by default.

They should exchange artifacts:

- findings
- reports
- plans
- patches
- reviews
- decisions
- evidence bundles

Artifacts are structured, attributable, auditable, and easier to route than raw chat transcripts.

### Orchestration vs Autonomy

AgentLegion does not assume full autonomy.

The orchestrator can run in several modes:

- human-directed
- commander-directed
- fixed pipeline
- router-only
- blackboard
- swarm/market

High-risk side effects should remain human-approved unless explicitly delegated by policy.

## 5. Core Design Laws

### Law 1: Do Not Flatten Runtimes

Never pretend different runtimes have the same execution semantics.

Use runtime adapters and preserve raw native events.

### Law 2: Route by Capability, Not by Name

The task router should select agents based on capability profiles, not model names or prompt names.

### Law 3: Artifacts Are the Shared Memory of the Legion

The legion should coordinate through structured artifacts rather than shared hidden context.

### Law 4: Side Effects Require Policy Gates

File writes, shell execution, network access, MCP installation, secret access, external channel sends, and scheduled runs are controlled actions.

### Law 5: Runtime State Is Runtime-Local

Session history, checkpoints, compacted context, memory, file caches, and subagent parent-child state are not portable unless a specific adapter proves otherwise.

### Law 6: Plans Must Be Auditable Before Execution

Before running a mission, the system should produce an execution plan:

- agents selected
- tools exposed
- permissions required
- artifacts expected
- side effects possible
- approval points
- runtime-specific warnings

### Law 7: Raw Events Must Be Preserved

Normalized events are for UI and cross-runtime workflows. Raw events are for debugging, auditing, and incident response.

## 6. What AgentLegion Is Not

AgentLegion is not:

- a universal agent definition language
- a replacement for native runtimes
- a promise of cross-runtime session migration
- a guarantee of deterministic convergence
- a security boundary by itself
- a prompt template format

AgentLegion is:

- a control-plane architecture
- a capability registry
- a mission orchestration model
- an adapter contract
- a policy and audit framework

