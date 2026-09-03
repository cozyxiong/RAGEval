import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, type Diff, type Report, type Run } from "../api";

export default function ReportPage() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState(params.get("run") || "");
  const [other, setOther] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [diff, setDiff] = useState<Diff | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!id) return;
    api.listRuns(id).then((rs) => {
      setRuns(rs);
      if (!runId && rs[0]) setRunId(rs[0].id);
    });
  }, [id]);

  useEffect(() => {
    if (!runId) return;
    api.report(runId).then(setReport).catch((e) => setMsg(String(e)));
  }, [runId]);

  const slices = useMemo(() => Object.entries(report?.slices || {}), [report]);

  return (
    <div>
      <h1>报告</h1>
      <div className="card row">
        <label>
          Run
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id.slice(0, 8)} {r.status}
              </option>
            ))}
          </select>
        </label>
        <label>
          Diff 对比 Run
          <select value={other} onChange={(e) => setOther(e.target.value)}>
            <option value="">（选择）</option>
            {runs
              .filter((r) => r.id !== runId)
              .map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id.slice(0, 8)}
                </option>
              ))}
          </select>
        </label>
        <button
          className="secondary"
          onClick={async () => {
            if (!runId || !other) return;
            try {
              setDiff(await api.diff(runId, other));
            } catch (e) {
              setMsg(String(e));
            }
          }}
        >
          计算 Diff
        </button>
        <button
          onClick={async () => {
            if (!id || !runId || !other) return;
            try {
              const exp = await api.createExperiment(id, {
                baseline_run_id: runId,
                result_run_id: other,
              });
              setMsg(`创建 experiment 成功：${exp.modified_variable} ${exp.modified_from} → ${exp.modified_to}`);
            } catch (e) {
              setMsg(String(e));
            }
          }}
        >
          创建 experiment
        </button>
      </div>
      {report && (
        <>
          <div className="grid">
            <div className="metric">
              <span>pass_rate</span>
              <b>{(report.pass_rate * 100).toFixed(1)}%</b>
            </div>
            <div className="metric">
              <span>n</span>
              <b>{report.n}</b>
            </div>
            <div className="metric">
              <span>retrieval_level</span>
              <b>{report.retrieval_level}</b>
            </div>
            <div className="metric">
              <span>judge_status</span>
              <b>{report.judge_status}</b>
            </div>
          </div>
          <div className="card">
            <p className="muted">fingerprint</p>
            <code>{report.fingerprint}</code>
            <h2>分项均值</h2>
            <pre>{JSON.stringify(report.means, null, 2)}</pre>
            <h2>retrieval</h2>
            <pre>{JSON.stringify(report.retrieval, null, 2)}</pre>
          </div>
          <div className="card">
            <h2>切片 slices</h2>
            <table>
              <thead>
                <tr>
                  <th>slice</th>
                  <th>n</th>
                  <th>pass_rate</th>
                </tr>
              </thead>
              <tbody>
                {slices.map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v.n}</td>
                    <td>{(v.pass_rate * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card">
            <h2>primary_cause_dist</h2>
            <pre>{JSON.stringify(report.primary_cause_dist, null, 2)}</pre>
          </div>
        </>
      )}
      {diff && (
        <div className="card">
          <h2>Diff</h2>
          <p>
            修复 fail {diff.fixed_fail_count} · 新 fail {diff.new_fail_count} · 仍失败{" "}
            {diff.still_fail_count}
          </p>
          <pre>{JSON.stringify(diff, null, 2)}</pre>
        </div>
      )}
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
