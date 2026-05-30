#!/usr/bin/env python3
"""Local DeepAgents smoke runner for AgentLegion MVP tests.

This script intentionally uses a fake tool-binding chat model so it can verify
that the local DeepAgents SDK constructs and invokes a graph without calling a
remote LLM provider.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ToolBindingFakeChatModel(BaseChatModel):
    """Fake chat model that satisfies DeepAgents' tool-binding requirement."""

    messages: Iterator[AIMessage | str] = Field(exclude=True)
    tools: Sequence[dict[str, Any] | type | Callable | BaseTool] = ()
    call_count: int = 0

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        self.tools = tools
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.call_count += 1
        message = next(self.messages)
        ai_message = AIMessage(content=message) if isinstance(message, str) else message
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    @property
    def _llm_type(self) -> str:
        return "agentlegion-tool-binding-fake"


def run_smoke() -> dict[str, Any]:
    model = ToolBindingFakeChatModel(messages=iter([AIMessage(content="deepagents smoke ok")]))
    agent = create_deep_agent(
        model=model,
        system_prompt="AgentLegion MVP smoke test. Return the scripted response.",
        name="agentlegion-deepagents-smoke",
    )
    result = agent.invoke({"messages": [HumanMessage(content="Run AgentLegion DeepAgents smoke test.")]})
    final = result["messages"][-1].content
    versions = ((agent.config or {}).get("metadata") or {}).get("versions") or {}
    return {
        "ok": final == "deepagents smoke ok",
        "final": final,
        "modelCallCount": model.call_count,
        "boundToolCount": len(model.tools),
        "versions": versions,
    }


def build_events(result: dict[str, Any], trajectory_id: str, session_id: str) -> list[dict[str, Any]]:
    timestamp = now_iso()
    return [
        {
            "type": "started",
            "agentId": "deepagents-researcher",
            "missionId": "mvp-local-smoke",
            "taskId": "deepagents-smoke",
            "timestamp": timestamp,
            "data": {
                "runtimeClass": "deepagents",
                "agentVersion": f"deepagents/{result.get('versions', {}).get('deepagents', 'unknown')}",
                "model": "agentlegion-tool-binding-fake",
                "taskType": "mvp_smoke",
                "traceId": trajectory_id,
                "sessionId": session_id,
            },
        },
        {
            "type": "message",
            "agentId": "deepagents-researcher",
            "missionId": "mvp-local-smoke",
            "taskId": "deepagents-smoke",
            "timestamp": timestamp,
            "data": {
                "messageId": f"{trajectory_id}-message-final",
                "role": "assistant",
                "contentType": "text",
                "content": result["final"],
            },
        },
        {
            "type": "completed" if result["ok"] else "failed",
            "agentId": "deepagents-researcher",
            "missionId": "mvp-local-smoke",
            "taskId": "deepagents-smoke",
            "timestamp": timestamp,
            "data": {
                "finalOutcome": "success" if result["ok"] else "failure",
                "latencyMs": None,
                "cost": {"totalUsd": 0, "inputTokens": 0, "outputTokens": 0},
            },
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local DeepAgents smoke test")
    parser.add_argument("--events-out", help="Write AgentEvent JSON array to this path")
    parser.add_argument("--trajectory-id", default="mvp-deepagents-smoke")
    parser.add_argument("--session-id", default="mvp-deepagents-session")
    args = parser.parse_args()

    result = run_smoke()
    if args.events_out:
        out = Path(args.events_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(build_events(result, args.trajectory_id, args.session_id), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
