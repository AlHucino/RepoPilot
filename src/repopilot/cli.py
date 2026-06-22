"""RepoPilot CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import typer

from openharness.runlog.evals import run_eval_suite
from openharness.runlog.trace import export_run_markdown, list_runs, load_run_events, summarize_run

app = typer.Typer(
    help="RepoPilot: run repository-task agents, inspect traces, and run evals.",
    no_args_is_help=True,
)
trace_app = typer.Typer(help="Inspect persistent run timelines.", no_args_is_help=True)
eval_app = typer.Typer(help="Run deterministic RepoPilot eval suites.", no_args_is_help=True)
app.add_typer(trace_app, name="trace")
app.add_typer(eval_app, name="eval")


def _cwd(value: str | None) -> Path:
    return Path(value or ".").expanduser().resolve()


@app.callback()
def main() -> None:
    """RepoPilot command group."""


@trace_app.command("list")
def trace_list(
    cwd: str | None = typer.Option(None, "--cwd", help="Project directory. Defaults to current directory."),
    limit: int = typer.Option(20, "--limit", min=1, max=200, help="Maximum runs to show."),
) -> None:
    """List recent trace runs."""
    runs = list_runs(_cwd(cwd), limit=limit)
    if not runs:
        typer.echo("No trace runs found.")
        return
    for run in runs:
        typer.echo(
            f"{run['run_id']}  status={run['status']}  tools={run['tool_count']}  "
            f"errors={run['error_count']}  tokens={run['total_tokens']}  "
            f"request={run['request_summary']}"
        )


@trace_app.command("show")
def trace_show(
    run_id: str = typer.Argument(..., help="Trace run id."),
    cwd: str | None = typer.Option(None, "--cwd", help="Project directory. Defaults to current directory."),
    raw: bool = typer.Option(False, "--raw", help="Print raw JSONL events instead of a scorecard."),
) -> None:
    """Show one trace run."""
    project = _cwd(cwd)
    if raw:
        for event in load_run_events(project, run_id):
            typer.echo(json.dumps(event, ensure_ascii=False))
        return
    typer.echo(json.dumps(summarize_run(project, run_id), indent=2, ensure_ascii=False))


@trace_app.command("export")
def trace_export(
    run_id: str = typer.Argument(..., help="Trace run id."),
    cwd: str | None = typer.Option(None, "--cwd", help="Project directory. Defaults to current directory."),
    fmt: Literal["markdown", "json"] = typer.Option("markdown", "--format", help="Export format."),
    output: str | None = typer.Option(None, "--output", "-o", help="Output path."),
) -> None:
    """Export a trace run."""
    project = _cwd(cwd)
    if fmt == "json":
        events = load_run_events(project, run_id)
        out = (
            Path(output).expanduser().resolve()
            if output
            else project / ".repopilot" / "traces" / f"run-{run_id}.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        typer.echo(str(out))
        return
    typer.echo(str(export_run_markdown(project, run_id, output_path=output)))


@eval_app.command("run")
def eval_run(
    suite: Literal["local", "swebench-smoke"] = typer.Option("local", "--suite", help="Eval suite to run."),
    cwd: str | None = typer.Option(None, "--cwd", help="Project directory. Defaults to current directory."),
) -> None:
    """Run an eval suite and emit a scorecard."""
    scorecard = run_eval_suite(_cwd(cwd), suite=suite)
    typer.echo(json.dumps(scorecard, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
