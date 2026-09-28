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
  content_hash?: string;
  effective_date?: string;
  retrieval_reason?: string;
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
  confidence: number | null;
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
    seed?: number;
    variant?: string;
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
  model_calls?: Array<{outcome: string; configured_provider: string; latency_ms: number}>;
  evidence_passport?: Passport;
};

export type Document = {
  id: string; title: string; category: string; source: string;
  effective_date: string; content: string; content_hash: string;
};
export type Passport = {
  version: string; policy_version: string; retrieval: string; seed: number;
  context_sha256: string; input_sha256: string; sources: Document[]; memory_ids: string[];
  boundaries: string; prompt_versions?: Record<string, string>;
  verification?: Array<{id: string; snapshot_integrity: boolean; current_matches: boolean}>;
};
export type Job = {
  id: string; status: "queued" | "running" | "completed" | "blocked" | "failed" | "interrupted";
  run_id: string | null; attempts: number; error: string | null;
  created_at: string; updated_at: string; request: RunResult["request"]; events?: PipelineEvent[];
  history?: Array<{attempt: number; run_id: string; status: string; created_at: string; events: PipelineEvent[]}>;
};
export type Memory = {
  id: string; namespace: string; kind: string; content: string; importance: number;
  active: number; created_at: string; metadata: Record<string, unknown>; duplicate_count: number;
};
export type Evaluation = {
  id: string; total: number; passed: number; pass_rate: number; corpus_documents: number;
  latency_ms: number; scope: string; created_at: string; learning_writes: number;
  retrieval_metrics: {recall_at_2: number; precision_at_2: number; mrr_at_2: number};
  cases: Array<{case_id: string; category: string; passed: boolean; detail: string}>;
};
export type Experiment = {
  id: string; cohort_key: string; notice: string; method: string; learning_writes: number;
  request: {run_id: string; seed: number; sample_size: number; stress: number; fatigue: number};
  assumptions: Record<string, unknown>;
  variants: Array<{
    variant: string; delivered: number; opened: number; converted: number;
    audience_conversion_rate: number; interval95: number[]; paired_interval95: number[];
    difference_vs_clarity: number; conclusion: string;
  }>;
};
export type Report<T> = {id: string; kind: string; created_at: string; payload: T};

export type ModelProbe = {
  status: "ready" | "local" | "invalid-schema" | "unavailable";
  provider: string; key_configured: boolean; remote_request_sent: boolean;
  outcome: string; latency_ms: number; message: string; cost_notice: string;
};

export type RunComparison = {
  left: {run_id: string; created_at: string; status: string};
  right: {run_id: string; created_at: string; status: string};
  quality: {level: "strong" | "partial" | "contextual"; label: string; detail: string};
  dimensions: Array<{key: string; label: string; left: unknown; right: unknown; changed: boolean}>;
  evidence: {
    same: boolean;
    added: Array<{id: string; title: string}>;
    removed: Array<{id: string; title: string}>;
    version_changed: Array<{id: string; title: string; left_hash: string; right_hash: string}>;
    unchanged_ids: string[];
  };
  funnel: Array<{
    key: string; label: string; left: number | null; right: number | null;
    delta: number | null; unit: "count" | "rate";
  }>;
  content: {left_characters: number; right_characters: number; similarity: number; changed: boolean};
  interpretation: string[];
  boundaries: string;
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
