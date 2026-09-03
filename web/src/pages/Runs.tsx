import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type CaseResult, type Dataset, type Run, type Version } from "../api";

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
    if (!vid && all[0]) setVid(all[0].id);
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
      <h1>Runs</h1>
      <div className="card">
        <h2>rag_version</h2>
        <div className="grid">
          {Object.entries(rv).map(([k, v]) => (
            <label key={k}>
              {k}
              <input value={v} onChange={(e) => setRv({ ...rv, [k]: e.target.value })} />
            </label>
          ))}
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <label>
            dataset version
            <select value={vid} onChange={(e) => setVid(e.target.value)}>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version} {v.confirmed_at ? "confirmed" : "draft"} ({v.case_count})
                </option>
              ))}
            </select>
          </label>
          <label>
            use_as_gate
            <select value={gate ? "1" : "0"} onChange={(e) => setGate(e.target.value === "1")}>
              <option value="0">false</option>
              <option value="1">true</option>
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
                setMsg(`Start 已提交 ${run.id} status=${run.status}`);
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
      {runs.map((r) => (
        <div className="card" key={r.id}>
          <div className="row">
            <strong>{r.id.slice(0, 8)}</strong>
            <span className="chip">{r.status}</span>
            <span>
              进度 {r.done}/{r.total} pass={r.pass_count}
            </span>
            <Link to={`/projects/${id}/report?run=${r.id}`}>报告</Link>
            <button className="ghost" onClick={() => openFails(r)}>
              fail 列表
            </button>
            {(r.status === "PENDING" || r.status === "RUNNING") && (
              <button className="secondary" onClick={() => api.cancelRun(r.id).then(load)}>
                Cancel
              </button>
            )}
          </div>
          <div className="progress">
            <div style={{ width: `${r.total ? (100 * r.done) / r.total : 0}%` }} />
          </div>
        </div>
      ))}
      {selected && (
        <div className="card">
          <h2>fail 列表 · {selected.id.slice(0, 8)}</h2>
          <table>
            <thead>
              <tr>
                <th>case</th>
                <th>behavior</th>
                <th>cause</th>
                <th>answer</th>
              </tr>
            </thead>
            <tbody>
              {fails.map((c) => (
                <tr key={c.case_id}>
                  <td>{c.case_id}</td>
                  <td>{c.evaluated_behavior}</td>
                  <td>{c.primary_cause}</td>
                  <td>{c.actual_answer}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
