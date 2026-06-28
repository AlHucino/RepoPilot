"""Persistent RepoPilot run timeline storage.

The original runtime emits stream events for UI rendering and stores session
snapshots for resume. RepoPilot turns those runtime signals into durable,
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


TRACE_DIR_NAME = ".repopilot"
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


def _load_latest_scorecard(cwd: Path) -> dict[str, Any] | None:
    eval_dir = cwd / TRACE_DIR_NAME / "evals"
    if not eval_dir.exists():
        return None
    for path in sorted(eval_dir.glob("*-scorecard.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _scorecard_from_runs(cwd: Path, runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    completed = sum(1 for run in runs if run.get("status") == "completed")
    tool_calls = sum(int(run.get("tool_count") or 0) for run in runs)
    tool_errors = sum(int(run.get("tool_error_count") or 0) for run in runs)
    permission_decisions = sum(int(run.get("permission_decision_count") or 0) for run in runs)
    permission_blocks = sum(int(run.get("permission_block_count") or 0) for run in runs)
    return {
        "suite": "traces",
        "generated_at": time.time(),
        "cwd": str(cwd),
        "total_cases": total,
        "passed_cases": completed,
        "pass_rate": round(completed / total, 4) if total else 0,
        "tool_calls": tool_calls,
        "tool_error_rate": round(tool_errors / tool_calls, 4) if tool_calls else 0,
        "permission_decisions": permission_decisions,
        "permission_blocks": permission_blocks,
        "total_tokens": sum(int(run.get("total_tokens") or 0) for run in runs),
        "runs": runs,
    }


def _dashboard_timeline(events: list[dict[str, Any]], *, limit: int = 30) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for event in events:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        kind = str(event.get("kind") or "event")
        elapsed_ms = float(event.get("elapsed_ms") or 0)
        if kind == "run_started":
            title = "Run started"
            detail = str(payload.get("request_summary") or "")
            severity = "info"
        elif kind == "assistant_turn":
            title = "Assistant turn"
            detail = str(payload.get("text") or "")
            severity = "info"
        elif kind == "tool_started":
            title = f"Tool started: {payload.get('tool_name') or 'unknown'}"
            detail = ""
            severity = "info"
        elif kind == "tool_completed":
            failed = bool(payload.get("is_error"))
            title = f"Tool {'failed' if failed else 'completed'}: {payload.get('tool_name') or 'unknown'}"
            detail = str(payload.get("output_preview") or "")
            severity = "error" if failed else "success"
        elif kind == "permission_decision":
            allowed = bool(payload.get("allowed"))
            risk = str(payload.get("risk") or "unknown")
            title = f"Permission {'allowed' if allowed else 'blocked'}: {payload.get('tool_name') or 'unknown'}"
            detail = f"{risk}: {payload.get('reason') or ''}".strip()
            severity = "info" if allowed else "warning"
        elif kind == "compact_event":
            title = "Context compact event"
            detail = f"{payload.get('trigger') or '-'} / {payload.get('phase') or '-'}"
            severity = "info"
        elif kind == "error":
            title = "Runtime error"
            detail = str(payload.get("message") or "")
            severity = "error"
        elif kind == "run_completed":
            title = "Run completed"
            detail = f"status={payload.get('status', 'unknown')}"
            severity = "success" if payload.get("status") == "completed" else "warning"
        else:
            continue
        timeline.append(
            {
                "elapsed_ms": elapsed_ms,
                "kind": kind,
                "title": _summarize(title, limit=120),
                "detail": _summarize(detail, limit=260),
                "severity": severity,
            }
        )
    return timeline[-limit:]


def export_dashboard_snapshot(
    cwd: str | Path,
    *,
    output_path: str | Path | None = None,
    limit: int = 50,
) -> Path:
    """Export real RepoPilot traces and scorecard data for the React dashboard."""
    cwd_path = Path(cwd).resolve()
    raw_runs = list_runs(cwd_path, limit=limit)
    runs = [{key: value for key, value in run.items() if key != "path"} for run in raw_runs]
    scorecard = dict(_load_latest_scorecard(cwd_path) or _scorecard_from_runs(cwd_path, runs))
    scorecard["cwd"] = f"./{cwd_path.name}"
    all_events: list[dict[str, Any]] = []
    for run in raw_runs:
        run_id = str(run.get("run_id") or "")
        if not run_id:
            continue
        try:
            all_events.extend(load_run_events(cwd_path, run_id))
        except (OSError, json.JSONDecodeError):
            continue

    latest_events: list[dict[str, Any]] = []
    if runs:
        try:
            latest_events = load_run_events(cwd_path, str(runs[0]["run_id"]))
        except (OSError, json.JSONDecodeError, KeyError):
            latest_events = []

    risk_breakdown: dict[str, int] = {}
    for event in all_events:
        if event.get("kind") != "permission_decision":
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        risk = str(payload.get("risk") or "unknown")
        risk_breakdown[risk] = risk_breakdown.get(risk, 0) + 1

    snapshot = {
        "generated_at": time.time(),
        "project_name": cwd_path.name or "RepoPilot",
        "repo_path": f"./{cwd_path.name}",
        "headline": (
            f"{len(runs)} trace run(s) loaded from .repopilot with "
            f"{int(scorecard.get('tool_calls') or 0)} tool calls and "
            f"{int(scorecard.get('permission_decisions') or 0)} permission decisions."
        ),
        "scorecard": scorecard,
        "runs": runs,
        "timeline": _dashboard_timeline(latest_events),
        "risk_breakdown": dict(sorted(risk_breakdown.items())),
    }
    output = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else cwd_path / "repopilot-dashboard" / "public" / "snapshot.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
    return output


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
        f"# RepoPilot Run {run_id}",
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
