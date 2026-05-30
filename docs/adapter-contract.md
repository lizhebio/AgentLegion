# Runtime Adapter Contract

## 1. Purpose

Runtime adapters are the boundary between AgentLegion and native agent runtimes.

They must not hide native semantics. They should expose capabilities, compile plans, invoke runtimes, normalize events, and preserve raw payloads.

## 2. TypeScript Reference Interface

```ts
export interface RuntimeAdapter {
  readonly runtimeClass: string;

  capabilities(): Promise<RuntimeCapabilities> | RuntimeCapabilities;

  validateUnit(unit: AgentUnit): Promise<ValidationResult> | ValidationResult;

  validateTask(unit: AgentUnit, task: AgentTask): Promise<ValidationResult> | ValidationResult;

  plan(input: {
    unit: AgentUnit;
    task: AgentTask;
    policy: EffectivePolicy;
    context: MissionContext;
  }): Promise<RuntimePlan> | RuntimePlan;

  invoke(plan: RuntimePlan): AsyncIterable<AgentEvent>;

  status?(handle: RuntimeHandle): Promise<RuntimeStatus>;

  cancel?(handle: RuntimeHandle, reason?: string): Promise<void>;

  approve?(handle: RuntimeHandle, decision: ApprovalDecision): Promise<void>;

  exportState?(handle: RuntimeHandle): Promise<RuntimeStateSnapshot>;

  normalizeEvent?(raw: unknown): AgentEvent;
}
```

## 3. Required Capabilities

Every adapter must report:

- supported input types
- supported output types
- supported event types
- tool exposure mechanism
- permission mechanism
- approval mechanism
- cancellation support
- session/resume support
- sandbox support
- raw event availability

## 4. Non-Goals

Adapters should not:

- pretend unsupported runtime behavior is supported
- silently drop raw events
- silently expand permissions
- translate runtime-local state into fake portable state
- install tools/MCP servers without policy approval

## 5. Trajectory Write Path

Every adapter must eventually write through the trajectory spine:

```text
Runtime native event
  -> AgentEvent envelope
  -> Bronze raw event
  -> EventNormalizer
  -> Silver facts
  -> Gold regression/eval assets when failures are accepted
```

The minimum implementation can use the local CLI path:

```bash
python3 agentlegion.py ingest-events events.json \
  --trajectory-id <trajectory-id> \
  --session-id <runtime-session-id> \
  --agent-version <adapter-agent-version> \
  --task-type <task-type>
```

Adapters should treat normalized facts as the portable analysis layer and raw event payloads as the source of truth when runtime-specific behavior matters.

## 6. Runtime-Specific Notes

### DeepAgents

Maps naturally to:

- `create_deep_agent(...)`
- LangGraph compiled graph
- middleware stack
- checkpointer/store
- `SubAgent`

### OpenClaw

Maps naturally to:

- `AgentConfig`
- `AgentDefaultsConfig`
- channel bindings
- heartbeat
- sandbox
- event stream
- session/subagent registry

### Claude Code

Must preserve:

- `AgentDefinition`
- `runAgent(...)`
- sidechain transcript
- permission precedence
- MCP lifecycle
- prompt-cache-sensitive behavior
- remote/background/fork semantics

### Hermes

Must preserve:

- `init_agent(...)`
- `run_conversation(...)`
- checkpoint manager
- session DB
- delegate child `AIAgent`
- tool registry

### open-webui

Should be treated as:

- chat adapter
- tool/function provider
- memory/chat backend
- UI/channel surface

It should not be treated as a full autonomous agent runtime unless an explicit harness is added.
