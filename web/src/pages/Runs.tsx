import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type CaseResult, type Run } from "../api";
import { CAUSE_LABEL, STATUS_LABEL, pct, shortId } from "../copy";
import { PageHead } from "../Layout";

export default function RunsPage() {
  const { id } = useParams();
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<Run | null>(null);
  const [fails, setFails] = useState<CaseResult[]>([]);
  const [msg, setMsg] = useState("");

  async function load() {
    if (!id) return;
    setRuns(await api.listRuns(id));
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
        kicker="历史"
        title="以往评测"
        lead="这里是已经提交过的轮次。要再考一轮，去新建评测，只改一个变量后点 Start。"
      />
      <div className="row" style={{ marginBottom: 16 }}>
        <Link to={`/projects/${id}/runs/new`}>
          <button>Start 新一轮</button>
        </Link>
      </div>
      {runs.length === 0 && (
        <div className="card">
          <p className="hint">还没有评测历史。</p>
        </div>
      )}
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
      {msg && <p className="err">{msg}</p>}
    </div>
  );
}
