"""RepoPilot trace and eval tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from openharness.runlog.evals import run_eval_suite
from openharness.runlog.trace import export_run_markdown, list_runs, load_run_events
from openharness.api.client import ApiMessageCompleteEvent, ApiTextDeltaEvent
from openharness.api.usage import UsageSnapshot
from openharness.config.settings import PermissionSettings
from openharness.engine.messages import ConversationMessage, TextBlock, ToolUseBlock
from openharness.engine.query_engine import QueryEngine
from openharness.permissions import PermissionChecker, PermissionMode
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolRegistry, ToolResult


class _FakeResponse:
    def __init__(self, message: ConversationMessage, usage: UsageSnapshot | None = None) -> None:
        self.message = message
        self.usage = usage or UsageSnapshot(input_tokens=1, output_tokens=1)


class _FakeApiClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)

    async def stream_message(self, request):
        del request
        response = self._responses.pop(0)
        for block in response.message.content:
            if isinstance(block, TextBlock) and block.text:
                yield ApiTextDeltaEvent(text=block.text)
        yield ApiMessageCompleteEvent(
            message=response.message,
            usage=response.usage,
            stop_reason=None,
        )


class _EchoInput(BaseModel):
    text: str


class _EchoTool(BaseTool):
    name = "echo_write"
    description = "Echoes text with a mutating-tool classification."
    input_model = _EchoInput

    async def execute(self, arguments: _EchoInput, context: ToolExecutionContext) -> ToolResult:
        del context
        return ToolResult(output=f"echo:{arguments.text}")


def test_local_eval_writes_scorecard_and_trace_runs(tmp_path: Path) -> None:
    scorecard = run_eval_suite(tmp_path, suite="local")

    assert scorecard["suite"] == "local"
    assert scorecard["total_cases"] == 8
    assert scorecard["permission_decisions"] >= 8
    assert scorecard["tool_calls"] >= 8
    assert (tmp_path / ".repopilot" / "evals" / "local-scorecard.json").exists()
    assert len(list_runs(tmp_path, limit=20)) >= 8


@pytest.mark.asyncio
async def test_query_engine_persists_tool_permission_trace(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(_EchoTool())
    engine = QueryEngine(
        api_client=_FakeApiClient(
            [
                _FakeResponse(
                    ConversationMessage(
                        role="assistant",
                        content=[
                            TextBlock(text="I will call a tool."),
                            ToolUseBlock(
                                id="toolu_echo",
                                name="echo_write",
                                input={"text": "hello"},
                            ),
                        ],
                    ),
                    UsageSnapshot(input_tokens=5, output_tokens=3),
                ),
                _FakeResponse(
                    ConversationMessage(
                        role="assistant",
                        content=[TextBlock(text="done")],
                    ),
                    UsageSnapshot(input_tokens=4, output_tokens=2),
                ),
            ]
        ),
        tool_registry=registry,
        permission_checker=PermissionChecker(PermissionSettings(mode=PermissionMode.FULL_AUTO)),
        cwd=tmp_path,
        model="deterministic-test",
        system_prompt="system",
    )

    events = [event async for event in engine.submit_message("use the echo tool")]
    runs = list_runs(tmp_path, limit=5)

    assert events
    assert len(runs) == 1
    trace_events = load_run_events(tmp_path, runs[0]["run_id"])
    kinds = [event["kind"] for event in trace_events]
    permission = next(event for event in trace_events if event["kind"] == "permission_decision")
    completed = next(event for event in trace_events if event["kind"] == "tool_completed")
    runtime = next(event for event in trace_events if event["kind"] == "tool_runtime")

    assert "assistant_turn" in kinds
    assert "tool_started" in kinds
    assert permission["payload"]["allowed"] is True
    assert permission["payload"]["risk"] == "filesystem-write"
    assert completed["payload"]["metadata"] == {}
    assert runtime["payload"]["duration_ms"] >= 0


def test_trace_markdown_export(tmp_path: Path) -> None:
    run_eval_suite(tmp_path, suite="swebench-smoke")
    run_id = list_runs(tmp_path, limit=1)[0]["run_id"]

    output = export_run_markdown(tmp_path, run_id)

    text = output.read_text(encoding="utf-8")
    assert "RepoPilot Run" in text
    assert "Scorecard" in text
