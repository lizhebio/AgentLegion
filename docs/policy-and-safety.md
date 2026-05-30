# Policy and Safety Model

## 1. Default-Deny Principle

AgentLegion assumes default deny for high-risk actions:

- shell execution
- filesystem write
- network egress
- MCP/server installation
- secret access
- external channel send
- scheduled automation
- subagent spawning
- browser control
- database mutation

Agents must be explicitly granted these capabilities by policy.

## 2. Policy Categories

| Category | Examples |
|---|---|
| Tool policy | allow/deny/ask for specific tools or tool classes |
| Filesystem policy | read/write paths, patch application, checkpoint requirement |
| Shell policy | command execution, timeout, sandbox backend |
| Network policy | egress targets, HTTP tools, MCP servers |
| Secret policy | secret refs, injection scope, redaction |
| Channel policy | Slack/Telegram/email/Discord sends |
| Schedule policy | cron, heartbeat, automation |
| Subagent policy | spawn depth, allowed targets, concurrency |
| Artifact policy | who can read/write artifacts |

## 3. Approval States

Approval is not a static boolean.

It is a runtime state machine:

- `not_required`
- `requested`
- `pending`
- `approved`
- `denied`
- `expired`
- `unavailable`
- `failed`

Adapters must expose native approval payloads when available.

## 4. MCP and Tool Installation Risk

MCP servers and dynamically loaded tools are code execution surfaces.

AgentLegion should require:

- trusted registry or allowlist
- checksum or signature
- declared permissions
- sandbox class
- secret scope
- network policy
- human approval
- audit record

## 5. Secrets

Manifests must not store secret values.

Use secret references:

```yaml
secrets:
  - ref: provider/openai/api_key
    scope: runtime
```

Adapters must redact secrets from:

- prompts
- logs
- raw events where possible
- artifacts
- tool result summaries

## 6. External Side Effects

External side effects include:

- sending messages
- writing files
- applying patches
- executing commands
- calling APIs
- scheduling future runs
- modifying databases

Any mission that includes external side effects should have an explicit side-effect plan and approval checkpoint.

## 7. Audit Requirements

Audit records should include:

- mission id
- task id
- agent unit id
- runtime class
- adapter version
- effective policy
- runtime plan
- exposed tools
- approvals
- raw events
- normalized events
- artifacts produced
- side effects performed

