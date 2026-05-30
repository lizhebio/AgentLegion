# ADR 0001: AgentLegion Is Not AgentChart

## Status

Accepted.

## Context

Earlier exploration considered a Helm-like `AgentChart` for declaring agents as portable runtime resource bundles.

Source-level review of multiple agent runtimes showed that this idea is only partially valid. Runtimes differ in non-portable semantics:

- streaming event format
- tool result injection
- approval flow
- sandbox semantics
- memory loading
- context compaction
- checkpoint and resume
- subagent lifecycle
- hooks and feature flags
- MCP/tool/server installation

Therefore a universal agent manifest would either be too weak to be useful or too strong to be true.

## Decision

AgentLegion will not attempt to define a universal agent manifest.

Instead it will define:

- `AgentUnit`
- `CapabilityProfile`
- `LegionPlan`
- `MissionSpec`
- `PolicySpec`
- `RuntimePlan`
- `Artifact`
- `RuntimeAdapter`

The system will coordinate heterogeneous agents by capability and policy, not by pretending their runtimes are equivalent.

## Consequences

Positive:

- runtime differences remain visible
- adapters can preserve native semantics
- safety and audit become first-class
- multi-agent orchestration becomes explicit

Negative:

- less elegant than a single manifest
- more engineering work in adapters
- requires capability modeling
- requires policy and artifact infrastructure

## Principle

Unify missions, capabilities, artifacts, policies, and events. Do not unify runtime internals.

