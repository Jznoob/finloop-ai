import { useEffect, useState } from "react";
import type { Page } from "../App";
import { api } from "../lib/api";
import { formatPercent, shortId } from "../lib/format";
import type { Citation, Document, Evaluation, Experiment, Job, Memory, Report, RunResult } from "../types";
import { DocumentDialog } from "./RunDetail";

type Props = {page: Page; run: RunResult | null; onOpenRun: (id: string) => void; onRetry: (id: string) => void; onError: (error: unknown) => void};
const variantLabels: Record<string,string> = {clarity: "清晰解释", evidence: "证据优先", scenario: "情景分析"};
const statusLabels: Record<string,string> = {queued: "排队中", running: "运行中", completed: "已完成", blocked: "已阻断", failed: "失败", interrupted: "已中断"};
const date = (value: string) => new Date(value).toLocaleString("zh-CN", {hour12: false});

export function StudioPages(props: Props) {
  switch (props.page) {
    case "lab": return <Laboratory {...props}/>;
    case "knowledge": return <Knowledge onError={props.onError}/>;
    case "memory": return <Memories onError={props.onError}/>;
    case "evals": return <Evaluations onError={props.onError}/>;
    case "history": return <History {...props}/>;
    case "settings": return <Configuration onError={props.onError}/>;
    default: return null;
  }
}

function Laboratory({run, onError}: Props) {
  const [runs, setRuns] = useState<RunResult[]>([]);
  const [sourceId, setSourceId] = useState(run?.run_id ?? "");
  const [seed, setSeed] = useState(42);
  const [sampleSize, setSampleSize] = useState(1200);
  const [stress, setStress] = useState(.5);
  const [fatigue, setFatigue] = useState(.2);
  const [result, setResult] = useState<Experiment | null>(null);
  const [reports, setReports] = useState<Report<Experiment>[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    Promise.all([api.runs(), api.experiments()]).then(([items, history]) => {
      setRuns(items.filter((item) => item.execution)); setReports(history);
      setSourceId((current) => current || items.find((item) => item.execution)?.run_id || "");
    }).catch(onError);
  }, []);
  async function compare() {
    setBusy(true);
    try {
      setResult(await api.experiment({run_id: sourceId, seed, sample_size: sampleSize, stress, fatigue}));
      setReports(await api.experiments());
    } catch (error) {onError(error);} finally {setBusy(false);}
  }
  const scale = result ? Math.max(.05, ...result.variants.map((row) => row.interval95[1] * 1.2)) : .05;
  return <div className="lab-layout">
    <form className="panel page-card lab-controls" onSubmit={(event) => {event.preventDefault(); void compare();}}>
      <div className="section-kicker">COUNTERFACTUAL SANDBOX</div><h2>如果换一种策略，会怎样？</h2><p className="subtle">固定虚拟样本，只改变策略与假设。实验不会写入客群记忆或策略权重。</p>
      <label className="field-label" htmlFor="source-run">基线运行</label><select id="source-run" required value={sourceId} onChange={(event) => setSourceId(event.target.value)}><option value="">请选择已完成的运行</option>{runs.map((item) => <option key={item.run_id} value={item.run_id}>{shortId(item.run_id)} · {item.segment.name}</option>)}</select>
      <div className="form-row"><label>样本人数<input aria-label="样本人数" type="number" min={200} max={5000} required value={sampleSize} onChange={(event) => setSampleSize(Number(event.target.value))}/></label><label>随机种子<input aria-label="实验随机种子" type="number" min={0} max={2147483647} required value={seed} onChange={(event) => setSeed(Number(event.target.value))}/></label></div>
      <label className="slider-label" htmlFor="stress">市场压力假设 <b>{formatPercent(stress, 0)}</b></label><input id="stress" type="range" min={0} max={1} step={.05} value={stress} onChange={(event) => setStress(Number(event.target.value))}/><p className="subtle">压力升高时，模拟器假定情景分析的响应概率上升。</p>
      <label className="slider-label" htmlFor="fatigue">触达疲劳假设 <b>{formatPercent(fatigue, 0)}</b></label><input id="fatigue" type="range" min={0} max={1} step={.05} value={fatigue} onChange={(event) => setFatigue(Number(event.target.value))}/><p className="subtle">疲劳同时降低打开与响应概率。</p>
      <button className="primary-button full" disabled={busy || !sourceId}>{busy ? "正在比较…" : "运行同样本对比 →"}</button>
      {!sourceId && <p className="subtle">先在工作台完成一轮任务，再选择实验基线。</p>}
    </form>
    <div><section className="panel page-card lab-result"><div className="panel-heading"><div><div className="section-kicker">PAIRED COHORT COMPARISON</div><h2>策略差异与不确定性</h2></div><span className="mode-badge">合成实验</span></div>
      {!result ? <div className="empty-state"><h3>让差异有可比较的基线</h3><p>同一组送达、打开与响应随机数，分别计算三种策略结果。区间跨过 0 时会提示差异证据不足。</p></div> : <>
        <div className="experiment-caption">最近结果 · {result.request.sample_size} 人 · seed {result.request.seed} · 压力 {formatPercent(result.request.stress,0)} · 疲劳 {formatPercent(result.request.fatigue,0)}</div>
        <div className="interval-chart" aria-label="三种策略转化率与95%区间">{result.variants.map((row) => <div className="interval-row" key={row.variant}><span>{variantLabels[row.variant]}</span><div className="interval-track"><i style={{left: `${row.interval95[0]/scale*100}%`, width: `${(row.interval95[1]-row.interval95[0])/scale*100}%`}}/><b style={{left: `${row.audience_conversion_rate/scale*100}%`}}/></div><strong>{formatPercent(row.audience_conversion_rate,2)}</strong></div>)}<div className="chart-caption">● 点估计　— 95% Wilson 区间；分母为全部入组人数</div></div>
        <div className="table-scroll"><table><thead><tr><th>策略</th><th>转化 / 入组</th><th>较清晰解释</th><th>配对差异 95% 区间</th></tr></thead><tbody>{result.variants.map((row) => <tr key={row.variant}><td><b>{variantLabels[row.variant]}</b><small>{row.conclusion}</small></td><td>{row.converted} / {result.request.sample_size}</td><td>{(row.difference_vs_clarity*100).toFixed(2)} pp</td><td>{(row.paired_interval95[0]*100).toFixed(2)} ~ {(row.paired_interval95[1]*100).toFixed(2)} pp</td></tr>)}</tbody></table></div>
        <p className="method-note">{result.notice}</p><details className="technical-details"><summary>展开模拟假设与计算方法</summary><p>{result.method}</p><pre>{JSON.stringify(result.assumptions,null,2)}</pre></details>
      </>}
    </section><section className="panel page-card saved-experiments"><h3>已保存实验</h3>{reports.length ? <div className="saved-list">{reports.slice(0,6).map((report) => <button key={report.id} onClick={() => setResult(report.payload)}><span>{report.payload.request.sample_size} 人 · seed {report.payload.request.seed}</span><small>{date(report.created_at)} ↗</small></button>)}</div> : <p className="subtle">运行后会自动保存输入、假设和完整结果。</p>}</section></div>
  </div>;
}

function Knowledge({onError}: {onError: Props["onError"]}) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Citation[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState<Document | null>(null);
  useEffect(() => {api.knowledge().then(setDocuments).catch(onError);}, []);
  async function search() {
    if (query.trim().length < 2) {setResults(null); return;}
    setBusy(true);
    try {setResults((await api.search(query.trim())).results);} catch (error) {onError(error);} finally {setBusy(false);}
  }
  return <section className="panel page-card"><div className="section-intro"><h2>可检索、可引用的制度与知识</h2><p>{documents.length} 篇演示文档 · 段落级 BM25 · 无相关词项时返回空结果</p></div>
    <form className="search-form" onSubmit={(event) => {event.preventDefault(); void search();}}><input aria-label="知识检索" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="例如：风险等级倒挂、触达疲劳、身份证号脱敏" maxLength={300}/><button className="primary-button compact" disabled={busy}>{busy ? "检索中…" : "检索证据"}</button><button className="secondary-button" type="button" onClick={() => {setQuery(""); setResults(null);}}>全部文档</button></form>
    {results && <div className="search-results"><h3>命中 {results.length} 篇文档</h3>{results.length === 0 ? <p className="empty-copy">没有相关依据。尝试更具体的关键词，或查看全部文档。</p> : results.map((citation) => <button key={citation.document_id} onClick={() => setSource(documents.find((doc) => doc.id === citation.document_id) ?? null)}><span className="section-kicker">{citation.document_id} · 排序分 {citation.score.toFixed(3)}（非置信度）</span><h3>{citation.title}</h3><p>{citation.excerpt}</p></button>)}</div>}
    {!results && <div className="knowledge-grid">{documents.map((doc) => <button className="source-card" key={doc.id} onClick={() => setSource(doc)}><span>{doc.id}<b>{doc.category}</b></span><h3>{doc.title}</h3><p>{doc.content.slice(0,105)}…</p><small>生效 {doc.effective_date} · 查看全文 ↗</small></button>)}</div>}
    <DocumentDialog document={source} onClose={() => setSource(null)}/>
  </section>;
}

function Memories({onError}: {onError: Props["onError"]}) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {api.memories().then(setMemories).catch(onError).finally(() => setLoading(false));}, []);
  async function toggle(memory: Memory) {
    setBusy(memory.id);
    try {await api.memoryState(memory.id, !memory.active); setMemories(await api.memories());}
    catch (error) {onError(error);} finally {setBusy(null);}
  }
  const items = memories.filter((memory) => filter === "all" || memory.kind === filter);
  return <section className="panel page-card"><div className="section-intro"><h2>让经验可检查，也可撤回</h2><p>同内容的旧版记录分组展示、统一禁用，不删除历史。新任务按内容去重召回，历史证据保留原始记忆 ID。</p></div>
    <div className="filter-row">{[["all","全部"],["episodic","情景记录"],["semantic","客群知识"],["procedural","固定流程"]].map(([id,label]) => <button key={id} className={filter === id ? "selected" : ""} onClick={() => setFilter(id)}>{label}</button>)}</div>
    <div className="memory-list">{items.map((memory) => <article key={memory.id} className={!memory.active ? "disabled-memory" : ""}><div className="memory-header"><span className="mode-badge">{memory.kind}</span><small>{memory.namespace} · {String(memory.metadata.origin ?? memory.metadata.source ?? "旧版记录")}</small><button className="secondary-button" disabled={busy !== null} onClick={() => toggle(memory)}>{busy === memory.id ? "保存中…" : memory.active ? "禁用" : "恢复"}</button></div><p>{memory.content}</p>{memory.duplicate_count > 1 && <p className="subtle">已折叠 {memory.duplicate_count} 条同内容记录；禁用或恢复会应用于整组。</p>}<div className="memory-footer"><code>{memory.id}</code><span>{date(memory.created_at)}</span></div></article>)}</div>
    {loading ? <p className="empty-copy" role="status">正在读取记忆…</p> : items.length === 0 && <p className="empty-copy">暂无该类型记忆。完成任务后可在这里查看。</p>}
  </section>;
}

function Evaluations({onError}: {onError: Props["onError"]}) {
  const [report, setReport] = useState<Evaluation | null>(null);
  const [history, setHistory] = useState<Report<Evaluation>[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {api.evaluations().then((items) => {setHistory(items); setReport(items[0]?.payload ?? null);}).catch(onError);}, []);
  async function evaluate() {
    setBusy(true);
    try {setReport(await api.evaluate()); setHistory(await api.evaluations());}
    catch (error) {onError(error);} finally {setBusy(false);}
  }
  return <section className="panel page-card"><div className="panel-heading"><div className="section-intro"><h2>可复现的质量回归</h2><p>使用临时数据库和本地模板。评测不会新增业务运行、长期记忆或策略权重。</p></div><button className="primary-button compact" onClick={evaluate} disabled={busy}>{busy ? "评测中…" : "运行评测"}</button></div>
    {history.length > 0 && <label className="report-selector">报告<select value={report?.id ?? ""} onChange={(event) => setReport(history.find((item) => item.id === event.target.value)?.payload ?? null)}>{history.map((item) => <option key={item.id} value={item.id}>{date(item.created_at)} · {item.payload.passed}/{item.payload.total}</option>)}</select></label>}
    {!report ? <div className="empty-state"><h3>验证正常路径，也验证失败边界</h3><p>包括无关查询、伪造引用、产品风险倒挂、禁用词修订与脱敏预算。</p></div> : <>
      <div className="score-grid">{[["回归通过",`${report.passed} / ${report.total}`],["Recall@2", formatPercent(report.retrieval_metrics.recall_at_2)],["Precision@2", formatPercent(report.retrieval_metrics.precision_at_2)],["MRR@2", report.retrieval_metrics.mrr_at_2.toFixed(3)]].map(([label,value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <p className="method-note">{report.scope} 检索指标只使用有相关文档的查询，固定截取前 2 条；无关查询单独检查是否拒答。语料：{report.corpus_documents} 篇。</p>
      <div className="table-scroll"><table><thead><tr><th>测试用例</th><th>类别</th><th>结果</th><th>验证内容</th></tr></thead><tbody>{report.cases.map((item) => <tr key={item.case_id}><td><code>{item.case_id}</code></td><td>{item.category}</td><td><span className={`status-badge ${item.passed ? "approved" : "blocked"}`}>{item.passed ? "通过" : "失败"}</span></td><td>{item.detail}</td></tr>)}</tbody></table></div>
    </>}
  </section>;
}

function History({onOpenRun, onRetry, onError}: Props) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runs, setRuns] = useState<RunResult[]>([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [inspection, setInspection] = useState<Job | null>(null);
  async function inspect(id: string) {
    try {setInspection(await api.job(id));} catch (error) {onError(error);}
  }
  async function load() {
    setBusy(true);
    try {const [tasks, results] = await Promise.all([api.jobs(), api.runs()]); setJobs(tasks); setRuns(results);}
    catch (error) {onError(error);} finally {setBusy(false);}
  }
  useEffect(() => {void load();}, []);
  const shown = runs.filter((item) => `${item.run_id} ${item.request.objective} ${item.segment.name}`.includes(query));
  return <div><section className="panel page-card"><div className="panel-heading"><div className="section-intro"><h2>任务队列与恢复</h2><p>网络重传按幂等键去重。重试保留原输入与旧轨迹，重新执行完整流程。</p></div><button className="secondary-button" onClick={load} disabled={busy}>{busy ? "刷新中…" : "刷新列表"}</button></div>
    <div className="table-scroll"><table><thead><tr><th>任务 / 目标</th><th>创建时间</th><th>状态</th><th>尝试</th><th>操作</th></tr></thead><tbody>{jobs.map((job) => <tr key={job.id}><td><b>{job.request.objective}</b><small>{job.id}</small>{job.error && ["failed","interrupted"].includes(job.status) && <small>{job.error}</small>}</td><td>{date(job.created_at)}</td><td><span className={`status-badge ${job.status}`}>{statusLabels[job.status]}</span></td><td><button className="secondary-button" onClick={() => inspect(job.id)} aria-label={`查看 ${job.id} 的尝试记录`}>{job.attempts} 次 ↗</button></td><td>{["failed","interrupted"].includes(job.status) ? <button className="secondary-button" onClick={() => onRetry(job.id)}>重新运行</button> : job.run_id && ["completed","blocked"].includes(job.status) ? <button className="secondary-button" onClick={() => onOpenRun(job.run_id!)}>查看结果</button> : "—"}</td></tr>)}</tbody></table></div>{!jobs.length && <p className="empty-copy">还没有后台任务，新建运行后会显示在这里。</p>}
    {inspection && <div className="technical-details"><div className="panel-heading"><h3>历次尝试 · {inspection.id}</h3><button className="secondary-button" onClick={() => setInspection(null)}>关闭记录</button></div>{inspection.history?.length ? inspection.history.map((attempt) => <details key={attempt.run_id}><summary>第 {attempt.attempt} 次 · {statusLabels[attempt.status] ?? attempt.status} · {attempt.run_id} · {date(attempt.created_at)}</summary><ol>{attempt.events.map((event) => <li key={event.sequence}><b>{event.stage} / {event.status}</b> — {event.message}</li>)}</ol>{!attempt.events.length && <p>尚未写入阶段事件。</p>}</details>) : <p>此任务尚无尝试日志，或创建于旧版本。已有最终结果仍可查阅。</p>}</div>}
  </section><section className="panel page-card saved-experiments"><h2>已保存的运行结果</h2><input aria-label="搜索运行历史" placeholder="搜索目标、客群或运行编号" value={query} onChange={(event) => setQuery(event.target.value)}/><div className="saved-list">{shown.map((item) => <button key={item.run_id} onClick={() => onOpenRun(item.run_id)}><span><b>{item.segment.name}</b> · {item.request.objective}<small>{shortId(item.run_id)} · {date(item.created_at)}</small></span><span>查看 ↗</span></button>)}</div>{!shown.length && <p className="empty-copy">没有匹配的运行记录。</p>}</section></div>;
}

function Configuration({onError}: {onError: Props["onError"]}) {
  const [config, setConfig] = useState<Record<string,string|number|boolean>>({});
  useEffect(() => {api.configuration().then(setConfig).catch(onError);}, []);
  const labels: Record<string,string> = {provider:"当前提供方",key_configured:"已配置服务端密钥",context_budget:"上下文估算预算",execution:"渠道执行",runtime:"执行器",retry:"失败恢复",retrieval:"检索方式",learning:"策略学习",token_estimator:"预算口径"};
  return <section className="panel page-card"><div className="section-intro"><h2>当前运行能力</h2><p>这里展示服务端实际配置。模型密钥只在服务端环境文件中配置，不会返回浏览器。</p></div><dl className="config-list">{Object.entries(config).map(([key,value]) => <div key={key}><dt>{labels[key] ?? key}</dt><dd>{typeof value === "boolean" ? value ? "是" : "否" : String(value)}</dd></div>)}</dl><div className="method-note">本地模板模式可验证工作流、规则、存储与实验；真实模型的生成质量需要配置服务端接口后单独评估。</div><a className="secondary-button" href="/docs" target="_blank" rel="noreferrer">查看 API 接口 ↗</a></section>;
}
