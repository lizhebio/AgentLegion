#!/usr/bin/env python3
"""Read-only AgentLegion planner CLI.

This intentionally does not invoke any runtime. It loads AgentUnit,
LegionPlan, PolicySpec, and MissionSpec YAML resources, validates the minimal
shape, ranks candidate agents by capability, and emits an auditable mission
plan.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


Resource = dict[str, Any]


STORE_DIRECTORIES = [
    "bronze/raw-events",
    "bronze/raw-traces",
    "bronze/raw-scores",
    "silver/trajectory-runs",
    "silver/trajectory-steps",
    "silver/message-events",
    "silver/llm-call-facts",
    "silver/tool-call-facts",
    "silver/retrieval-facts",
    "silver/state-transition-facts",
    "silver/artifact-facts",
    "silver/score-facts",
    "gold/regression-cases",
    "gold/replay-snapshots",
    "gold/trajectory-diffs",
    "gold/eval-reports",
    "gold/release-gates",
    "artifacts",
    "runtime-plans",
]

FACT_DIRECTORIES = {
    "TrajectoryRun": "silver/trajectory-runs",
    "TrajectoryStep": "silver/trajectory-steps",
    "MessageEvent": "silver/message-events",
    "LLMCallFact": "silver/llm-call-facts",
    "ToolCallFact": "silver/tool-call-facts",
    "RetrievalFact": "silver/retrieval-facts",
    "StateTransitionFact": "silver/state-transition-facts",
    "ArtifactFact": "silver/artifact-facts",
    "ScoreFact": "silver/score-facts",
    "RegressionCase": "gold/regression-cases",
    "ReplaySnapshot": "gold/replay-snapshots",
    "TrajectoryDiff": "gold/trajectory-diffs",
    "ReleaseGate": "gold/release-gates",
}

ROOT_CAUSE_CATEGORIES = [
    "Intent",
    "Planning",
    "Tool Selection",
    "Tool Arguments",
    "Observation Use",
    "Retrieval",
    "State",
    "Recovery",
    "Artifact",
    "Policy / Safety",
    "Infrastructure",
    "Evaluation",
]


@dataclass
class Diagnostic:
    level: str
    message: str
    resource: str | None = None

    def to_dict(self) -> dict[str, str]:
        data = {"level": self.level, "message": self.message}
        if self.resource:
            data["resource"] = self.resource
        return data


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(data: Any) -> str:
    return hashlib.sha256(stable_json(data).encode("utf-8")).hexdigest()


def safe_id(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            safe.append(char)
        else:
            safe.append("-")
    return "".join(safe).strip("-") or "unknown"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def content_ref(path: Path, root: Path) -> Resource:
    raw = path.read_bytes()
    return {
        "uri": str(path.relative_to(root)),
        "mediaType": "application/json",
        "hash": hashlib.sha256(raw).hexdigest(),
        "sizeBytes": len(raw),
    }


def read_json_or_jsonl(path: Path) -> list[Resource]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"{path}: expected JSON array")
        if not all(isinstance(item, dict) for item in data):
            raise ValueError(f"{path}: every event must be an object")
        return data

    events = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        events.append(item)
    return events


def parse_scalar(value: str) -> str | int | float | bool:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_yaml_documents(path: Path) -> list[Resource]:
    with path.open("r", encoding="utf-8") as f:
        docs = [doc for doc in yaml.safe_load_all(f) if doc is not None]
    for doc in docs:
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: expected YAML document object, got {type(doc).__name__}")
    return docs


def load_resources(paths: list[Path]) -> list[Resource]:
    resources: list[Resource] = []
    for path in paths:
        if path.is_dir():
            for child in sorted(path.rglob("*.yaml")):
                resources.extend(load_yaml_documents(child))
            for child in sorted(path.rglob("*.yml")):
                resources.extend(load_yaml_documents(child))
        else:
            resources.extend(load_yaml_documents(path))
    return resources


def resource_id(resource: Resource) -> str:
    metadata = resource.get("metadata") or {}
    return str(metadata.get("id") or metadata.get("name") or "<unknown>")


def validate_resource(resource: Resource) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    kind = resource.get("kind")
    rid = resource_id(resource)

    if resource.get("apiVersion") != "agentlegion.dev/v0":
        diagnostics.append(Diagnostic("error", "apiVersion must be agentlegion.dev/v0", rid))
    if not kind:
        diagnostics.append(Diagnostic("error", "missing kind", rid))
        return diagnostics
    if not isinstance(resource.get("metadata"), dict):
        diagnostics.append(Diagnostic("error", "missing metadata object", rid))

    if kind == "AgentUnit":
        diagnostics.extend(validate_agent_unit(resource))
    elif kind == "LegionPlan":
        diagnostics.extend(validate_legion_plan(resource))
    elif kind == "MissionSpec":
        diagnostics.extend(validate_mission_spec(resource))
    elif kind == "PolicySpec":
        diagnostics.extend(validate_policy_spec(resource))
    else:
        diagnostics.append(Diagnostic("warning", f"unknown kind {kind!r}; skipped by planner", rid))

    return diagnostics


def validate_agent_unit(unit: Resource) -> list[Diagnostic]:
    rid = resource_id(unit)
    diagnostics: list[Diagnostic] = []
    runtime = unit.get("runtime") or {}
    capabilities = unit.get("capabilities") or {}
    interfaces = unit.get("interfaces") or {}
    safety = unit.get("safety") or {}

    required = [
        ("metadata.id", (unit.get("metadata") or {}).get("id")),
        ("metadata.description", (unit.get("metadata") or {}).get("description")),
        ("runtime.class", runtime.get("class")),
        ("runtime.adapter", runtime.get("adapter")),
        ("capabilities.domains", capabilities.get("domains")),
        ("capabilities.actions", capabilities.get("actions")),
        ("interfaces.input", interfaces.get("input")),
        ("interfaces.output", interfaces.get("output")),
        ("safety.trustLevel", safety.get("trustLevel")),
    ]
    for field, value in required:
        if value in (None, "", [], {}):
            diagnostics.append(Diagnostic("error", f"AgentUnit missing {field}", rid))
    return diagnostics


def validate_legion_plan(plan: Resource) -> list[Diagnostic]:
    rid = resource_id(plan)
    diagnostics: list[Diagnostic] = []
    if not plan.get("units"):
        diagnostics.append(Diagnostic("error", "LegionPlan missing units", rid))
    if not plan.get("roles"):
        diagnostics.append(Diagnostic("error", "LegionPlan missing roles", rid))
    return diagnostics


def validate_mission_spec(mission: Resource) -> list[Diagnostic]:
    rid = resource_id(mission)
    diagnostics: list[Diagnostic] = []
    if not mission.get("goal"):
        diagnostics.append(Diagnostic("error", "MissionSpec missing goal", rid))
    workflow = mission.get("workflow")
    if not workflow:
        diagnostics.append(Diagnostic("error", "MissionSpec missing workflow", rid))
    elif not isinstance(workflow, list):
        diagnostics.append(Diagnostic("error", "MissionSpec workflow must be a list", rid))
    return diagnostics


def validate_policy_spec(policy: Resource) -> list[Diagnostic]:
    rid = resource_id(policy)
    diagnostics: list[Diagnostic] = []
    defaults = policy.get("defaults") or {}
    if defaults.get("effect") not in {"allow", "deny", "ask"}:
        diagnostics.append(Diagnostic("error", "PolicySpec defaults.effect must be allow, deny, or ask", rid))
    if not isinstance(policy.get("rules"), list):
        diagnostics.append(Diagnostic("error", "PolicySpec rules must be a list", rid))
    return diagnostics


def index_resources(resources: list[Resource]) -> dict[str, Any]:
    index: dict[str, Any] = {
        "AgentUnit": {},
        "LegionPlan": {},
        "MissionSpec": {},
        "PolicySpec": {},
    }
    for resource in resources:
        kind = resource.get("kind")
        if kind in index:
            index[kind][resource_id(resource)] = resource
    return index


def flatten_role_agents(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def agents_for_role(legion: Resource, role: str) -> list[str]:
    roles = legion.get("roles") or {}
    return flatten_role_agents(roles.get(role))


def action_key(action: str) -> str:
    if "." in action:
        # filesystem.write -> writeFiles, shell.execute -> runShell
        resource, operation = action.split(".", 1)
        known = {
            ("filesystem", "read"): "readFiles",
            ("filesystem", "write"): "writeFiles",
            ("shell", "execute"): "runShell",
            ("mcp", "install"): "useMcp",
            ("channel", "send"): "sendMessages",
            ("schedule", "create"): "scheduleTasks",
            ("subagent", "spawn"): "spawnSubagents",
        }
        return known.get((resource, operation), action)
    return action


def score_agent(unit: Resource, step: Resource, role: str | None) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []
    capabilities = unit.get("capabilities") or {}
    domains = set(capabilities.get("domains") or [])
    actions = capabilities.get("actions") or {}
    interfaces = unit.get("interfaces") or {}
    outputs = set(interfaces.get("output") or [])
    safety = unit.get("safety") or {}

    task_text = " ".join(str(step.get(k, "")) for k in ("id", "task", "expectedOutput")).lower()
    expected = str(step.get("expectedOutput") or "")

    if role and role in str((unit.get("metadata") or {}).get("labels", {})):
        score += 8
        reasons.append(f"metadata label matches role {role}")

    if role:
        role_domain_map = {
            "researcher": ["source_research", "architecture_analysis", "evidence_synthesis"],
            "coder": ["coding", "patch_generation", "local_tool_execution"],
            "reviewer": ["code_review", "static_analysis"],
            "commander": ["mission_control", "channel_operations", "session_orchestration"],
        }
        matches = sorted(domains.intersection(role_domain_map.get(role, [])))
        if matches:
            score += 20 + len(matches) * 3
            reasons.append(f"domain match for role {role}: {', '.join(matches)}")

    output_aliases = {
        "architecture_findings": "findings",
        "implementation_plan": "plan",
        "review_findings": "review",
    }
    expected_output = output_aliases.get(expected, expected)
    if expected_output in outputs:
        score += 12
        reasons.append(f"can produce {expected_output}")

    keyword_actions = {
        "inspect": "readFiles",
        "analyze": "performResearch",
        "research": "performResearch",
        "implement": "writeFiles",
        "patch": "producePatch",
        "review": "reviewCode",
        "apply": "writeFiles",
        "decide": "spawnSubagents",
    }
    for keyword, action in keyword_actions.items():
        if keyword in task_text and actions.get(action):
            score += 4
            reasons.append(f"task keyword {keyword!r} matches capability {action}")

    side_effects = set(capabilities.get("sideEffects") or [])
    if step.get("requiresApproval") and not side_effects:
        warnings.append("step requires approval but selected agent declares no side-effect surface")
    if side_effects:
        score -= min(len(side_effects), 8)
        warnings.append(f"side effects declared: {', '.join(sorted(side_effects))}")

    trust = safety.get("trustLevel")
    trust_penalty = {"low": 0, "medium": 1, "high": 3, "critical": 8}.get(str(trust), 2)
    score -= trust_penalty
    if trust:
        warnings.append(f"trust level: {trust}")

    return score, reasons, warnings


def policy_effect(policy: Resource | None, resource: str, action: str, role: str | None, agent_id: str | None) -> str:
    if not policy:
        return "unknown"
    default = (policy.get("defaults") or {}).get("effect", "deny")
    result = default
    for rule in policy.get("rules") or []:
        if rule.get("resource") != resource:
            continue
        if rule.get("action") and rule.get("action") != action:
            continue
        applies = rule.get("appliesTo") or {}
        roles = applies.get("roles")
        agents = applies.get("agents")
        if roles and role not in roles:
            continue
        if agents and agent_id not in agents:
            continue
        result = rule.get("effect", result)
    return result


def infer_side_effect_requests(step: Resource, role: str | None) -> list[tuple[str, str]]:
    text = " ".join(str(step.get(k, "")) for k in ("id", "task", "expectedOutput")).lower()
    requests: list[tuple[str, str]] = []
    is_executor_role = role in {"coder", "commander", "operator"}
    if is_executor_role and any(
        phrase in text
        for phrase in (
            "implement",
            "apply",
            "write file",
            "write files",
            "modify",
            "change file",
            "change files",
            "produce patch",
        )
    ):
        requests.append(("filesystem", "write"))
    if is_executor_role and any(
        phrase in text
        for phrase in (
            "execute shell",
            "run shell",
            "run command",
            "execute command",
            "run tests",
            "run test",
        )
    ):
        requests.append(("shell", "execute"))
    if role in {"commander", "operator"} and any(word in text for word in ("send", "notify", "message")):
        requests.append(("channel", "send"))
    return requests


def build_plan(index: dict[str, Any], legion_name: str, mission_name: str, policy_name: str | None) -> dict[str, Any]:
    legions = index["LegionPlan"]
    missions = index["MissionSpec"]
    policies = index["PolicySpec"]
    units = index["AgentUnit"]

    if legion_name not in legions:
        raise ValueError(f"LegionPlan {legion_name!r} not found")
    if mission_name not in missions:
        raise ValueError(f"MissionSpec {mission_name!r} not found")

    legion = legions[legion_name]
    mission = missions[mission_name]
    policy = policies.get(policy_name) if policy_name else None

    planned_steps = []
    for step in mission.get("workflow") or []:
        role = step.get("role")
        explicit_agent = step.get("agentId")
        candidate_ids = [explicit_agent] if explicit_agent else agents_for_role(legion, role)
        if not candidate_ids:
            candidate_ids = list(units)

        ranked = []
        for candidate_id in candidate_ids:
            unit = units.get(candidate_id)
            if not unit:
                ranked.append(
                    {
                        "agentId": candidate_id,
                        "score": -999,
                        "valid": False,
                        "reasons": [],
                        "warnings": [f"AgentUnit {candidate_id!r} not found"],
                    }
                )
                continue
            score, reasons, warnings = score_agent(unit, step, role)
            ranked.append(
                {
                    "agentId": candidate_id,
                    "runtime": (unit.get("runtime") or {}).get("class"),
                    "adapter": (unit.get("runtime") or {}).get("adapter"),
                    "score": score,
                    "valid": True,
                    "reasons": reasons,
                    "warnings": warnings,
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        selected = ranked[0] if ranked else None
        selected_id = selected["agentId"] if selected else None

        policy_checks = []
        for resource, action in infer_side_effect_requests(step, role):
            policy_checks.append(
                {
                    "resource": resource,
                    "action": action,
                    "effect": policy_effect(policy, resource, action, role, selected_id),
                }
            )

        planned_steps.append(
            {
                "id": step.get("id"),
                "role": role,
                "task": step.get("task"),
                "dependsOn": step.get("dependsOn", []),
                "expectedOutput": step.get("expectedOutput"),
                "requiresApproval": bool(step.get("requiresApproval")),
                "selectedAgent": selected,
                "candidates": ranked,
                "policyChecks": policy_checks,
                "status": "planned_read_only",
            }
        )

    return {
        "apiVersion": "agentlegion.dev/v0",
        "kind": "MissionPlan",
        "metadata": {
            "missionId": resource_id(mission),
            "legion": resource_id(legion),
            "policy": policy_name,
        },
        "goal": mission.get("goal"),
        "constraints": mission.get("constraints", {}),
        "steps": planned_steps,
        "notes": [
            "This is a read-only plan. No agent runtime was invoked.",
            "Policy checks are advisory until a RuntimeAdapter and PolicyGate enforce them.",
        ],
    }


def find_mission_step(mission: Resource, step_id: str) -> Resource | None:
    for step in mission.get("workflow") or []:
        if step.get("id") == step_id:
            return step
    return None


def compile_runtime_plan(
    mission_plan: Resource,
    index: dict[str, Any],
    mission_name: str,
    policy_name: str | None,
    dry_run: bool,
) -> Resource:
    mission = index["MissionSpec"].get(mission_name)
    policy = index["PolicySpec"].get(policy_name) if policy_name else None
    units = index["AgentUnit"]
    if not mission:
        raise ValueError(f"MissionSpec {mission_name!r} not found")

    runtime_plans = []
    for step in mission_plan.get("steps") or []:
        selected = step.get("selectedAgent") or {}
        agent_id = selected.get("agentId")
        unit = units.get(agent_id)
        runtime_class = selected.get("runtime")
        mission_step = find_mission_step(mission, str(step.get("id"))) or {}
        role = step.get("role")
        unit_labels = ((unit or {}).get("metadata") or {}).get("labels") or {}
        role_mismatch = bool(role and unit_labels.get("role") and unit_labels.get("role") != role)
        policy_checks = step.get("policyChecks") or []
        approval_points = [
            f"{check.get('resource')}.{check.get('action')}"
            for check in policy_checks
            if check.get("effect") == "ask"
        ]
        denied = [
            f"{check.get('resource')}.{check.get('action')}"
            for check in policy_checks
            if check.get("effect") == "deny"
        ]
        unsupported = []
        warnings = list(selected.get("warnings") or [])
        if role_mismatch:
            warnings.append(f"selected agent role {unit_labels.get('role')!r} does not match requested role {role!r}")
        if not unit:
            unsupported.append(f"AgentUnit {agent_id!r} not found")

        native_config: Resource
        command_preview: list[str]
        if runtime_class == "deepagents":
            extension = ((unit or {}).get("extensions") or {}).get("deepagents") or {}
            python = extension.get("python") or ".venv/bin/python"
            script = extension.get("script") or "scripts/deepagents_smoke.py"
            command_preview = [
                str(python),
                str(script),
                "--trajectory-id",
                f"dryrun-{step.get('id')}",
                "--session-id",
                f"dryrun-{step.get('id')}-session",
            ]
            native_config = {
                "mode": extension.get("mode") or "local_smoke",
                "python": python,
                "script": script,
                "createDeepAgent": {
                    "model": "agentlegion-tool-binding-fake" if dry_run else extension.get("model"),
                    "systemPrompt": mission_step.get("task"),
                    "tools": extension.get("tools", []),
                    "checkpointer": extension.get("checkpointer"),
                    "store": extension.get("store"),
                },
                "commandPreview": command_preview,
            }
        elif runtime_class == "hermes":
            command_preview = [
                "hermes",
                "chat",
                "-q",
                str(mission_step.get("task") or step.get("task") or ""),
            ]
            native_config = {
                "mode": "dry_run_command_preview",
                "commandPreview": command_preview,
                "nativeRef": ((unit or {}).get("runtime") or {}).get("nativeRef"),
                "enabledToolsets": (((unit or {}).get("extensions") or {}).get("hermes") or {}).get("enabledToolsets", []),
                "checkpoint": (((unit or {}).get("extensions") or {}).get("hermes") or {}).get("checkpoint", {}),
                "note": "Command preview only. AgentLegion does not invoke Hermes chat in dry-run mode.",
            }
        else:
            command_preview = []
            native_config = {
                "mode": "unsupported_runtime",
                "runtimeClass": runtime_class,
            }
            unsupported.append(f"runtime {runtime_class!r} has no compiler")

        phase = "blocked" if denied else "pending_approval" if approval_points else "ready_dry_run"
        runtime_plans.append(
            {
                "id": f"{mission_plan['metadata']['missionId']}.{step.get('id')}.{agent_id}",
                "runtimeClass": runtime_class,
                "agentUnitId": agent_id,
                "missionId": mission_plan["metadata"]["missionId"],
                "taskId": step.get("id"),
                "adapterVersion": "agentlegion.compiler/v0",
                "phase": phase,
                "dryRun": dry_run,
                "role": role,
                "dependsOn": step.get("dependsOn", []),
                "nativeConfig": native_config,
                "exposedTools": (((unit or {}).get("extensions") or {}).get(str(runtime_class)) or {}).get("tools", []),
                "permissionPlan": {
                    "policy": policy_name,
                    "checks": policy_checks,
                    "approvalRequired": approval_points,
                    "denied": denied,
                    "defaultEffect": ((policy or {}).get("defaults") or {}).get("effect"),
                },
                "sandboxPlan": {
                    "required": ((unit or {}).get("safety") or {}).get("sandboxRequired"),
                    "runtimeLocal": True,
                },
                "expectedArtifacts": [step.get("expectedOutput")] if step.get("expectedOutput") else [],
                "approvalPoints": approval_points,
                "warnings": warnings,
                "unsupported": unsupported,
            }
        )

    return {
        "apiVersion": "agentlegion.dev/v0",
        "kind": "CompiledRuntimePlan",
        "metadata": {
            "missionId": mission_plan["metadata"]["missionId"],
            "sourcePlanKind": mission_plan.get("kind"),
            "compiler": "agentlegion.compiler/v0",
            "dryRun": dry_run,
        },
        "runtimePlans": runtime_plans,
        "summary": {
            "total": len(runtime_plans),
            "ready": sum(1 for item in runtime_plans if item["phase"] == "ready_dry_run"),
            "pendingApproval": sum(1 for item in runtime_plans if item["phase"] == "pending_approval"),
            "blocked": sum(1 for item in runtime_plans if item["phase"] == "blocked"),
            "warnings": sum(len(item.get("warnings") or []) for item in runtime_plans),
        },
    }


def command_validate(args: argparse.Namespace) -> int:
    resources = load_resources([Path(p) for p in args.files])
    diagnostics = []
    for resource in resources:
        diagnostics.extend(validate_resource(resource))

    result = {
        "ok": not any(d.level == "error" for d in diagnostics),
        "resourceCount": len(resources),
        "diagnostics": [d.to_dict() for d in diagnostics],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


def command_plan(args: argparse.Namespace) -> int:
    paths = [Path(args.legion), Path(args.mission)]
    if args.policy:
        paths.append(Path(args.policy))
    resources = load_resources(paths)
    diagnostics = []
    for resource in resources:
        diagnostics.extend(validate_resource(resource))
    if any(d.level == "error" for d in diagnostics):
        print(
            json.dumps(
                {
                    "ok": False,
                    "diagnostics": [d.to_dict() for d in diagnostics],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1

    index = index_resources(resources)
    plan = build_plan(index, args.legion_name, args.mission_name, args.policy_name)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(str(out))
    else:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def command_compile_runtime_plan(args: argparse.Namespace) -> int:
    paths = [Path(args.legion), Path(args.mission)]
    if args.policy:
        paths.append(Path(args.policy))
    resources = load_resources(paths)
    diagnostics = []
    for resource in resources:
        diagnostics.extend(validate_resource(resource))
    if any(d.level == "error" for d in diagnostics):
        print(
            json.dumps(
                {
                    "ok": False,
                    "diagnostics": [d.to_dict() for d in diagnostics],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1

    index = index_resources(resources)
    mission_plan = build_plan(index, args.legion_name, args.mission_name, args.policy_name)
    compiled = compile_runtime_plan(
        mission_plan=mission_plan,
        index=index,
        mission_name=args.mission_name,
        policy_name=args.policy_name,
        dry_run=args.dry_run,
    )
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_json(out, compiled)
        print(str(out))
    else:
        print(json.dumps(compiled, indent=2, ensure_ascii=False))
    return 0


def write_json_if_missing(path: Path, data: Resource) -> bool:
    if path.exists():
        return False
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


class LocalTrajectoryStore:
    def __init__(self, root: Path):
        self.root = root

    def init(self) -> None:
        for item in STORE_DIRECTORIES:
            directory = self.root / item
            directory.mkdir(parents=True, exist_ok=True)
            (directory / ".gitkeep").touch(exist_ok=True)

    def write_raw_event(self, trajectory_id: str, event_index: int, event: Resource) -> Resource:
        path = self.root / "bronze/raw-events" / safe_id(trajectory_id) / f"{event_index:06d}-{safe_id(str(event.get('type', 'raw')))}.json"
        write_json(path, event)
        return content_ref(path, self.root)

    def write_fact(self, fact: Resource, preferred_id: str) -> Resource:
        kind = str(fact.get("kind") or "Unknown")
        directory = FACT_DIRECTORIES.get(kind)
        if not directory:
            raise ValueError(f"unsupported fact kind {kind!r}")
        path = self.root / directory / f"{safe_id(preferred_id)}.json"
        write_json(path, fact)
        return content_ref(path, self.root)

    def write_artifact_json(self, name: str, data: Any) -> Resource:
        path = self.root / "artifacts" / f"{safe_id(name)}.json"
        write_json(path, data)
        return content_ref(path, self.root)

    def read_fact_by_id(self, kind: str, fact_id: str) -> Resource:
        directory = FACT_DIRECTORIES.get(kind)
        if not directory:
            raise ValueError(f"unsupported fact kind {kind!r}")
        path = self.root / directory / f"{safe_id(fact_id)}.json"
        if not path.exists():
            raise FileNotFoundError(f"{kind} {fact_id!r} not found at {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected object")
        return data


class EventNormalizer:
    version = "agentlegion.event-normalizer/v0"

    def __init__(self, trajectory_id: str, session_id: str, agent_version: str, task_type: str):
        self.trajectory_id = trajectory_id
        self.session_id = session_id
        self.agent_version = agent_version
        self.task_type = task_type
        self.step_index = 0
        self.tool_steps: dict[str, str] = {}

    def run_fact(self, event: Resource, raw_ref: Resource) -> Resource:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        return {
            "apiVersion": "agentlegion.dev/v0",
            "kind": "TrajectoryRun",
            "trajectoryId": self.trajectory_id,
            "traceId": data.get("traceId") or event.get("traceId"),
            "sessionId": self.session_id,
            "missionId": event.get("missionId"),
            "taskId": event.get("taskId"),
            "agentUnitId": event.get("agentId"),
            "runtimeClass": data.get("runtimeClass") or event.get("runtimeClass") or "unknown",
            "agentVersion": data.get("agentVersion") or self.agent_version,
            "promptVersion": data.get("promptVersion"),
            "model": data.get("model"),
            "toolSchemaVersion": data.get("toolSchemaVersion"),
            "taskType": data.get("taskType") or self.task_type,
            "status": "running",
            "finalOutcome": "unknown",
            "normalizerVersion": self.version,
            "startedAt": event.get("timestamp") or now_iso(),
            "rawTraceRef": raw_ref,
            "metadata": {
                "sourceEventType": event.get("type"),
            },
        }

    def completion_run_patch(self, event: Resource) -> Resource:
        event_type = str(event.get("type") or "")
        status_map = {
            "completed": ("completed", "success"),
            "failed": ("failed", "failure"),
            "cancelled": ("cancelled", "partial"),
        }
        status, outcome = status_map.get(event_type, ("running", "unknown"))
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        patch: Resource = {
            "status": status,
            "finalOutcome": data.get("finalOutcome") or outcome,
            "endedAt": event.get("timestamp") or now_iso(),
        }
        if data.get("latencyMs") is not None:
            patch["latencyMs"] = data.get("latencyMs")
        if isinstance(data.get("cost"), dict):
            patch["cost"] = data.get("cost")
        return patch

    def step_fact(self, event: Resource, step_type: str, status: str, name: str | None, raw_ref: Resource) -> Resource:
        self.step_index += 1
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        step_id = str(data.get("stepId") or f"{self.trajectory_id}-step-{self.step_index:04d}")
        return {
            "apiVersion": "agentlegion.dev/v0",
            "kind": "TrajectoryStep",
            "stepId": step_id,
            "trajectoryId": self.trajectory_id,
            "parentStepId": data.get("parentStepId"),
            "stepIndex": self.step_index,
            "turnIndex": data.get("turnIndex"),
            "stepType": step_type,
            "name": name,
            "status": status,
            "inputRef": raw_ref,
            "outputRef": raw_ref,
            "startedAt": event.get("timestamp"),
            "endedAt": event.get("timestamp") if status in {"completed", "failed"} else None,
            "latencyMs": data.get("latencyMs"),
            "errorType": data.get("errorType"),
        }

    def message_fact(self, event: Resource, step: Resource, raw_ref: Resource) -> Resource:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        return {
            "apiVersion": "agentlegion.dev/v0",
            "kind": "MessageEvent",
            "messageId": str(data.get("messageId") or sha256_json(event)[:16]),
            "stepId": step["stepId"],
            "trajectoryId": self.trajectory_id,
            "role": data.get("role") or "assistant",
            "contentRef": raw_ref,
            "contentType": data.get("contentType") or "text",
            "tokenCount": data.get("tokenCount"),
            "toolCallId": data.get("toolCallId"),
            "timestamp": event.get("timestamp") or now_iso(),
        }

    def tool_call_fact(self, event: Resource, step: Resource) -> Resource:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        args = data.get("args") if "args" in data else data.get("arguments", {})
        tool_call_id = str(data.get("toolCallId") or data.get("id") or sha256_json(event)[:16])
        self.tool_steps[tool_call_id] = str(step["stepId"])
        return {
            "apiVersion": "agentlegion.dev/v0",
            "kind": "ToolCallFact",
            "toolCallId": tool_call_id,
            "stepId": step["stepId"],
            "trajectoryId": self.trajectory_id,
            "toolName": data.get("toolName") or data.get("name") or "unknown",
            "namespace": data.get("namespace") or "default",
            "args": args,
            "argsHash": sha256_json(args),
            "validationResult": data.get("validationResult") or {"ok": True, "diagnostics": []},
            "resultSummary": data.get("resultSummary"),
            "isError": bool(data.get("isError", False)),
            "errorType": data.get("errorType"),
            "latencyMs": data.get("latencyMs"),
            "retryIndex": int(data.get("retryIndex") or 0),
            "sideEffectType": data.get("sideEffectType") or "read_only",
            "approvalStatus": data.get("approvalStatus") or "not_required",
            "sourceStepId": data.get("sourceStepId"),
        }

    def tool_result_patch(self, event: Resource) -> tuple[str | None, Resource]:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        tool_call_id = data.get("toolCallId") or data.get("id")
        step_id = self.tool_steps.get(str(tool_call_id)) if tool_call_id is not None else None
        return step_id, {
            "result": data.get("result"),
            "resultSummary": data.get("resultSummary"),
            "isError": bool(data.get("isError", False)),
            "errorType": data.get("errorType"),
            "latencyMs": data.get("latencyMs"),
        }

    def artifact_fact(self, event: Resource, step: Resource, raw_ref: Resource) -> Resource:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        artifact_id = str(data.get("artifactId") or data.get("id") or sha256_json(event)[:16])
        return {
            "apiVersion": "agentlegion.dev/v0",
            "kind": "ArtifactFact",
            "artifactId": artifact_id,
            "stepId": step["stepId"],
            "trajectoryId": self.trajectory_id,
            "artifactType": data.get("artifactType") or data.get("type") or "artifact",
            "uri": data.get("uri") or raw_ref["uri"],
            "metadataRef": raw_ref,
            "qualityStatus": data.get("qualityStatus") or "unchecked",
        }


def command_init_store(args: argparse.Namespace) -> int:
    root = Path(args.root)
    created: list[str] = []
    existing: list[str] = []
    for item in STORE_DIRECTORIES:
        directory = root / item
        existed = directory.exists()
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ".gitkeep").touch(exist_ok=True)
        (existing if existed else created).append(str(directory))

    manifest = {
        "apiVersion": "agentlegion.dev/v0",
        "kind": "LocalStoreManifest",
        "root": str(root),
        "layoutVersion": "bronze-silver-gold/v0",
        "layers": {
            "bronze": "raw runtime traces, events, tool returns, and scores kept as evidence",
            "silver": "normalized trajectory facts for analysis and attribution",
            "gold": "regression cases, replay snapshots, eval reports, and release gates",
        },
        "directories": STORE_DIRECTORIES,
    }
    manifest_created = write_json_if_missing(root / "store-manifest.json", manifest)

    result = {
        "ok": True,
        "root": str(root),
        "layoutVersion": manifest["layoutVersion"],
        "created": created,
        "existing": existing,
        "manifest": "created" if manifest_created else "existing",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def command_inspect_store(args: argparse.Namespace) -> int:
    root = Path(args.root)
    directories = []
    missing = []
    for item in STORE_DIRECTORIES:
        directory = root / item
        if not directory.is_dir():
            missing.append(item)
            continue
        file_count = sum(1 for child in directory.rglob("*") if child.is_file() and child.name != ".gitkeep")
        directories.append({"path": item, "fileCount": file_count})

    result = {
        "ok": not missing,
        "root": str(root),
        "layoutVersion": "bronze-silver-gold/v0",
        "directories": directories,
        "missing": missing,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


def command_ingest_events(args: argparse.Namespace) -> int:
    root = Path(args.root)
    store = LocalTrajectoryStore(root)
    store.init()
    events = read_json_or_jsonl(Path(args.events))
    normalizer = EventNormalizer(
        trajectory_id=args.trajectory_id,
        session_id=args.session_id,
        agent_version=args.agent_version,
        task_type=args.task_type,
    )

    written: list[Resource] = []
    run_fact: Resource | None = None
    tool_fact_paths_by_step: dict[str, Path] = {}

    for event_index, event in enumerate(events, start=1):
        raw_ref = store.write_raw_event(args.trajectory_id, event_index, event)
        event_type = str(event.get("type") or "raw")

        if event_type == "started":
            run_fact = normalizer.run_fact(event, raw_ref)
            ref = store.write_fact(run_fact, args.trajectory_id)
            written.append({"kind": "TrajectoryRun", "ref": ref})
            continue

        if event_type in {"completed", "failed", "cancelled"}:
            if run_fact is None:
                run_fact = normalizer.run_fact(event, raw_ref)
            run_fact.update(normalizer.completion_run_patch(event))
            ref = store.write_fact(run_fact, args.trajectory_id)
            written.append({"kind": "TrajectoryRun", "ref": ref})

            step = normalizer.step_fact(event, event_type, event_type if event_type != "completed" else "completed", event_type, raw_ref)
            step_ref = store.write_fact(step, str(step["stepId"]))
            written.append({"kind": "TrajectoryStep", "ref": step_ref})
            continue

        if event_type == "message":
            step = normalizer.step_fact(event, "message", "completed", "message", raw_ref)
            step_ref = store.write_fact(step, str(step["stepId"]))
            message = normalizer.message_fact(event, step, raw_ref)
            message_ref = store.write_fact(message, str(message["messageId"]))
            written.extend([{"kind": "TrajectoryStep", "ref": step_ref}, {"kind": "MessageEvent", "ref": message_ref}])
            continue

        if event_type == "tool_call":
            step = normalizer.step_fact(event, "tool_call", "started", "tool_call", raw_ref)
            step_ref = store.write_fact(step, str(step["stepId"]))
            tool_fact = normalizer.tool_call_fact(event, step)
            tool_ref = store.write_fact(tool_fact, str(tool_fact["toolCallId"]))
            tool_fact_paths_by_step[str(step["stepId"])] = root / tool_ref["uri"]
            written.extend([{"kind": "TrajectoryStep", "ref": step_ref}, {"kind": "ToolCallFact", "ref": tool_ref}])
            continue

        if event_type == "tool_result":
            step_id, patch = normalizer.tool_result_patch(event)
            if step_id and step_id in tool_fact_paths_by_step:
                tool_path = tool_fact_paths_by_step[step_id]
                tool_fact = json.loads(tool_path.read_text(encoding="utf-8"))
                tool_fact.update({k: v for k, v in patch.items() if v is not None})
                tool_ref = store.write_fact(tool_fact, str(tool_fact["toolCallId"]))
                written.append({"kind": "ToolCallFact", "ref": tool_ref})
            step = normalizer.step_fact(event, "tool_call", "completed" if not patch.get("isError") else "failed", "tool_result", raw_ref)
            step_ref = store.write_fact(step, str(step["stepId"]))
            written.append({"kind": "TrajectoryStep", "ref": step_ref})
            continue

        if event_type == "artifact":
            step = normalizer.step_fact(event, "artifact", "completed", "artifact", raw_ref)
            step_ref = store.write_fact(step, str(step["stepId"]))
            artifact = normalizer.artifact_fact(event, step, raw_ref)
            artifact_ref = store.write_fact(artifact, str(artifact["artifactId"]))
            written.extend([{"kind": "TrajectoryStep", "ref": step_ref}, {"kind": "ArtifactFact", "ref": artifact_ref}])
            continue

        step = normalizer.step_fact(event, "workflow", "completed", event_type, raw_ref)
        step_ref = store.write_fact(step, str(step["stepId"]))
        written.append({"kind": "TrajectoryStep", "ref": step_ref})

    result = {
        "ok": True,
        "root": str(root),
        "trajectoryId": args.trajectory_id,
        "eventCount": len(events),
        "writtenCount": len(written),
        "written": written,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def command_write_fixture_events(args: argparse.Namespace) -> int:
    out = Path(args.output)
    timestamp = now_iso()
    events = [
        {
            "type": "started",
            "agentId": "fixture-agent",
            "missionId": "fixture-mission",
            "taskId": "fixture-task",
            "timestamp": timestamp,
            "data": {
                "runtimeClass": "fixture-runtime",
                "agentVersion": "fixture-agent/v0",
                "model": "fixture-model",
                "toolSchemaVersion": "fixture-tools/v0",
                "taskType": "fixture",
            },
        },
        {
            "type": "message",
            "agentId": "fixture-agent",
            "missionId": "fixture-mission",
            "taskId": "fixture-task",
            "timestamp": timestamp,
            "data": {
                "messageId": "msg-001",
                "role": "assistant",
                "contentType": "text",
                "content": "I will inspect the requested files.",
                "tokenCount": 8,
            },
        },
        {
            "type": "tool_call",
            "agentId": "fixture-agent",
            "missionId": "fixture-mission",
            "taskId": "fixture-task",
            "timestamp": timestamp,
            "data": {
                "toolCallId": "tool-001",
                "toolName": "read_file",
                "namespace": "filesystem",
                "args": {"path": "README.md"},
                "sideEffectType": "read_only",
                "approvalStatus": "not_required",
            },
        },
        {
            "type": "tool_result",
            "agentId": "fixture-agent",
            "missionId": "fixture-mission",
            "taskId": "fixture-task",
            "timestamp": timestamp,
            "data": {
                "toolCallId": "tool-001",
                "resultSummary": "README.md read successfully",
                "isError": False,
                "latencyMs": 12,
            },
        },
        {
            "type": "artifact",
            "agentId": "fixture-agent",
            "missionId": "fixture-mission",
            "taskId": "fixture-task",
            "timestamp": timestamp,
            "data": {
                "artifactId": "artifact-001",
                "artifactType": "finding",
                "uri": "artifacts/fixture-finding.json",
                "qualityStatus": "unchecked",
            },
        },
        {
            "type": "completed",
            "agentId": "fixture-agent",
            "missionId": "fixture-mission",
            "taskId": "fixture-task",
            "timestamp": timestamp,
            "data": {
                "finalOutcome": "success",
                "latencyMs": 120,
                "cost": {"totalUsd": 0, "inputTokens": 10, "outputTokens": 20},
            },
        },
    ]
    write_json(out, events)
    print(str(out))
    return 0


def command_record_score(args: argparse.Namespace) -> int:
    store = LocalTrajectoryStore(Path(args.root))
    store.init()
    score_id = args.score_id or f"score-{sha256_json([args.target_type, args.target_id, args.score_name, now_iso()])[:12]}"
    rationale_ref = None
    if args.rationale:
        rationale_ref = store.write_artifact_json(
            f"score-rationale-{score_id}",
            {
                "scoreId": score_id,
                "rationale": args.rationale,
                "createdAt": now_iso(),
            },
        )

    score: Resource = {
        "apiVersion": "agentlegion.dev/v0",
        "kind": "ScoreFact",
        "scoreId": score_id,
        "trajectoryId": args.trajectory_id,
        "targetType": args.target_type,
        "targetId": args.target_id,
        "scoreName": args.score_name,
        "scoreType": args.score_type,
        "scoreValue": parse_scalar(args.score_value),
        "evaluatorType": args.evaluator_type,
        "evaluatorVersion": args.evaluator_version,
        "rationaleRef": rationale_ref,
        "createdAt": now_iso(),
    }
    ref = store.write_fact(score, score_id)
    result = {"ok": True, "scoreId": score_id, "ref": ref}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def command_promote_regression_case(args: argparse.Namespace) -> int:
    store = LocalTrajectoryStore(Path(args.root))
    store.init()
    if args.root_cause_category not in ROOT_CAUSE_CATEGORIES:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"root cause category must be one of: {', '.join(ROOT_CAUSE_CATEGORIES)}",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1

    trajectory = store.read_fact_by_id("TrajectoryRun", args.trajectory_id)
    case_id = args.case_id or f"regression-{args.trajectory_id}-{safe_id(args.root_cause_category).lower()}"
    replay_input_ref = store.write_artifact_json(
        f"replay-input-{case_id}",
        {
            "sourceTrajectoryId": args.trajectory_id,
            "userInput": args.replay_input,
            "createdAt": now_iso(),
        },
    )
    expected_behavior_ref = store.write_artifact_json(
        f"expected-behavior-{case_id}",
        {
            "sourceTrajectoryId": args.trajectory_id,
            "expectedBehavior": args.expected_behavior,
            "createdAt": now_iso(),
        },
    )
    snapshot_id = f"snapshot-{case_id}"
    replay_snapshot: Resource = {
        "apiVersion": "agentlegion.dev/v0",
        "kind": "ReplaySnapshot",
        "snapshotId": snapshot_id,
        "regressionCaseId": case_id,
        "trajectoryId": args.trajectory_id,
        "userInputRef": replay_input_ref,
        "initialStateRef": None,
        "memorySnapshotRef": None,
        "toolSpaceSnapshotRef": None,
        "toolSchemaSnapshotRef": trajectory.get("rawTraceRef"),
        "retrievalCorpusVersion": args.retrieval_corpus_version,
        "permissionContextRef": None,
        "externalApiFixtureRef": None,
        "clock": {
            "instant": trajectory.get("startedAt") or now_iso(),
            "timezone": args.timezone,
        },
        "featureFlags": {},
        "modelConfigRef": None,
        "promptVersion": trajectory.get("promptVersion"),
        "expectedBehaviorRef": expected_behavior_ref,
    }
    snapshot_ref = store.write_fact(replay_snapshot, snapshot_id)

    regression_case: Resource = {
        "apiVersion": "agentlegion.dev/v0",
        "kind": "RegressionCase",
        "caseId": case_id,
        "sourceTrajectoryId": args.trajectory_id,
        "rootCauseCategory": args.root_cause_category,
        "rootCauseDetail": args.root_cause_detail,
        "failedStepId": args.failed_step_id,
        "severity": args.severity,
        "fixOwner": args.fix_owner,
        "regressionPriority": args.regression_priority,
        "replayInputRef": replay_input_ref,
        "expectedBehaviorRef": expected_behavior_ref,
        "replaySnapshotRef": snapshot_ref,
        "createdFromFailureAt": trajectory.get("endedAt") or now_iso(),
        "status": "active",
    }
    case_ref = store.write_fact(regression_case, case_id)
    result = {
        "ok": True,
        "caseId": case_id,
        "regressionCaseRef": case_ref,
        "replaySnapshotRef": snapshot_ref,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def command_mvp_smoke(args: argparse.Namespace) -> int:
    root = Path(args.root)
    store = LocalTrajectoryStore(root)
    store.init()

    checks: list[Resource] = []

    hermes_path = shutil.which("hermes")
    if hermes_path:
        hermes = subprocess.run(
            [hermes_path, "--help"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            timeout=args.timeout_seconds,
            check=False,
        )
        checks.append(
            {
                "runtime": "hermes",
                "ok": hermes.returncode == 0 and "Hermes Agent" in hermes.stdout,
                "command": f"{hermes_path} --help",
                "returnCode": hermes.returncode,
                "stdoutFirstLine": hermes.stdout.splitlines()[0] if hermes.stdout else "",
                "stderrFirstLine": hermes.stderr.splitlines()[0] if hermes.stderr else "",
            }
        )
    else:
        checks.append({"runtime": "hermes", "ok": False, "error": "hermes command not found"})

    python_path = Path(args.python)
    deepagents_events = root / "fixtures" / "mvp-deepagents-smoke.events.json"
    deepagents_cmd = [
        str(python_path),
        "scripts/deepagents_smoke.py",
        "--events-out",
        str(deepagents_events),
        "--trajectory-id",
        args.deepagents_trajectory_id,
        "--session-id",
        args.deepagents_session_id,
    ]
    deepagents = subprocess.run(
        deepagents_cmd,
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        timeout=args.timeout_seconds,
        check=False,
    )
    deepagents_ok = False
    deepagents_payload: Resource | None = None
    try:
        deepagents_payload = json.loads(deepagents.stdout)
        deepagents_ok = bool(deepagents_payload.get("ok")) and deepagents.returncode == 0
    except json.JSONDecodeError:
        deepagents_ok = False

    checks.append(
        {
            "runtime": "deepagents",
            "ok": deepagents_ok,
            "command": " ".join(deepagents_cmd),
            "returnCode": deepagents.returncode,
            "result": deepagents_payload,
            "stderrFirstLine": deepagents.stderr.splitlines()[0] if deepagents.stderr else "",
        }
    )

    ingest_result: Resource | None = None
    if deepagents_ok and deepagents_events.exists():
        ingest_args = argparse.Namespace(
            root=str(root),
            events=str(deepagents_events),
            trajectory_id=args.deepagents_trajectory_id,
            session_id=args.deepagents_session_id,
            agent_version=(deepagents_payload or {}).get("versions", {}).get("deepagents", "unknown"),
            task_type="mvp_smoke",
        )
        # Capture the write summary without hiding failures from the final report.
        events = read_json_or_jsonl(deepagents_events)
        ingest_stdout = io.StringIO()
        with redirect_stdout(ingest_stdout):
            command_ingest_events(ingest_args)
        try:
            ingest_written = json.loads(ingest_stdout.getvalue())
        except json.JSONDecodeError:
            ingest_written = {"raw": ingest_stdout.getvalue()}
        ingest_result = {
            "events": str(deepagents_events),
            "eventCount": len(events),
            "trajectoryId": args.deepagents_trajectory_id,
            "written": ingest_written,
        }

    ok = all(bool(check.get("ok")) for check in checks)
    result = {
        "ok": ok,
        "checks": checks,
        "ingest": ingest_result,
        "notes": [
            "Hermes smoke checks CLI health only; it does not invoke a live Hermes task.",
            "DeepAgents smoke constructs and invokes a local graph with a fake tool-binding model.",
        ],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentlegion", description="Read-only AgentLegion planner CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate AgentLegion YAML resources")
    validate.add_argument("files", nargs="+", help="YAML files or directories")
    validate.set_defaults(func=command_validate)

    plan = sub.add_parser("plan", help="Create a read-only mission plan")
    plan.add_argument("--legion", required=True, help="LegionPlan YAML, optionally containing AgentUnit documents")
    plan.add_argument("--mission", required=True, help="MissionSpec YAML")
    plan.add_argument("--policy", help="PolicySpec YAML")
    plan.add_argument("--legion-name", default="software-engineering-legion", help="LegionPlan metadata.name")
    plan.add_argument("--mission-name", default="refactor-auth-module", help="MissionSpec metadata.id/name")
    plan.add_argument("--policy-name", default="default-deny-side-effects", help="PolicySpec metadata.name")
    plan.add_argument("--output", "-o", help="Write mission plan JSON to file")
    plan.set_defaults(func=command_plan)

    compile_plan = sub.add_parser("compile-runtime-plan", help="Compile a MissionPlan into runtime-specific dry-run plans")
    compile_plan.add_argument("--legion", required=True, help="LegionPlan YAML, optionally containing AgentUnit documents")
    compile_plan.add_argument("--mission", required=True, help="MissionSpec YAML")
    compile_plan.add_argument("--policy", help="PolicySpec YAML")
    compile_plan.add_argument("--legion-name", default="software-engineering-legion", help="LegionPlan metadata.name")
    compile_plan.add_argument("--mission-name", default="refactor-auth-module", help="MissionSpec metadata.id/name")
    compile_plan.add_argument("--policy-name", default="default-deny-side-effects", help="PolicySpec metadata.name")
    compile_plan.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True, help="Compile without executing native runtimes")
    compile_plan.add_argument("--output", "-o", help="Write compiled runtime plan JSON to file")
    compile_plan.set_defaults(func=command_compile_runtime_plan)

    init_store = sub.add_parser("init-store", help="Create local Bronze/Silver/Gold AgentLegion store directories")
    init_store.add_argument("--root", default=".agentlegion", help="Local store root")
    init_store.set_defaults(func=command_init_store)

    inspect_store = sub.add_parser("inspect-store", help="Inspect local AgentLegion store layout")
    inspect_store.add_argument("--root", default=".agentlegion", help="Local store root")
    inspect_store.set_defaults(func=command_inspect_store)

    ingest = sub.add_parser("ingest-events", help="Ingest AgentEvent JSON/JSONL into Bronze and normalized Silver facts")
    ingest.add_argument("events", help="JSON array or JSONL file containing AgentEvent-like objects")
    ingest.add_argument("--root", default=".agentlegion", help="Local store root")
    ingest.add_argument("--trajectory-id", required=True, help="Trajectory id to assign")
    ingest.add_argument("--session-id", required=True, help="Session id for the trajectory")
    ingest.add_argument("--agent-version", default="unknown", help="Agent version for TrajectoryRun")
    ingest.add_argument("--task-type", default="unknown", help="Task type for TrajectoryRun")
    ingest.set_defaults(func=command_ingest_events)

    fixture = sub.add_parser("write-fixture-events", help="Write a small AgentEvent fixture for local normalizer tests")
    fixture.add_argument("--output", default=".agentlegion/fixtures/agent-events.fixture.json", help="Fixture JSON path")
    fixture.set_defaults(func=command_write_fixture_events)

    score = sub.add_parser("record-score", help="Write a ScoreFact for a trajectory, step, tool call, artifact, or regression case")
    score.add_argument("--root", default=".agentlegion", help="Local store root")
    score.add_argument("--score-id", help="Score id; defaults to a generated id")
    score.add_argument("--trajectory-id", help="Trajectory id associated with this score")
    score.add_argument("--target-type", required=True, help="trajectory_run, trajectory_step, tool_call, artifact, regression_case, or custom")
    score.add_argument("--target-id", required=True, help="Target id being scored")
    score.add_argument("--score-name", required=True, help="Metric or rubric name")
    score.add_argument("--score-type", required=True, choices=["binary", "numeric", "categorical", "rubric", "human_feedback"], help="Score type")
    score.add_argument("--score-value", required=True, help="Score value; parsed as bool/int/float/string")
    score.add_argument("--evaluator-type", required=True, choices=["human", "llm", "rule", "unit_test", "integration_test"], help="Evaluator source")
    score.add_argument("--evaluator-version", help="Evaluator version")
    score.add_argument("--rationale", help="Human or evaluator rationale stored as an artifact")
    score.set_defaults(func=command_record_score)

    promote = sub.add_parser("promote-regression-case", help="Promote a failed trajectory into a RegressionCase and ReplaySnapshot")
    promote.add_argument("--root", default=".agentlegion", help="Local store root")
    promote.add_argument("--case-id", help="Regression case id; defaults from trajectory and root cause")
    promote.add_argument("--trajectory-id", required=True, help="Source TrajectoryRun id")
    promote.add_argument("--root-cause-category", required=True, choices=ROOT_CAUSE_CATEGORIES, help="Root-cause taxonomy label")
    promote.add_argument("--root-cause-detail", help="Short root-cause detail")
    promote.add_argument("--failed-step-id", help="Failed or most relevant step id")
    promote.add_argument("--severity", required=True, choices=["low", "medium", "high", "critical"], help="Failure severity")
    promote.add_argument("--fix-owner", help="Owner responsible for fixing this class of failure")
    promote.add_argument("--regression-priority", required=True, choices=["P0", "P1", "P2"], help="Regression priority")
    promote.add_argument("--replay-input", required=True, help="Replay input or pointer text")
    promote.add_argument("--expected-behavior", required=True, help="Expected behavior or assertion text")
    promote.add_argument("--retrieval-corpus-version", help="Retrieval corpus version if relevant")
    promote.add_argument("--timezone", default="UTC", help="Replay clock timezone")
    promote.set_defaults(func=command_promote_regression_case)

    mvp_smoke = sub.add_parser("mvp-smoke", help="Run local MVP smoke checks for Hermes and DeepAgents")
    mvp_smoke.add_argument("--root", default=".agentlegion", help="Local store root")
    mvp_smoke.add_argument("--python", default=".venv/bin/python", help="Python executable with DeepAgents installed")
    mvp_smoke.add_argument("--timeout-seconds", type=int, default=60, help="Per-runtime smoke timeout")
    mvp_smoke.add_argument("--deepagents-trajectory-id", default="mvp-deepagents-smoke", help="Trajectory id for DeepAgents smoke")
    mvp_smoke.add_argument("--deepagents-session-id", default="mvp-deepagents-session", help="Session id for DeepAgents smoke")
    mvp_smoke.set_defaults(func=command_mvp_smoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
