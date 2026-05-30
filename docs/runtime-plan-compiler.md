# Runtime Plan Compiler

`compile-runtime-plan` is the first adapter-level dry-run step.

It converts a mission plus legion roster into runtime-specific execution plans without invoking any runtime task.

```bash
python3 agentlegion.py compile-runtime-plan \
  --legion examples/mvp-local-legion.yaml \
  --legion-name mvp-local-legion \
  --mission examples/mission-refactor-auth.yaml \
  --policy examples/policy-default-deny.yaml \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json
```

## What It Produces

The output kind is:

```text
CompiledRuntimePlan
```

Each `runtimePlans[]` item contains:

- `runtimeClass`
- `agentUnitId`
- `taskId`
- `phase`
- `nativeConfig`
- `permissionPlan`
- `sandboxPlan`
- `expectedArtifacts`
- `approvalPoints`
- `warnings`
- `unsupported`

## Phases

`ready_dry_run` means the task can be dry-run compiled without policy approval.

`pending_approval` means the task has side effects that are allowed only after an approval step. For the MVP policy, filesystem writes and shell execution usually land here.

`blocked` means policy denies the task or the compiler cannot produce a compatible runtime plan.

## Runtime Mapping

DeepAgents maps to:

```text
.venv/bin/python scripts/deepagents_smoke.py
```

The dry-run native config includes a `createDeepAgent` block with model, system prompt, tools, checkpointer, and store fields. In dry-run mode, the model is `agentlegion-tool-binding-fake`.

Hermes maps to a command preview only:

```text
hermes chat -q "<task>"
```

AgentLegion does not invoke `hermes chat` during compile. The command preview exists to show what a future adapter would execute after policy approval.

## MVP Findings

For `examples/mvp-local-legion.yaml`, the current compiler result is expected to show:

```text
total: 5
ready: 2
pendingApproval: 3
blocked: 0
```

This MVP legion only has DeepAgents and Hermes. Commander and reviewer roles are temporarily routed to the available local runtimes, so the compiler intentionally emits role-mismatch warnings:

- commander -> DeepAgents or Hermes fallback
- reviewer -> DeepAgents fallback

Those warnings are useful. They show where the next runtimes should be attached:

- OpenClaw for commander/session/channel orchestration
- Claude Code or another reviewer runtime for review-only work

## Safety Boundary

The compiler does not:

- invoke DeepAgents,
- invoke Hermes,
- write workspace files,
- run shell commands,
- install MCP servers,
- send channel messages.

It only emits runtime plans and policy state.

## Next Gate

Use `approve-plan` to move selected `pending_approval` runtime plans into `approved_ready` or `rejected` without executing them.

```bash
python3 agentlegion.py approve-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json \
  --task-id implement \
  --decision allow \
  --reason "Approve implementation dry-run handoff only."
```
