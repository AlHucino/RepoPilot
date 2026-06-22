export interface TraceRun {
  run_id: string;
  status: string;
  model: string;
  request_summary: string;
  duration_ms?: number;
  event_count: number;
  assistant_turns: number;
  tool_count: number;
  tool_error_count: number;
  permission_decision_count: number;
  permission_block_count: number;
  compact_event_count: number;
  error_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface TimelineEvent {
  elapsed_ms: number;
  kind: string;
  title: string;
  detail?: string;
  severity?: "info" | "success" | "warning" | "error";
}

export interface EvalScorecard {
  suite: string;
  total_cases: number;
  passed_cases: number;
  pass_rate: number;
  tool_calls: number;
  tool_error_rate: number;
  permission_decisions: number;
  permission_blocks: number;
  total_tokens: number;
}

export interface Snapshot {
  generated_at: number;
  project_name: string;
  repo_path: string;
  headline: string;
  scorecard: EvalScorecard;
  runs: TraceRun[];
  timeline: TimelineEvent[];
  risk_breakdown: Record<string, number>;
}
