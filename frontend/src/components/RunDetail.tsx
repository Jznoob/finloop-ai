import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { formatPercent } from "../lib/format";
import type { Document, Passport, RunResult } from "../types";
import { Icon } from "./Icon";

export function DocumentDialog({document, onClose}: {document: Document | null; onClose: () => void}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { if (document) dialog.current?.showModal(); }, [document]);
  if (!document) return null;
  return <dialog ref={dialog} onCancel={onClose} onClose={onClose} className="document-dialog" aria-labelledby="document-title">
    <div className="dialog-top"><span className="section-kicker">SOURCE / {document.id}</span><button className="secondary-button" onClick={onClose} aria-label="关闭文档">关闭 ×</button></div>
    <h2 id="document-title">{document.title}</h2><p>{document.source} · 生效 {document.effective_date}</p>
    <div className="document-content">{document.content}</div><details><summary>文档版本指纹</summary><code>{document.content_hash}</code></details>
  </dialog>;
}

export function RunDetail({run, onError, onReviewed}: {run: RunResult; onError: (error: unknown) => void; onReviewed: () => Promise<void>}) {
  const [tab, setTab] = useState("content");
  const [passport, setPassport] = useState<Passport | null>(null);
  const [source, setSource] = useState<Document | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [reviewReady, setReviewReady] = useState(false);
  const [pending, setPending] = useState(false);
  const [note, setNote] = useState("");
  const [rating, setRating] = useState(4);
  const [endorse, setEndorse] = useState(true);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    let active = true;
    Promise.all([api.evidence(run.run_id), api.review(run.run_id)]).then(([evidence, review]) => {
      if (!active) return;
      setPassport(evidence); setReviewed(Boolean(review)); setReviewReady(true);
      if (review) { setNote(review.note); setRating(review.rating); setEndorse(Boolean(review.endorsed)); }
    }).catch(onError);
    return () => {active = false;};
  }, [run.run_id]);
  async function review() {
    setPending(true);
    try {
      await api.feedback({run_id: run.run_id, converted: endorse, rating, note});
      setReviewed(true); await onReviewed();
    } catch (error) {onError(error);} finally {setPending(false);}
  }
  async function copy() {
    try {await navigator.clipboard.writeText(run.compliance.final_copy); setCopied(true);}
    catch {onError(new Error("浏览器未允许复制，可直接选择文案文本复制。"));}
  }
  const execution = run.execution;
  return <section className="panel result-panel">
    <div className="result-tabs"><div role="tablist" aria-label="运行详情">{[
      ["content", "内容与复核"], ["evidence", "证据护照"], ["trace", "运行轨迹"],
    ].map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}</div>
      <a className="secondary-button" href={`/api/runs/${run.run_id}/export`} download>导出运行 JSON ↓</a></div>
    {tab === "content" ? <div className="result-grid">
      <article className="content-preview"><div className="card-title"><div><span>FINAL COPY</span><h3>渠道内容</h3></div><button onClick={copy}><Icon name={copied ? "check" : "copy"}/>{copied ? "已复制" : "复制"}</button></div>
        <div className="channel-line"><span>{run.segment.preferred_channel.toUpperCase()}</span>{run.segment.name} · {run.execution?.variant ?? "未执行"}</div>
        <div className="copy-body">{run.compliance.final_copy}</div>
        {execution && <div className="funnel" aria-label="模拟执行漏斗">{[["样本", execution.audience_size], ["送达", execution.delivered], ["打开", execution.opened], ["转化", execution.converted]].map(([label, value]) => <div key={label}><small>{label}</small><strong>{Number(value).toLocaleString()}</strong></div>)}</div>}
        <p className="subtle">以上为模拟漏斗，转化率分母为送达人数。不会自动更新策略权重。</p>
      </article>
      <div className="evidence-column">
        <article className="compliance-card"><div className="card-title"><h3>规则检查</h3><span className={`status-badge ${run.compliance.status}`}>{run.compliance.status === "approved" ? "通过" : run.compliance.status === "revised" ? "修订后通过" : "已阻断"}</span></div>
          <div className="check-list">{run.compliance.checks.map((check) => <div key={check.rule}><span className={check.passed ? "pass" : "fail"}><Icon name={check.passed ? "check" : "shield"}/></span><p><strong>{check.rule}</strong><small>{check.detail}</small></p></div>)}</div>
          {run.compliance.violations.length > 0 && <p className="subtle">原稿问题：{run.compliance.violations.join("；")}</p>}
        </article>
        <form className="review-card" onSubmit={(event) => {event.preventDefault(); void review();}}>
          <div className="card-title"><h3>人工质量复核</h3><span className="mode-badge">{reviewed ? "已提交" : "待复核"}</span></div>
          <p className="subtle">复核用于创意偏好权重，不作为真实客户转化数据。</p>
          <div className="form-row"><label>质量评分<select disabled={reviewed || pending} value={rating} onChange={(event) => setRating(Number(event.target.value))}>{[1,2,3,4,5].map((value) => <option key={value} value={value}>{value} / 5</option>)}</select></label><label>策略判断<select disabled={reviewed || pending} value={endorse ? "yes" : "no"} onChange={(event) => setEndorse(event.target.value === "yes")}><option value="yes">认可该策略</option><option value="no">不认可该策略</option></select></label></div>
          <label className="field-label" htmlFor="review-note">复核备注</label><textarea id="review-note" maxLength={500} rows={2} disabled={reviewed || pending} value={note} onChange={(event) => setNote(event.target.value)} placeholder="例如：解释清晰，但应进一步说明持有期限"/>
          <button className="secondary-button wide" disabled={reviewed || pending || !reviewReady || !execution}>{reviewed ? "复核已保存 · 重复提交已锁定" : pending ? "提交中…" : "提交复核"}</button>
        </form>
      </div>
    </div> : tab === "evidence" ? <div className="passport-view">
      <div className="section-intro"><h3>这次决策使用了哪些依据？</h3><p>保存运行时原文与 SHA-256 指纹。当前文档更新后，仍可查阅当时版本。</p></div>
      {!passport?.sources?.length ? <p className="empty-copy">此历史记录来自旧版本，未保存证据快照。新建任务即可生成。</p> : <>
        <div className="passport-meta"><span>规则版本 <b>{passport.policy_version}</b></span><span>随机种子 <b>{passport.seed}</b></span><span>召回记忆 <b>{passport.memory_ids.length}</b></span></div>
        <div className="source-grid">{passport.sources.map((doc) => {
          const match = passport.verification?.find((item) => item.id === doc.id);
          const cite = run.citations.find((item) => item.document_id === doc.id);
          return <button key={doc.id} className="source-card" onClick={() => setSource(doc)}><span>{doc.id} <b>{match?.snapshot_integrity ? "快照完整" : "未核验"}</b></span><h4>{doc.title}</h4><p>{doc.source}</p><small>{cite?.retrieval_reason === "mandatory-policy" ? "制度强制载入" : "查询检索命中"} · {match?.current_matches ? "与当前版本一致" : "当前版本已变化"}</small><code>{doc.content_hash.slice(0,20)}…</code></button>;
        })}</div><p className="subtle">{passport.boundaries}</p>
        <details className="technical-details"><summary>上下文预算与版本记录</summary><p>{run.context_trace.estimated_tokens} / {run.context_trace.budget} 估算 tokens · 上下文组装时额外脱敏 {run.context_trace.redactions} 次（输入已在持久化前脱敏）</p><p>纳入：{run.context_trace.included_sections.join(" / ")}</p><p>丢弃：{run.context_trace.dropped_sections.join(" / ") || "无"}</p><code>input {passport.input_sha256}<br/>context {passport.context_sha256}</code></details>
      </>}
    </div> : <div className="trace-view"><div className="section-intro"><h3>执行事件与模型状态</h3><p>展示实际保存的阶段事件。模型降级会明确记录。</p></div>
      <div className="model-calls">{run.model_calls?.map((call, index) => <span key={index}>调用 {index+1} · {call.outcome} · {call.latency_ms}ms</span>)}</div>
      <div className="timeline">{run.events.map((event) => <div className="timeline-row" key={event.sequence}><div className="timeline-seq">{String(event.sequence).padStart(2,"0")}</div><div className={`timeline-dot ${event.status}`}/><div className="timeline-body"><div><strong>{event.agent}</strong><span>{event.status}</span><time>{new Date(event.timestamp).toLocaleTimeString("zh-CN", {hour12: false})}</time></div><p>{event.message}</p>{Object.keys(event.payload).length > 0 && <details><summary>结构化数据</summary><pre>{JSON.stringify(event.payload,null,2)}</pre></details>}</div></div>)}</div>
      <p className="subtle">模拟转化率 {execution ? formatPercent(execution.conversion_rate) : "—"} · 仅用于检查闭环行为</p>
    </div>}
    <DocumentDialog document={source} onClose={() => setSource(null)}/>
  </section>;
}
