"""Deterministic AgentOps eval suites.

The local suite validates trace, audit, and scorecard behavior without calling
an LLM.  SWE-bench smoke mode records benchmark metadata so the project can
show public-benchmark compatibility without requiring a heavyweight Docker run
for every demo.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from openharness.agentops.trace import TraceRecorder, summarize_run
from openharness.api.usage import UsageSnapshot
from openharness.engine.messages import ConversationMessage, TextBlock, ToolUseBlock
from openharness.engine.stream_events import (
    AssistantTurnComplete,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)


SuiteName = Literal["local", "swebench-smoke"]


@dataclass(frozen=True)
class EvalCase:
    id: str
    prompt: str
    tool_name: str
    risk: str
    should_error: bool = False
    should_block_permission: bool = False


LOCAL_EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase("read-code", "Inspect the project entrypoint and summarize it.", "read_file", "read-only"),
    EvalCase("grep-risk", "Search for unsafe shell usage.", "grep", "read-only"),
    EvalCase("write-patch", "Apply a small deterministic source change.", "file_edit", "filesystem-write"),
    EvalCase("run-tests", "Run a focused unit test.", "bash", "shell-command"),
    EvalCase("blocked-secret", "Attempt to read an SSH private key path.", "read_file", "credential-risk", should_block_permission=True),
    EvalCase("tool-error", "Call a missing tool and preserve the error.", "missing_tool", "mutating-tool", should_error=True),
    EvalCase("network-check", "Fetch public benchmark metadata.", "web_fetch", "network"),
    EvalCase("compact-aware", "Keep trace continuity through context compact.", "compact", "read-only"),
)


def run_eval_suite(cwd: str | Path, suite: SuiteName = "local") -> dict[str, Any]:
    """Run a deterministic eval suite and return a scorecard."""
    if suite == "swebench-smoke":
        return run_swebench_smoke(cwd)
    return run_local_eval(cwd)


def run_local_eval(cwd: str | Path) -> dict[str, Any]:
    """Generate deterministic trace runs that validate AgentOps plumbing."""
    cwd_path = Path(cwd).resolve()
    results: list[dict[str, Any]] = []
    for case in LOCAL_EVAL_CASES:
        recorder = TraceRecorder.start(
            cwd=cwd_path,
            model="deterministic-eval",
            request_summary=f"[{case.id}] {case.prompt}",
            mode="eval-local",
        )
        recorder.record("eval_case_started", {"case_id": case.id, "prompt": case.prompt})
        recorder.record_stream_event(
            AssistantTurnComplete(
                message=ConversationMessage(
                    role="assistant",
                    content=[
                        TextBlock(text=f"Planning case {case.id}."),
                        ToolUseBlock(id=f"toolu_{case.id}", name=case.tool_name, input={"case_id": case.id}),
                    ],
                ),
                usage=UsageSnapshot(input_tokens=12, output_tokens=6),
            )
        )
        recorder.record_stream_event(ToolExecutionStarted(tool_name=case.tool_name, tool_input={"case_id": case.id}))
        recorder.record_permission_decision(
            tool_name=case.tool_name,
            allowed=not case.should_block_permission,
            requires_confirmation=case.risk not in {"read-only", "credential-risk"},
            reason="deterministic eval policy",
            risk=case.risk,
            file_path="/tmp/fake" if case.risk in {"read-only", "filesystem-write", "credential-risk"} else None,
            command="pytest -q tests/test_example.py" if case.tool_name == "bash" else None,
        )
        if case.should_block_permission:
            recorder.record_stream_event(
                ToolExecutionCompleted(
                    tool_name=case.tool_name,
                    output="Permission denied by deterministic eval policy.",
                    is_error=True,
                    metadata={"duration_ms": 1.0},
                )
            )
        elif case.should_error:
            recorder.record_stream_event(
                ToolExecutionCompleted(
                    tool_name=case.tool_name,
                    output="Unknown tool: missing_tool",
                    is_error=True,
                    metadata={"duration_ms": 2.0},
                )
            )
        else:
            recorder.record_stream_event(
                ToolExecutionCompleted(
                    tool_name=case.tool_name,
                    output=f"Completed deterministic case {case.id}.",
                    is_error=False,
                    metadata={"duration_ms": 3.0},
                )
            )
        if case.id == "compact-aware":
            recorder.record(
                "compact_event",
                {
                    "phase": "compact_end",
                    "trigger": "auto",
                    "message": "deterministic compact checkpoint",
                },
            )
        recorder.finish(status="completed")
        summary = summarize_run(cwd_path, recorder.run_id)
        summary["case_id"] = case.id
        results.append(summary)
    return _build_scorecard(cwd_path, "local", results)


def run_swebench_smoke(cwd: str | Path) -> dict[str, Any]:
    """Record a lightweight SWE-bench compatibility smoke trace."""
    cwd_path = Path(cwd).resolve()
    cases = (
        {
            "instance_id": "swebench-lite-smoke-001",
            "repo": "pytest-dev/pytest",
            "problem_statement": "Validate that RepoTrace can import a public benchmark instance shape.",
        },
        {
            "instance_id": "swebench-verified-smoke-001",
            "repo": "django/django",
            "problem_statement": "Validate trace metadata for a verified-style software issue.",
        },
    )
    results: list[dict[str, Any]] = []
    for case in cases:
        recorder = TraceRecorder.start(
            cwd=cwd_path,
            model="swebench-smoke-adapter",
            request_summary=f"[{case['instance_id']}] {case['problem_statement']}",
            mode="eval-swebench-smoke",
        )
        recorder.record("benchmark_case_loaded", case)
        recorder.record_stream_event(
            AssistantTurnComplete(
                message=ConversationMessage(
                    role="assistant",
                    content=[TextBlock(text="Loaded benchmark metadata; no Docker solve was executed.")],
                ),
                usage=UsageSnapshot(input_tokens=20, output_tokens=9),
            )
        )
        recorder.finish(status="completed")
        summary = summarize_run(cwd_path, recorder.run_id)
        summary["case_id"] = case["instance_id"]
        results.append(summary)
    return _build_scorecard(cwd_path, "swebench-smoke", results)


def _build_scorecard(cwd: Path, suite: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item.get("status") == "completed")
    tool_calls = sum(int(item.get("tool_count") or 0) for item in results)
    tool_errors = sum(int(item.get("tool_error_count") or 0) for item in results)
    permission_decisions = sum(int(item.get("permission_decision_count") or 0) for item in results)
    permission_blocks = sum(int(item.get("permission_block_count") or 0) for item in results)
    scorecard = {
        "suite": suite,
        "generated_at": time.time(),
        "cwd": str(cwd),
        "total_cases": total,
        "passed_cases": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "tool_calls": tool_calls,
        "tool_error_rate": round(tool_errors / tool_calls, 4) if tool_calls else 0,
        "permission_decisions": permission_decisions,
        "permission_blocks": permission_blocks,
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in results),
        "runs": results,
    }
    out_dir = cwd / ".repotrace" / "evals"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{suite}-scorecard.json").write_text(
        json.dumps(scorecard, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return scorecard
