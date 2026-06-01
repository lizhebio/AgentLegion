# Execution Simulator

`execute-plan` is the first safe execution gate.

It reads an approved `CompiledRuntimePlan` and executes only runtime plans that the local simulator knows are safe.

For the current MVP:

- DeepAgents `local_smoke` plans can execute.
- Hermes plans are never executed. They remain command previews and are recorded as skipped.

## Approve A DeepAgents Step

The `plan` step is routed to DeepAgents in the local MVP fallback. Approve it first:

```bash
python3 agentlegion.py approve-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json \
  --task-id plan \
  --decision allow \
  --reason "Approve DeepAgents planning dry-run." \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json
```

## Execute The Approved DeepAgents Step

```bash
python3 agentlegion.py execute-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json \
  --task-id plan \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-executed.json
```

The simulator runs:

```text
.venv/bin/python scripts/deepagents_smoke.py
```

It writes runtime events to `.agentlegion/fixtures/`, ingests them into Bronze/Silver, and writes an `ExecutionRecord`.

## Hermes Safety Behavior

If a Hermes plan is approved and passed to `execute-plan`, the simulator records:

```text
approved_not_executed
```

It does not run:

```text
hermes chat -q ...
```

This is intentional. Hermes is write-capable in the MVP legion, so real execution needs a stricter adapter, sandbox, workspace isolation, and policy enforcement.

## Control Records

The simulator writes:

```text
.agentlegion/control/execution-records/
.agentlegion/control/audit-events/
```

Each execution record includes:

- runtime plan id
- mission id
- task id
- agent unit id
- runtime class
- phase before execution
- status
- command for DeepAgents safe smoke runs
- trajectory id
- ingest summary
- start/end timestamps

## Safety Boundary

The simulator does not:

- execute Hermes,
- run arbitrary shell commands,
- write workspace files,
- install MCP servers,
- call external LLM providers,
- send external messages.

It only executes the DeepAgents fake-model smoke path and captures trajectory facts.
