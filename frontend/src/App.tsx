import { useEffect, useMemo, useState } from "react";
import { Icon } from "./components/Icon";
import { api } from "./lib/api";
import { formatDuration, formatPercent, shortId } from "./lib/format";
import type { Dashboard, RunResult } from "./types";

const fallbackMetrics = {
  total_runs: 0,
  compliance_rate: 1,
  average_conversion_rate: 0,
  feedback_count: 0,
  average_rating: 0,
  memory_count: 0,
  bandit_arms: [],
};

const navItems = [
  { icon: "grid" as const, label: "运行总览", active: true },
  { icon: "flow" as const, label: "智能体图谱" },
  { icon: "book" as const, label: "营销知识库" },
  { icon: "pulse" as const, label: "评测中心" },
];

function App() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [activeRun, setActiveRun] = useState<RunResult | null>(null);
  const [segmentId, setSegmentId] = useState("steady-planner");
  const [objective, setObjective] = useState("在市场波动加剧时，为稳健客户提供有依据的资产配置教育");
  const [signal, setSignal] = useState("权益市场近五日波动显著放大，客户对回撤的咨询增加");
  const [tab, setTab] = useState<"overview" | "trace" | "memory">("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  async function loadDashboard() {
    const data = await api.dashboard();
    setDashboard(data);
    setActiveRun((current) => current ?? data.recent_runs[0] ?? null);
  }

  useEffect(() => {
    loadDashboard().catch((reason: Error) => setError(reason.message));
  }, []);

  async function runWorkflow() {
    setLoading(true);
    setError("");
    try {
      const run = await api.run({ segment_id: segmentId, objective, market_signal: signal });
      setActiveRun(run);
      setTab("overview");
      await loadDashboard();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "运行失败");
    } finally {
      setLoading(false);
    }
  }

  const metrics = dashboard?.metrics ?? fallbackMetrics;
  const product = activeRun?.selected_product;
  const execution = activeRun?.execution;
  const content = activeRun?.compliance.final_copy ?? "";
  const strategy = activeRun?.artifacts.find((artifact) => artifact.agent === "strategy-agent");
  const stageState = useMemo(() => {
    const state: Record<string, string> = {};
    activeRun?.events.forEach((event) => {
      if (event.status !== "started") state[event.stage] = event.status;
    });
    return state;
  }, [activeRun]);

  async function copyContent() {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><span /><span /><span /></div>
          <div><strong>FinLoop</strong><small>Growth Intelligence</small></div>
        </div>
        <nav className="nav-list">
          <p className="nav-kicker">工作空间</p>
          {navItems.map((item) => (
            <button className={`nav-item ${item.active ? "active" : ""}`} key={item.label}>
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.active && <i />}
            </button>
          ))}
          <p className="nav-kicker secondary">系统</p>
          <button className="nav-item"><Icon name="settings" /><span>运行配置</span></button>
        </nav>
        <div className="runtime-card">
          <div className="runtime-head"><span className="status-dot" />运行环境</div>
          <strong>离线安全模式</strong>
          <p>所有渠道执行均为仿真</p>
          <div className="runtime-meta"><span>Model</span><b>{activeRun?.model_provider ?? "deterministic/local"}</b></div>
        </div>
        <div className="sidebar-user">
          <div className="avatar">FL</div>
          <div><strong>项目演示空间</strong><small>杭州 · Sandbox</small></div>
          <span>···</span>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow"><span /> LIVE WORKSPACE</div>
            <h1>智能营销运行台</h1>
          </div>
          <div className="top-actions">
            <div className="audit-pill"><Icon name="shield" /><span>合规闸门</span><b>ON</b></div>
            <button className="primary-button compact" onClick={runWorkflow} disabled={loading}>
              <Icon name={loading ? "pulse" : "play"} />{loading ? "智能体协作中…" : "新建运行"}
            </button>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}

        <section className="metric-grid">
          <Metric label="闭环运行" value={String(metrics.total_runs).padStart(2, "0")} meta="全部轨迹可复现" tone="mint" />
          <Metric label="合规通过率" value={formatPercent(metrics.compliance_rate, 0)} meta="独立规则闸门" tone="blue" />
          <Metric label="平均转化率" value={execution ? formatPercent(execution.conversion_rate) : formatPercent(metrics.average_conversion_rate)} meta={execution ? `本轮 ${execution.converted} 个转化` : "等待首轮反馈"} tone="amber" />
          <Metric label="长期记忆" value={String(metrics.memory_count)} meta="情景 · 语义 · 流程" tone="violet" />
        </section>

        <div className="workspace-grid">
          <section className="panel flow-panel">
            <div className="panel-heading">
              <div><div className="section-kicker">AGENT ORCHESTRATION</div><h2>闭环执行图</h2></div>
              {activeRun ? (
                <div className="run-identity"><span>{shortId(activeRun.run_id)}</span><b>{formatDuration(activeRun.created_at, activeRun.completed_at)}</b></div>
              ) : <span className="muted">等待首次运行</span>}
            </div>
            <div className="pipeline">
              {(dashboard?.pipeline ?? defaultPipeline).map((node, index) => {
                const nodeState = stageState[node.id];
                return (
                  <div className="pipeline-wrap" key={node.id}>
                    <div className={`pipeline-node ${nodeState ?? "idle"}`}>
                      <div className="node-index">{nodeState ? <Icon name="check" /> : String(index + 1).padStart(2, "0")}</div>
                      <strong>{node.name}</strong><small>{node.agent}</small>
                    </div>
                    {index < (dashboard?.pipeline ?? defaultPipeline).length - 1 && <div className={`pipeline-link ${nodeState ? "active" : ""}`}><span /></div>}
                  </div>
                );
              })}
            </div>
            <div className="flow-summary">
              <div className="signal-orb"><Icon name="spark" /></div>
              <div className="flow-summary-copy">
                <span>当前策略判断</span>
                <strong>{strategy?.summary ?? "选择客群和目标后启动一次完整闭环"}</strong>
                <p>{activeRun ? activeRun.request.market_signal : "系统将并行分析市场信号与知识依据，再进入适当性和合规检查。"}</p>
              </div>
              {product && <div className="product-chip"><small>适配产品</small><b>{product.name}</b><span>R{product.risk_level} · {product.category}</span></div>}
            </div>
          </section>

          <section className="panel control-panel">
            <div className="panel-heading control-heading">
              <div><div className="section-kicker">MISSION CONTROL</div><h2>发起营销任务</h2></div>
              <span className="sandbox-tag">SANDBOX</span>
            </div>
            <label className="field-label">目标客群</label>
            <div className="segment-options">
              {(dashboard?.segments ?? []).map((segment) => (
                <button key={segment.id} className={segmentId === segment.id ? "selected" : ""} onClick={() => setSegmentId(segment.id)}>
                  <span>C{segment.risk_level}</span><div><strong>{segment.name}</strong><small>{segment.preferred_channel.toUpperCase()}</small></div>
                </button>
              ))}
            </div>
            <label className="field-label" htmlFor="objective">业务目标</label>
            <textarea id="objective" value={objective} onChange={(event) => setObjective(event.target.value)} rows={3} />
            <label className="field-label" htmlFor="signal">市场信号</label>
            <textarea id="signal" value={signal} onChange={(event) => setSignal(event.target.value)} rows={3} />
            <button className="primary-button full" onClick={runWorkflow} disabled={loading || !dashboard}>
              <Icon name={loading ? "pulse" : "play"} />
              {loading ? "正在协同 7 个智能体…" : "运行完整闭环"}
              {!loading && <Icon name="arrow" />}
            </button>
            <p className="safe-note"><Icon name="shield" />不会向真实客户发送消息，执行结果由可复现模拟器生成。</p>
          </section>
        </div>

        <section className="panel result-panel">
          <div className="result-tabs">
            <div>
              <button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>策略与内容</button>
              <button className={tab === "trace" ? "active" : ""} onClick={() => setTab("trace")}>决策轨迹 <span>{activeRun?.events.length ?? 0}</span></button>
              <button className={tab === "memory" ? "active" : ""} onClick={() => setTab("memory")}>记忆更新 <span>{activeRun?.memory_updates.length ?? 0}</span></button>
            </div>
            {activeRun && <span className={`result-status ${activeRun.compliance.status}`}><Icon name="shield" />{activeRun.compliance.status === "approved" ? "合规通过" : activeRun.compliance.status === "revised" ? "已修订通过" : "已阻断"} · {activeRun.compliance.score}</span>}
          </div>

          {!activeRun ? <EmptyState onRun={runWorkflow} /> : tab === "overview" ? (
            <div className="result-grid">
              <article className="content-preview">
                <div className="card-title"><div><span>FINAL COPY</span><h3>渠道内容预览</h3></div><button onClick={copyContent}><Icon name={copied ? "check" : "copy"} />{copied ? "已复制" : "复制"}</button></div>
                <div className="channel-line"><span>{activeRun.segment.preferred_channel.toUpperCase()}</span><i />面向 {activeRun.segment.name}</div>
                <div className="copy-body">{content}</div>
                <div className="copy-footer"><span>创意版本 · {execution?.variant ?? "—"}</span><span>{content.length} 字</span></div>
              </article>
              <div className="evidence-column">
                <article className="compliance-card">
                  <div className="card-title"><div><span>GUARDRAILS</span><h3>合规决策</h3></div><div className="score-ring">{activeRun.compliance.score}</div></div>
                  <div className="check-list">
                    {activeRun.compliance.checks.map((check) => <div key={check.rule}><span className={check.passed ? "pass" : "fail"}><Icon name={check.passed ? "check" : "shield"} /></span><p><strong>{check.rule}</strong><small>{check.detail}</small></p></div>)}
                  </div>
                </article>
                <article className="citation-card">
                  <div className="card-title"><div><span>EVIDENCE</span><h3>知识依据</h3></div><b>{activeRun.citations.length} sources</b></div>
                  {activeRun.citations.slice(0, 3).map((citation) => <div className="citation" key={citation.document_id}><span>{citation.document_id}</span><div><strong>{citation.title}</strong><p>{citation.excerpt}</p></div><b>{formatPercent(citation.score, 0)}</b></div>)}
                </article>
              </div>
            </div>
          ) : tab === "trace" ? (
            <EventTrace run={activeRun} />
          ) : (
            <MemoryView run={activeRun} />
          )}
        </section>
        <footer><span>FinLoop AI · 所有产品、客群和执行数据均为虚构演示</span><span>Event-sourced · Auditable · Offline-first</span></footer>
      </main>
    </div>
  );
}

const defaultPipeline = [
  { id: "insight", name: "洞察", agent: "Insight Agent" },
  { id: "retrieve", name: "知识", agent: "Knowledge Agent" },
  { id: "decide", name: "决策", agent: "Strategy Agent" },
  { id: "compose", name: "内容", agent: "Content Agent" },
  { id: "guard", name: "合规", agent: "Compliance Agent" },
  { id: "execute", name: "执行", agent: "Execution Agent" },
  { id: "learn", name: "反馈", agent: "Feedback Agent" },
];

function Metric({ label, value, meta, tone }: { label: string; value: string; meta: string; tone: string }) {
  return <article className={`metric-card ${tone}`}><div className="metric-top"><span>{label}</span><i /></div><strong>{value}</strong><p><span>↗</span>{meta}</p><div className="micro-chart"><i/><i/><i/><i/><i/><i/></div></article>;
}

function EmptyState({ onRun }: { onRun: () => void }) {
  return <div className="empty-state"><div><Icon name="spark" /></div><h3>准备好运行第一个闭环</h3><p>系统将生成完整的决策轨迹、合规审查、仿真执行结果与可检索记忆。</p><button className="primary-button compact" onClick={onRun}><Icon name="play" />启动演示</button></div>;
}

function EventTrace({ run }: { run: RunResult }) {
  return <div className="trace-view"><div className="trace-meta"><div><span>上下文预算</span><b>{run.context_trace.estimated_tokens} / {run.context_trace.budget} tokens</b></div><div><span>纳入区块</span><b>{run.context_trace.included_sections.length}</b></div><div><span>隐私脱敏</span><b>{run.context_trace.redactions}</b></div><div><span>状态</span><b>{run.status.toUpperCase()}</b></div></div><div className="timeline">{run.events.map((event) => <div className="timeline-row" key={event.sequence}><div className="timeline-seq">{String(event.sequence).padStart(2, "0")}</div><div className={`timeline-dot ${event.status}`} /><div className="timeline-body"><div><strong>{event.agent}</strong><span>{event.stage}</span><time>{new Date(event.timestamp).toLocaleTimeString("zh-CN", { hour12: false })}</time></div><p>{event.message}</p></div></div>)}</div></div>;
}

function MemoryView({ run }: { run: RunResult }) {
  const labels: Record<string, { name: string; desc: string }> = { episodic: { name: "情景记忆", desc: "本次运行发生了什么" }, semantic: { name: "语义记忆", desc: "关于客群的新认知" }, procedural: { name: "流程记忆", desc: "以后应该如何决策" } };
  return <div className="memory-view"><div className="memory-intro"><Icon name="memory" /><div><h3>反馈已经写回长期记忆</h3><p>下一次相似任务会按相关性、重要度和时间衰减召回，而不是塞入完整历史。</p></div></div><div className="memory-grid">{run.memory_updates.map((memory) => <article key={memory.id}><div><span>{labels[memory.kind]?.name ?? memory.kind}</span><b>{formatPercent(memory.importance, 0)} 重要度</b></div><h4>{labels[memory.kind]?.desc}</h4><p>{memory.content}</p><small>{memory.namespace} · {memory.id}</small></article>)}</div></div>;
}

export default App;
