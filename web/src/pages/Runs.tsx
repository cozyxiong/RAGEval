import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type CaseResult, type Dataset, type Run, type Version } from "../api";
import { CAUSE_LABEL, RV_LABEL, STATUS_LABEL, pct, shortId } from "../copy";
import { PageHead } from "../Layout";

const EMPTY_RV = {
  kb: "mock-kb",
  chunk: "naive",
  embedding: "mock-embed",
  retrieval: "keyword",
  rerank: "none",
  generator: "mock-generator",
  prompt: "closed-v1",
};

export default function RunsPage() {
  const { id } = useParams();
  const [runs, setRuns] = useState<Run[]>([]);
  const [rv, setRv] = useState({ ...EMPTY_RV });
  const [vid, setVid] = useState("");
  const [versions, setVersions] = useState<Version[]>([]);
  const [selected, setSelected] = useState<Run | null>(null);
  const [fails, setFails] = useState<CaseResult[]>([]);
  const [msg, setMsg] = useState("");
  const [gate, setGate] = useState(false);

  async function load() {
    if (!id) return;
    const rs = await api.listRuns(id);
    setRuns(rs);
    const dss: Dataset[] = await api.listDatasets(id);
    const all: Version[] = [];
    for (const d of dss) {
      all.push(...(await api.listVersions(d.id)));
    }
    setVersions(all);
    const confirmed = all.find((v) => v.confirmed_at) || all[0];
    if (!vid && confirmed) setVid(confirmed.id);
  }
  useEffect(() => {
    load().catch((e) => setMsg(String(e)));
  }, [id]);
  useEffect(() => {
    const running = runs.find((r) => r.status === "RUNNING" || r.status === "PENDING");
    if (!running) return;
    const t = setInterval(async () => {
      const fresh = await api.getRun(running.id);
      setRuns((rs) => rs.map((r) => (r.id === fresh.id ? fresh : r)));
    }, 1000);
    return () => clearInterval(t);
  }, [runs]);

  async function openFails(run: Run) {
    setSelected(run);
    const cases = await api.runCases(run.id);
    setFails(cases.filter((c) => c.judge_label === "fail"));
  }

  return (
    <div>
      <PageHead
        kicker="③ 开始评测"
        title="提交后，后台会一题一题去问"
        lead="每次只改一个变量（比如提示词或检索），才能判断「到底是哪一处改好了还是改坏了」。点 Start 排队，不要在网页里同步跑全集。"
      />
      <div className="card">
        <h2>这一轮改了什么 · rag_version</h2>
        <p className="hint">只填你真正动过的那一格，其余保持和上次一样。</p>
        <div className="grid">
          {Object.entries(rv).map(([k, v]) => (
            <label key={k}>
              {RV_LABEL[k] || k}
              <input value={v} onChange={(e) => setRv({ ...rv, [k]: e.target.value })} />
            </label>
          ))}
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <label>
            用哪套已锁定的题
            <select value={vid} onChange={(e) => setVid(e.target.value)}>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  第 {v.version} 版 {v.confirmed_at ? "已 Confirm" : "草稿不可考"} · {v.case_count} 题
                </option>
              ))}
            </select>
          </label>
          <label>
            未校准不许当门槛
            <select value={gate ? "1" : "0"} onChange={(e) => setGate(e.target.value === "1")}>
              <option value="0">先跑着看（推荐）</option>
              <option value="1">use_as_gate = 必须已校准</option>
            </select>
          </label>
          <button
            onClick={async () => {
              if (!id) return;
              try {
                const run = await api.createRun(id, {
                  dataset_version_id: vid,
                  rag_version: rv,
                  use_as_gate: gate,
                });
                setMsg(`Start 已提交 ${run.id.slice(0, 8)}，正在排队。`);
                await load();
              } catch (e) {
                setMsg(String(e));
              }
            }}
          >
            Start
          </button>
        </div>
      </div>
      {runs.map((r) => {
        const rate = r.total ? r.pass_count / r.total : 0;
        return (
          <div className="card" key={r.id}>
            <div className="row">
              <strong>{shortId(r.id)}</strong>
              <span className="chip">{STATUS_LABEL[r.status] || r.status}</span>
              <span>
                进度 {r.done}/{r.total} · 过关 {r.pass_count} 题（{pct(rate)}）
              </span>
              <Link to={`/projects/${id}/report?run=${r.id}`}>看成绩</Link>
              <button className="ghost" onClick={() => openFails(r)}>
                fail 列表
              </button>
              {(r.status === "PENDING" || r.status === "RUNNING") && (
                <button className="secondary" onClick={() => api.cancelRun(r.id).then(load)}>
                  停掉
                </button>
              )}
            </div>
            <div className="progress">
              <div style={{ width: `${r.total ? (100 * r.done) / r.total : 0}%` }} />
            </div>
            <p className="hint">提示词 {r.rag_version?.prompt || "—"} · 检索 {r.rag_version?.retrieval || "—"}</p>
          </div>
        );
      })}
      {selected && (
        <div className="card">
          <h2>没过关的题 · fail 列表</h2>
          <table>
            <thead>
              <tr>
                <th>题号</th>
                <th>系统实际表现</th>
                <th>主要原因</th>
                <th>它怎么答的</th>
              </tr>
            </thead>
            <tbody>
              {fails.map((c) => (
                <tr key={c.case_id}>
                  <td>{c.case_id}</td>
                  <td>{c.evaluated_behavior}</td>
                  <td>{CAUSE_LABEL[c.primary_cause || ""] || c.primary_cause}</td>
                  <td>{(c.actual_answer || "").slice(0, 160)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {msg && <p className={msg.startsWith("Start") ? "muted" : "err"}>{msg}</p>}
    </div>
  );
}
