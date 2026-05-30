# MVP Local Test

This test validates the first local AgentLegion MVP formation:

```text
Hermes Coder + DeepAgents Researcher
```

The goal is not full autonomous execution yet. The goal is to prove that AgentLegion can:

1. register both local runtimes as `AgentUnit` resources,
2. validate the local legion manifest,
3. confirm Hermes is deployed and reachable through its safe CLI surface,
4. construct and invoke a local DeepAgents graph,
5. normalize DeepAgents runtime events into the Bronze/Silver trajectory store.

## Local Resources

`examples/mvp-local-legion.yaml` declares:

- `deepagents-researcher`
- `hermes-coder`

DeepAgents uses the local SDK at:

```text
../deepagents/libs/deepagents
```

Hermes uses the deployed CLI:

```text
hermes
```

## Environment

DeepAgents requires Python 3.11 or newer. The local MVP test uses `.venv`:

```bash
uv venv --python 3.11 .venv
uv pip install -e ../deepagents/libs/deepagents
```

`.venv/` is ignored by git.

## Smoke Test

Run:

```bash
python3 agentlegion.py mvp-smoke
```

The command performs two checks:

- Hermes: runs `hermes --help` only. It does not start a live Hermes task.
- DeepAgents: runs `scripts/deepagents_smoke.py` with a fake tool-binding model. It constructs a real DeepAgents graph and invokes it without calling an external LLM provider.

The DeepAgents smoke test writes `AgentEvent` JSON to:

```text
.agentlegion/fixtures/mvp-deepagents-smoke.events.json
```

Then AgentLegion ingests those events into:

```text
.agentlegion/bronze/raw-events/
.agentlegion/silver/trajectory-runs/
.agentlegion/silver/trajectory-steps/
.agentlegion/silver/message-events/
```

## Expected Output

The final report should contain:

```json
{
  "ok": true,
  "checks": [
    {"runtime": "hermes", "ok": true},
    {"runtime": "deepagents", "ok": true}
  ]
}
```

The DeepAgents result should include:

```json
{
  "final": "deepagents smoke ok",
  "modelCallCount": 1,
  "boundToolCount": 8,
  "versions": {
    "deepagents": "0.6.3"
  }
}
```

## Safety Boundary

This MVP test deliberately avoids side effects:

- no Hermes task invocation,
- no file writes outside `.agentlegion/`,
- no shell execution by either runtime,
- no external LLM call,
- no MCP installation,
- no channel send.

The next step is an adapter-level dry run that turns a `MissionPlan` step into runtime-specific commands without executing side-effecting tools.
