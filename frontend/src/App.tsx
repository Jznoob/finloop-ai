import { useEffect, useRef, useState } from "react";
import { Icon } from "./components/Icon";
import { api } from "./lib/api";
import { formatPercent, shortId } from "./lib/format";
import { StudioPages } from "./components/StudioPages";
import { RunDetail } from "./components/RunDetail";
import type { Dashboard, Job, RunResult } from "./types";

export type Page = "overview" | "lab" | "knowledge" | "memory" | "evals" | "history" | "settings";
const navigation = [
  { id: "overview", label: "运行工作台", icon: "grid", description: "从目标到可复查的决策" },
  { id: "lab", label: "策略实验室", icon: "spark", description: "固定样本，检验策略对假设的敏感性" },
  { id: "knowledge", label: "证据知识库", icon: "book", description: "检索原文，检查引用与版本" },
  { id: "memory", label: "记忆管理", icon: "memory", description: "检查来源，管理后续任务可召回的记忆" },
  { id: "evals", label: "质量评测", icon: "shield", description: "独立环境中的检索、拒答与流程回归" },
  { id: "history", label: "运行历史", icon: "clock", description: "找回每次任务，导出证据或重新尝试" },
  { id: "settings", label: "运行配置", icon: "settings", description: "查看当前能力、模型连接与运行边界" },
] as const;
const stageNames = ["洞察", "知识", "决策", "内容", "合规", "执行", "反馈"];
const stages = ["insight", "retrieve", "decide", "compose", "guard", "execute", "learn"];
const initialRequest: RunResult["request"] = {
  segment_id: "steady-planner", objective: "在市场波动加剧时，为稳健客户提供有依据的资产配置教育",
  market_signal: "权益市场近五日波动显著放大，客户对回撤的咨询增加",
  dry_run: true, seed: 42, variant: "auto",
};
const presets = [
  {label: "波动应对", segment: "steady-planner", objective: initialRequest.objective, signal: initialRequest.market_signal},
  {label: "沉默激活", segment: "growth-explorer", objective: "对沉默客群开展低负担教育触达", signal: "近期打开率下降，需要评估触达疲劳与渠道偏好"},
  {label: "多资产教育", segment: "pro-allocator", objective: "帮助专业客户理解多资产组合风险", signal: "股债相关性阶段性变化，海外市场波动上升"},
];

function pageFromHash(): Page {
  const value = location.hash.slice(1);
  return navigation.some((item) => item.id === value) ? value as Page : "overview";
}

export default function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [run, setRun] = useState<RunResult | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [request, setRequest] = useState(initialRequest);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [pollRevision, setPollRevision] = useState(0);
  const [provider, setProvider] = useState("正在连接…");
  const [ready, setReady] = useState(false);
  const submission = useRef<{payload: string; key: string} | null>(null);
  const submittingRef = useRef(false);
  const busy = submitting || job?.status === "queued" || job?.status === "running";
  const selected = navigation.find((item) => item.id === page)!;

  function navigate(next: Page) { location.hash = next; setPage(next); window.scrollTo(0, 0); }
  async function refresh() {
    const data = await api.dashboard();
    setDashboard(data);
    setRun((current) => current ?? data.recent_runs[0] ?? null);
  }
  useEffect(() => {
    let stopped = false;
    let retryTimer: number;
    const onHash = () => {setPage(pageFromHash()); window.scrollTo(0, 0);};
    window.addEventListener("hashchange", onHash);
    async function connect() {
      try {
        const [data, jobs, config] = await Promise.all([api.dashboard(), api.jobs(), api.configuration()]);
        if (stopped) return;
        setDashboard(data); setRun(data.recent_runs[0] ?? null);
        setProvider(String(config.provider)); setReady(true); setError("");
        setJob(jobs.find((item) => ["queued", "running"].includes(item.status)) ?? null);
      } catch {
        if (stopped) return;
        setProvider("等待服务连接");
        setError("暂时无法连接本地服务，正在自动重连。已保存的任务不会丢失。");
        retryTimer = window.setTimeout(connect, 3000);
      }
    }
    void connect();
    return () => {stopped = true; window.clearTimeout(retryTimer); window.removeEventListener("hashchange", onHash);};
  }, []);

  useEffect(() => {
    if (!job) return;
    let stopped = false;
    let timer: number;
    const poll = async () => {
      try {
        const status = await api.job(job.id);
        if (stopped) return;
        if (["completed", "blocked"].includes(status.status) && status.run_id) {
          const result = await api.getRun(status.run_id);
          if (stopped) return;
          const data = await api.dashboard();
          if (!stopped) { setRun(result); setDashboard(data); setJob(status); setError(""); }
          return;
        }
        setJob(status);
        if (["failed", "interrupted"].includes(status.status)) {
          setError(status.error ?? "任务失败，可在运行历史中重试"); return;
        }
        setError("");
      } catch {
        if (!stopped) setError("连接暂时中断，正在重新连接；任务已保存在服务端。");
      }
      if (!stopped) timer = window.setTimeout(poll, 800);
    };
    timer = window.setTimeout(poll, 150);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [job?.id, pollRevision]);

  async function submit() {
    if (busy || submittingRef.current) return;
    submittingRef.current = true; setSubmitting(true); setError("");
    const payload = JSON.stringify(request);
    if (submission.current?.payload !== payload) {
      submission.current = {payload, key: crypto.randomUUID()};
    }
    try {
      setJob(await api.submit(request, submission.current.key));
      submission.current = null;
    } catch (reason) { setError(message(reason)); }
    finally { setSubmitting(false); submittingRef.current = false; }
  }

  async function openRun(id: string) {
    try { setRun(await api.getRun(id)); navigate("overview"); }
    catch (reason) { setError(message(reason)); }
  }
  async function retry(id: string) {
    try { setJob(await api.retry(id)); setPollRevision((value) => value + 1); setError(""); navigate("overview"); }
    catch (reason) { setError(message(reason)); }
  }
  const events = busy ? job?.events ?? [] : run?.events ?? [];
  const metrics = dashboard?.metrics;

  return <div className="app-shell studio">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><span/><span/><span/></div><div><strong>FinLoop</strong><small>Decision Studio / 02</small></div></div>
      <nav aria-label="主导航" className="nav-list">
        <p className="nav-kicker">工作空间</p>
        {navigation.map((item) => <button key={item.id} className={`nav-item ${page === item.id ? "active" : ""}`}
          title={item.label} aria-label={item.label} aria-current={page === item.id ? "page" : undefined}
          onClick={() => navigate(item.id)}><Icon name={item.icon}/><span>{item.label}</span>{page === item.id && <i/>}</button>)}
      </nav>
      <div className="runtime-card"><div className="runtime-head"><span className="status-dot"/>本地研究空间</div>
        <strong>{!ready ? "正在连接服务" : provider.startsWith("deterministic") ? "本地模板运行" : "模型连接模式"}</strong>
        <p>模拟渠道 · 人工复核学习</p><div className="runtime-meta">{provider}</div></div>
      <div className="sidebar-user"><div className="avatar">FL</div><div><strong>金融营销决策工作台</strong><small>Local workspace · v0.2</small></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><div className="eyebrow"><span/> FINLOOP / {page.toUpperCase()}</div><h1>{selected.label}</h1><p className="page-description">{selected.description}</p></div>
        <div className="top-actions"><span className="mode-badge">模拟环境</span><a className="text-link" href="/docs" target="_blank" rel="noreferrer">API 文档 ↗</a></div></header>
      {error && <div className="error-banner" role="alert">{error}<button aria-label="关闭提示" onClick={() => setError("")}>×</button></div>}
      {page !== "overview" ? <StudioPages page={page} run={run} onOpenRun={openRun} onRetry={retry} onError={(error) => setError(message(error))}/>
      : <>
        <section className="metric-grid" aria-label="工作空间统计">
          <Metric label="已完成运行" value={String(metrics?.total_runs ?? "—")} detail="来自持久化运行记录"/>
          <Metric label="规则通过率" value={metrics?.total_runs ? formatPercent(metrics.compliance_rate, 0) : "—"} detail="含自动修订后通过"/>
          <Metric label="人工复核" value={String(metrics?.feedback_count ?? "—")} detail="只有人工反馈更新策略权重"/>
          <Metric label="长期记忆" value={String(metrics?.memory_count ?? "—")} detail="可查看来源、禁用与恢复"/>
        </section>
        <div className="workspace-grid">
          <section className="panel flow-panel">
            <div className="panel-heading"><div><div className="section-kicker">DECISION WORKFLOW</div><h2>{busy ? "任务正在运行" : "决策全流程"}</h2></div><span className="mode-badge">{busy ? job?.status === "queued" ? "排队中" : "处理中" : run ? shortId(run.run_id) : "准备就绪"}</span></div>
            <div className="pipeline">{stages.map((stage, index) => {
              const state = [...events].reverse().find((event) => event.stage === stage)?.status;
              return <div className="pipeline-wrap" key={stage}><div className={`pipeline-node ${state ?? "idle"}`}><div className="node-index">{state === "completed" || state === "revised" ? <Icon name="check"/> : index + 1}</div><strong>{stageNames[index]}</strong><small>{state === "started" ? "处理中" : state === "blocked" ? "已阻断" : state ? "已完成" : "等待"}</small></div>{index < 6 && <div className={`pipeline-link ${state ? "active" : ""}`}><span/></div>}</div>;
            })}</div>
            {busy ? <div className="progress-message" role="status"><span className="status-dot"/>{events.at(-1)?.message ?? "任务已持久化，正在分配执行资源…"}<small>可以切换页面；刷新后任务仍可找回。</small></div>
            : run ? <div className="flow-summary"><div className="signal-orb"><Icon name="spark"/></div><div className="flow-summary-copy"><span>{run.segment.name} · C{run.segment.risk_level}</span><strong>{run.selected_product?.name} · R{run.selected_product?.risk_level}</strong><p>{run.request.objective}</p></div></div>
            : <div className="workflow-empty"><h3>先定义目标，再检验证据</h3><p>从右侧选择一个场景。运行结束后，可以检查来源、比较策略并提交复核。</p></div>}
            <div className="feature-links"><button onClick={() => navigate("lab")}><Icon name="spark"/><span>同样本策略对比<small>控制模拟噪声，展示不确定性</small></span>↗</button><button onClick={() => navigate("evals")}><Icon name="shield"/><span>隔离质量评测<small>包含拒答与风险倒挂负例</small></span>↗</button></div>
          </section>
          <form className="panel control-panel" onSubmit={(event) => {event.preventDefault(); void submit();}}>
            <div className="panel-heading"><div><div className="section-kicker">NEW MISSION</div><h2>创建决策任务</h2></div></div>
            <div className="preset-list">{presets.map((preset) => <button type="button" key={preset.label} disabled={busy} onClick={() => setRequest({...request, segment_id: preset.segment, objective: preset.objective, market_signal: preset.signal})}>{preset.label}</button>)}</div>
            <label className="field-label" htmlFor="segment">目标客群</label><select id="segment" value={request.segment_id} disabled={busy} onChange={(event) => setRequest({...request, segment_id: event.target.value})}>{(dashboard?.segments ?? []).map((segment) => <option key={segment.id} value={segment.id}>{segment.name} · C{segment.risk_level} · {segment.preferred_channel.toUpperCase()}</option>)}</select>
            <label className="field-label" htmlFor="objective">业务目标</label><textarea id="objective" required minLength={4} maxLength={300} rows={2} value={request.objective} disabled={busy} onChange={(event) => setRequest({...request, objective: event.target.value})}/>
            <label className="field-label" htmlFor="signal">市场信号</label><textarea id="signal" required minLength={4} maxLength={500} rows={2} value={request.market_signal} disabled={busy} onChange={(event) => setRequest({...request, market_signal: event.target.value})}/>
            <details className="advanced"><summary>实验参数</summary><div className="form-row"><label>创意策略<select value={request.variant} onChange={(event) => setRequest({...request, variant: event.target.value})}><option value="auto">由复核权重选择</option><option value="clarity">清晰解释</option><option value="evidence">证据优先</option><option value="scenario">情景分析</option></select></label><label>随机种子<input type="number" min="0" max="2147483647" required value={request.seed} onChange={(event) => setRequest({...request, seed: Number(event.target.value)})}/></label></div></details>
            <button className="primary-button full" disabled={busy || !ready}><Icon name={busy ? "pulse" : "play"}/>{busy ? "任务处理中…" : "创建并运行"}<Icon name="arrow"/></button>
            <p className="safe-note">渠道数据为模拟值；同样的种子与参数得到相同样本。</p>
          </form>
        </div>
        {run ? <RunDetail key={run.run_id} run={run} onError={(error) => setError(message(error))} onReviewed={refresh}/>
          : <section className="panel empty-state"><Icon name="flow"/><h3>{ready ? "工作空间已就绪" : "正在连接工作空间"}</h3><p>完成首次任务后，这里将展示内容、证据、执行漏斗与复核入口。</p></section>}
      </>}
      <footer><span>FinLoop AI · 虚构产品与匿名模拟客群</span><span>证据快照 / 可复现实验 / 人工复核</span></footer>
    </main>
  </div>;
}

export function message(error: unknown) { return error instanceof Error ? error.message : "操作失败，请重试"; }
function Metric({label, value, detail}: {label: string; value: string; detail: string}) {
  return <article className="metric-card"><div className="metric-top">{label}</div><strong>{value}</strong><p>{detail}</p></article>;
}
