import { useEffect, useMemo, useState } from "react";
import type { Snapshot, TimelineEvent, TraceRun } from "./types";

function fmtNumber(value?: number): string {
  if (value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

function fmtDate(ts?: number): string {
  if (!ts) return "-";
  return new Date(ts * 1000).toISOString().replace("T", " ").replace(".000Z", " UTC");
}

function severityClass(event: TimelineEvent): string {
  return `timeline-dot ${event.severity || "info"}`;
}

function RunRow({ run }: { run: TraceRun }) {
  const toolErrorRate = run.tool_count ? run.tool_error_count / run.tool_count : 0;
  return (
    <article className="run-row">
      <div>
        <div className="mono strong">{run.run_id}</div>
        <div className="muted">{run.request_summary}</div>
      </div>
      <div>{run.model}</div>
      <div>{run.status}</div>
      <div>{fmtNumber(run.duration_ms)} ms</div>
      <div>{run.tool_count}</div>
      <div>{fmtNumber(toolErrorRate * 100)}%</div>
      <div>{run.permission_block_count}</div>
      <div>{run.total_tokens}</div>
    </article>
  );
}

export function App() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("./snapshot.json", { cache: "no-store" })
      .then((response) => response.json())
      .then(setSnapshot)
      .catch((err) => setError(String(err)));
  }, []);

  const filteredRuns = useMemo(() => {
    if (!snapshot) return [];
    const needle = filter.trim().toLowerCase();
    if (!needle) return snapshot.runs;
    return snapshot.runs.filter((run) =>
      [run.run_id, run.status, run.model, run.request_summary].join(" ").toLowerCase().includes(needle)
    );
  }, [filter, snapshot]);

  if (error) {
    return <main className="shell"><div className="empty">Failed to load snapshot.json: {error}</div></main>;
  }

  if (!snapshot) {
    return <main className="shell"><div className="empty">Loading RepoPilot snapshot...</div></main>;
  }

  const scorecard = snapshot.scorecard;
  const risks = Object.entries(snapshot.risk_breakdown || {});

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <div className="eyebrow">REPOPILOT</div>
          <h1>{snapshot.project_name}</h1>
          <p>{snapshot.headline}</p>
        </div>
        <div className="hero-meta">
          <span>Generated {fmtDate(snapshot.generated_at)}</span>
          <span>{snapshot.repo_path}</span>
        </div>
      </section>

      <section className="stats-grid">
        <article className="stat">
          <span>Eval Pass Rate</span>
          <strong>{fmtNumber(scorecard.pass_rate * 100)}%</strong>
          <small>{scorecard.passed_cases}/{scorecard.total_cases} deterministic cases</small>
        </article>
        <article className="stat">
          <span>Tool Error Rate</span>
          <strong>{fmtNumber(scorecard.tool_error_rate * 100)}%</strong>
          <small>{scorecard.tool_calls} tool calls traced</small>
        </article>
        <article className="stat">
          <span>Permission Blocks</span>
          <strong>{scorecard.permission_blocks}</strong>
          <small>{scorecard.permission_decisions} decisions recorded</small>
        </article>
        <article className="stat">
          <span>Token Footprint</span>
          <strong>{scorecard.total_tokens}</strong>
          <small>input + output tokens</small>
        </article>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Run Timeline</h2>
          <input
            type="search"
            placeholder="Filter run id, model, status, or request..."
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </div>
        <div className="run-head">
          <span>Run</span>
          <span>Model</span>
          <span>Status</span>
          <span>Duration</span>
          <span>Tools</span>
          <span>Tool Err</span>
          <span>Blocks</span>
          <span>Tokens</span>
        </div>
        <div className="run-list">
          {filteredRuns.map((run) => <RunRow key={run.run_id} run={run} />)}
          {filteredRuns.length === 0 && <div className="empty">No matching runs.</div>}
        </div>
      </section>

      <section className="two-col">
        <article className="panel">
          <div className="panel-header">
            <h2>Timeline</h2>
          </div>
          <div className="timeline">
            {snapshot.timeline.map((event, index) => (
              <div className="timeline-item" key={`${event.kind}-${index}`}>
                <span className={severityClass(event)} />
                <div>
                  <div className="timeline-title">
                    <span>{event.title}</span>
                    <code>{fmtNumber(event.elapsed_ms)} ms</code>
                  </div>
                  {event.detail && <p>{event.detail}</p>}
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <h2>Risk Audit</h2>
          </div>
          <div className="risk-list">
            {risks.map(([risk, count]) => (
              <div className="risk-row" key={risk}>
                <span>{risk}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
