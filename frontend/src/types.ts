export type Segment = {
  id: string;
  name: string;
  description: string;
  risk_level: number;
  preferred_channel: string;
  concerns: string[];
};

export type Citation = {
  document_id: string;
  title: string;
  source: string;
  excerpt: string;
  score: number;
};

export type PipelineEvent = {
  sequence: number;
  run_id: string;
  timestamp: string;
  agent: string;
  stage: string;
  status: "started" | "completed" | "revised" | "blocked";
  message: string;
  payload: Record<string, unknown>;
};

export type AgentArtifact = {
  agent: string;
  title: string;
  summary: string;
  data: Record<string, unknown>;
  citations: Citation[];
  confidence: number;
};

export type RunResult = {
  run_id: string;
  status: "completed" | "blocked" | "failed";
  created_at: string;
  completed_at: string;
  request: {
    segment_id: string;
    objective: string;
    market_signal: string;
    dry_run: boolean;
  };
  segment: Segment;
  selected_product: {
    id: string;
    name: string;
    risk_level: number;
    category: string;
    horizon: string;
    highlights: string[];
    risks: string[];
  } | null;
  artifacts: AgentArtifact[];
  events: PipelineEvent[];
  citations: Citation[];
  compliance: {
    status: "approved" | "revised" | "blocked";
    score: number;
    violations: string[];
    checks: Array<{ rule: string; passed: boolean; detail: string }>;
    final_copy: string;
  };
  execution: {
    mode: string;
    variant: string;
    channel: string;
    audience_size: number;
    delivered: number;
    opened: number;
    converted: number;
    open_rate: number;
    conversion_rate: number;
    idempotency_key: string;
  } | null;
  context_trace: {
    budget: number;
    estimated_tokens: number;
    included_sections: string[];
    dropped_sections: string[];
    redactions: number;
  };
  memory_updates: Array<{
    id: string;
    namespace: string;
    kind: string;
    content: string;
    importance: number;
  }>;
  model_provider: string;
};

export type Dashboard = {
  metrics: {
    total_runs: number;
    compliance_rate: number;
    average_conversion_rate: number;
    feedback_count: number;
    average_rating: number;
    memory_count: number;
    bandit_arms: Array<{
      arm: string;
      alpha: number;
      beta: number;
      impressions: number;
      conversions: number;
    }>;
  };
  segments: Segment[];
  recent_runs: RunResult[];
  pipeline: Array<{ id: string; name: string; agent: string }>;
};
