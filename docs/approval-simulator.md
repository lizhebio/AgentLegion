# Approval Simulator

`approve-plan` simulates the control-plane approval gate.

It reads a `CompiledRuntimePlan`, changes selected `pending_approval` runtime plans to either `approved_ready` or `rejected`, and writes immutable local control records.

It does not invoke any runtime.

## Allow One Task

```bash
python3 agentlegion.py approve-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json \
  --task-id implement \
  --decision allow \
  --reason "Approve implementation dry-run handoff only." \
  --decided-by local-operator \
  --output .agentlegion/runtime-plans/mvp-local-refactor-auth.implement-approved.json
```

## Deny One Task

```bash
python3 agentlegion.py approve-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json \
  --task-id decide \
  --decision deny \
  --reason "Commander fallback is not acceptable for final decision." \
  --decided-by local-operator
```

## Allow All Pending Items

```bash
python3 agentlegion.py approve-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.compiled.json \
  --all \
  --decision allow \
  --reason "Local MVP dry-run approval."
```

## Control Records

The simulator writes:

```text
.agentlegion/control/approval-decisions/
.agentlegion/control/audit-events/
```

Each `ApprovalDecision` records:

- runtime plan id
- mission id
- task id
- agent unit id
- runtime class
- approval points
- allow/deny decision
- reason
- actor
- timestamp

Each `AuditEvent` records the same control action in append-only form.

## Phases

Before approval:

```text
pending_approval
```

After allow:

```text
approved_ready
```

After deny:

```text
rejected
```

The simulator skips runtime plans that are not `pending_approval` and records an `approval_skipped` audit entry in the command output.

## Safety Boundary

Approval changes control-plane state only. It does not execute command previews, does not call Hermes, does not call DeepAgents, and does not perform side effects.

## Next Gate

Use `execute-plan` after approval to run only simulator-safe runtime plans.

```bash
python3 agentlegion.py execute-plan \
  .agentlegion/runtime-plans/mvp-local-refactor-auth.plan-approved.json \
  --task-id plan
```

The current execution simulator runs only DeepAgents `local_smoke` plans. Hermes remains non-executed.
