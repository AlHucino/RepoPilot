"""Persistent AgentOps trace storage.

The original runtime emits stream events for UI rendering and stores session
snapshots for resume.  RepoTrace turns those runtime signals into durable,
queryable execution traces that can be exported and scored.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from openharness.api.usage import UsageSnapshot
from openharness.engine.stream_events import (
    AssistantTurnComplete,
    CompactProgressEvent,
    ErrorEvent,
    StreamEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from openharness.utils.fs import atomic_write_text


TRACE_DIR_NAME = ".repotrace"
TRACE_SUBDIR = "traces"
TRACE_SCHEMA_VERSION = 1


def get_project_trace_dir(cwd: str | Path) -> Path:
    """Return the per-project trace directory."""
    trace_dir = Path(cwd).resolve() / TRACE_DIR_NAME / TRACE_SUBDIR
    trace_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, UsageSnapshot):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            return str(value)
    return str(value)


def _summarize(text: str, *, limit: int = 300) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def classify_tool_risk(
    tool_name: str,
    *,
    is_read_only: bool,
    file_path: str | None = None,
    command: str | None = None,
) -> str:
    """Classify a tool call for audit and dashboard grouping."""
    if is_read_only:
        return "read-only"
    lowered_name = tool_name.lower()
    lowered_command = (command or "").lower()
    if file_path and any(marker in file_path for marker in (".ssh", ".aws", ".kube", ".docker")):
        return "credential-risk"
    if lowered_name in {"bash", "shell"}:
        if any(token in lowered_command for token in ("rm ", "sudo ", "chmod ", "chown ", "deploy")):
            return "shell-command-high-risk"
        return "shell-command"
    if any(token in lowered_name for token in ("write", "edit", "notebook")):
        return "filesystem-write"
    if any(token in lowered_name for token in ("web", "mcp", "http")):
        return "network"
    return "mutating-tool"


@dataclass
class TraceRecorder:
    """Append-only JSONL recorder for one agent run."""

    cwd: Path
    model: str
    request_summary: str
    mode: str = "submit"
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    started_at: float = field(default_factory=time.time)
    path: Path | None = None
    _event_count: int = 0
    _tool_count: int = 0
    _tool_error_count: int = 0
    _permission_block_count: int = 0

    @classmethod
    def start(
        cls,
        *,
        cwd: str | Path,
        model: str,
        request_summary: str,
        mode: str = "submit",
    ) -> "TraceRecorder":
        recorder = cls(
            cwd=Path(cwd).resolve(),
            model=model,
            request_summary=_summarize(request_summary),
            mode=mode,
        )
        recorder.path = get_project_trace_dir(recorder.cwd) / f"run-{recorder.run_id}.jsonl"
        recorder.record(
            "run_started",
            {
                "schema_version": TRACE_SCHEMA_VERSION,
                "cwd": str(recorder.cwd),
                "model": recorder.model,
                "request_summary": recorder.request_summary,
                "mode": recorder.mode,
            },
        )
        return recorder

    def record(self, kind: str, payload: dict[str, Any] | None = None) -> None:
        """Append one trace event."""
        if self.path is None:
            return
        now = time.time()
        event = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "kind": kind,
            "timestamp": now,
            "elapsed_ms": round((now - self.started_at) * 1000, 3),
            "payload": _json_safe(payload or {}),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
        self._event_count += 1

    def record_stream_event(self, event: StreamEvent, usage: UsageSnapshot | None = None) -> None:
        """Persist a runtime stream event in trace form."""
        if isinstance(event, AssistantTurnComplete):
            self.record(
                "assistant_turn",
                {
                    "text": _summarize(event.message.text, limit=800),
                    "tool_uses": [
                        {"id": tool.id, "name": tool.name, "input": tool.input}
                        for tool in event.message.tool_uses
                    ],
                    "usage": (usage or event.usage).model_dump(),
                },
            )
            return
        if isinstance(event, ToolExecutionStarted):
            self._tool_count += 1
            self.record(
                "tool_started",
                {
                    "tool_name": event.tool_name,
                    "tool_input": event.tool_input,
                },
            )
            return
        if isinstance(event, ToolExecutionCompleted):
            if event.is_error:
                self._tool_error_count += 1
            self.record(
                "tool_completed",
                {
                    "tool_name": event.tool_name,
                    "is_error": event.is_error,
                    "output_preview": _summarize(event.output, limit=1000),
                    "output_chars": len(event.output or ""),
                    "metadata": event.metadata or {},
                },
            )
            return
        if isinstance(event, ErrorEvent):
            self.record(
                "error",
                {
                    "message": event.message,
                    "recoverable": event.recoverable,
                },
            )
            return
        if isinstance(event, CompactProgressEvent):
            self.record(
                "compact_event",
                {
                    "phase": event.phase,
                    "trigger": event.trigger,
                    "message": event.message,
                    "attempt": event.attempt,
                    "checkpoint": event.checkpoint,
                    "metadata": event.metadata or {},
                },
            )

    def record_permission_decision(
        self,
        *,
        tool_name: str,
        allowed: bool,
        requires_confirmation: bool,
        reason: str,
        risk: str,
        file_path: str | None = None,
        command: str | None = None,
    ) -> None:
        if not allowed:
            self._permission_block_count += 1
        self.record(
            "permission_decision",
            {
                "tool_name": tool_name,
                "allowed": allowed,
                "requires_confirmation": requires_confirmation,
                "reason": reason,
                "risk": risk,
                "file_path": file_path,
                "command": command,
            },
        )

    def record_permission_confirmation(self, *, tool_name: str, confirmed: bool, reason: str) -> None:
        self.record(
            "permission_confirmation",
            {
                "tool_name": tool_name,
                "confirmed": confirmed,
                "reason": reason,
            },
        )

    def finish(self, *, status: str = "completed") -> None:
        """Append a terminal run summary."""
        duration_ms = round((time.time() - self.started_at) * 1000, 3)
        self.record(
            "run_completed",
            {
                "status": status,
                "duration_ms": duration_ms,
                "event_count": self._event_count,
                "tool_count": self._tool_count,
                "tool_error_count": self._tool_error_count,
                "permission_block_count": self._permission_block_count,
            },
        )


def load_run_events(cwd: str | Path, run_id: str) -> list[dict[str, Any]]:
    """Load all events for a run."""
    path = get_project_trace_dir(cwd) / f"run-{run_id}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Trace run not found: {run_id}")
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def list_runs(cwd: str | Path, *, limit: int = 20) -> list[dict[str, Any]]:
    """List recent trace runs, newest first."""
    trace_dir = get_project_trace_dir(cwd)
    runs: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("run-*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
        run_id = path.stem.replace("run-", "", 1)
        try:
            events = load_run_events(cwd, run_id)
            summary = summarize_events(events)
            summary["path"] = str(path)
            runs.append(summary)
        except (OSError, json.JSONDecodeError):
            continue
        if len(runs) >= limit:
            break
    return runs


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a compact scorecard from trace events."""
    if not events:
        return {}
    run_id = str(events[0].get("run_id") or "")
    started = next((event for event in events if event.get("kind") == "run_started"), events[0])
    completed = next((event for event in reversed(events) if event.get("kind") == "run_completed"), None)
    assistant_turns = [event for event in events if event.get("kind") == "assistant_turn"]
    tool_events = [event for event in events if event.get("kind") == "tool_completed"]
    permission_events = [event for event in events if event.get("kind") == "permission_decision"]
    errors = [event for event in events if event.get("kind") == "error"]
    compact_events = [event for event in events if event.get("kind") == "compact_event"]
    usage = UsageSnapshot()
    for event in assistant_turns:
        payload = event.get("payload") or {}
        raw_usage = payload.get("usage") or {}
        usage.input_tokens += int(raw_usage.get("input_tokens") or 0)
        usage.output_tokens += int(raw_usage.get("output_tokens") or 0)
    completed_payload = (completed or {}).get("payload") or {}
    started_payload = started.get("payload") or {}
    return {
        "run_id": run_id,
        "status": completed_payload.get("status", "running"),
        "model": started_payload.get("model", ""),
        "request_summary": started_payload.get("request_summary", ""),
        "started_at": started.get("timestamp"),
        "duration_ms": completed_payload.get("duration_ms"),
        "event_count": len(events),
        "assistant_turns": len(assistant_turns),
        "tool_count": len(tool_events),
        "tool_error_count": sum(1 for event in tool_events if (event.get("payload") or {}).get("is_error")),
        "permission_decision_count": len(permission_events),
        "permission_block_count": sum(
            1 for event in permission_events if not (event.get("payload") or {}).get("allowed")
        ),
        "compact_event_count": len(compact_events),
        "error_count": len(errors),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
    }


def summarize_run(cwd: str | Path, run_id: str) -> dict[str, Any]:
    """Summarize one run by ID."""
    return summarize_events(load_run_events(cwd, run_id))


def export_run_markdown(cwd: str | Path, run_id: str, *, output_path: str | Path | None = None) -> Path:
    """Export one run as a human-readable Markdown report."""
    events = load_run_events(cwd, run_id)
    summary = summarize_events(events)
    if output_path is None:
        output = get_project_trace_dir(cwd) / f"run-{run_id}.md"
    else:
        output = Path(output_path)
    lines = [
        f"# RepoTrace Run {run_id}",
        "",
        "## Scorecard",
        "",
        f"- Status: {summary.get('status')}",
        f"- Model: {summary.get('model')}",
        f"- Request: {summary.get('request_summary')}",
        f"- Duration: {summary.get('duration_ms')} ms",
        f"- Tool calls: {summary.get('tool_count')} ({summary.get('tool_error_count')} errors)",
        f"- Permission decisions: {summary.get('permission_decision_count')} "
        f"({summary.get('permission_block_count')} blocked)",
        f"- Compact events: {summary.get('compact_event_count')}",
        f"- Tokens: {summary.get('total_tokens')} total "
        f"({summary.get('input_tokens')} input / {summary.get('output_tokens')} output)",
        "",
        "## Timeline",
        "",
    ]
    for event in events:
        payload = event.get("payload") or {}
        kind = event.get("kind")
        elapsed = event.get("elapsed_ms")
        if kind == "assistant_turn":
            lines.append(f"- `{elapsed}ms` assistant: {payload.get('text', '')}")
        elif kind == "tool_started":
            lines.append(f"- `{elapsed}ms` tool started: `{payload.get('tool_name')}`")
        elif kind == "tool_completed":
            status = "error" if payload.get("is_error") else "ok"
            lines.append(f"- `{elapsed}ms` tool completed: `{payload.get('tool_name')}` ({status})")
        elif kind == "permission_decision":
            decision = "allowed" if payload.get("allowed") else "blocked"
            lines.append(
                f"- `{elapsed}ms` permission: `{payload.get('tool_name')}` {decision} "
                f"[{payload.get('risk')}] {payload.get('reason')}"
            )
        elif kind == "compact_event":
            lines.append(f"- `{elapsed}ms` compact: {payload.get('trigger')}/{payload.get('phase')}")
        elif kind == "error":
            lines.append(f"- `{elapsed}ms` error: {payload.get('message')}")
        elif kind in {"run_started", "run_completed"}:
            lines.append(f"- `{elapsed}ms` {kind}: {payload}")
    atomic_write_text(output, "\n".join(lines).rstrip() + "\n")
    return output
