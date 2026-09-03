import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, type Diff, type Report, type Run } from "../api";
import { CAUSE_LABEL, STATUS_LABEL, TYPE_LABEL, pct, shortId } from "../copy";
import { PageHead } from "../Layout";

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

  const slices = useMemo(() => Object.values(report?.slices || {}), [report]);
  const causes = useMemo(() => {
    const dist = report?.primary_cause_dist || {};
    const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1;
    return Object.entries(dist).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({
      k,
      v,
      p: v / total,
    }));
  }, [report]);

  return (
    <div>
      <PageHead
        kicker="④ 看成绩"
        title="这轮考得怎么样"
        lead="及格率是「行为对、忠于资料、答得全、问得对」同时满足的比例。点开切片看哪类题最差，用 Diff 对比只改一个变量的前后两轮。"
      />
      <div className="card row">
        <label>
          看哪一轮
          <select value={runId} onChange={(e) => setRunId(e.target.value)}>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {shortId(r.id)} · {STATUS_LABEL[r.status] || r.status} · 提示词 {r.rag_version?.prompt || "—"}
              </option>
            ))}
          </select>
        </label>
        <label>
          和另一轮对比
          <select value={other} onChange={(e) => setOther(e.target.value)}>
            <option value="">先选一轮</option>
            {runs
              .filter((r) => r.id !== runId)
              .map((r) => (
                <option key={r.id} value={r.id}>
                  {shortId(r.id)} · {r.rag_version?.prompt || "—"}
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
              setMsg(`创建 experiment 成功：只改了「${exp.modified_variable}」，从 ${exp.modified_from} 到 ${exp.modified_to}`);
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
          <div className="card hero-score">
            <div>
              <div className="num">{pct(report.pass_rate)}</div>
              <p className="hint">综合及格率 · 共考 {report.n} 题</p>
            </div>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div className="bar">
                <i style={{ width: pct(report.pass_rate) }} />
              </div>
              <p className="hint">
                机器打分校准：{STATUS_LABEL[report.judge_status] || report.judge_status}。
                找到该找的资料：{pct(report.retrieval.expected_source_hit)}。
              </p>
            </div>
          </div>
          <div className="grid">
            <div className="metric">
              <span>忠于资料</span>
              <b>{pct(report.means.faithfulness)}</b>
              <small>有没有编资料里没有的话</small>
            </div>
            <div className="metric">
              <span>答得全</span>
              <b>{pct(report.means.completeness)}</b>
              <small>要点覆盖得怎样</small>
            </div>
            <div className="metric">
              <span>问得对</span>
              <b>{pct(report.means.answer_relevancy)}</b>
              <small>有没有答非所问</small>
            </div>
            <div className="metric">
              <span>资料命中</span>
              <b>{pct(report.retrieval.expected_source_hit)}</b>
              <small>该找的文档找没找到</small>
            </div>
          </div>
          <div className="card">
            <h2>切片 · 三类题各自考得怎样</h2>
            <table>
              <thead>
                <tr>
                  <th>题型</th>
                  <th>题数</th>
                  <th>及格率</th>
                </tr>
              </thead>
              <tbody>
                {slices.map((v) => (
                  <tr key={`${v.case_type}|${v.expected_behavior}`}>
                    <td>{TYPE_LABEL[v.case_type] || v.case_type}</td>
                    <td>{v.n}</td>
                    <td>
                      <strong>{pct(v.pass_rate)}</strong>
                      <div className="bar" style={{ marginTop: 6 }}>
                        <i style={{ width: pct(v.pass_rate) }} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card">
            <h2>错在哪</h2>
            {causes.length === 0 && <p className="hint">这轮没有标出主因，或全部过关。</p>}
            {causes.map((c) => (
              <div className="cause-row" key={c.k}>
                <span style={{ width: 180 }}>{CAUSE_LABEL[c.k] || c.k}</span>
                <div className="bar">
                  <i style={{ width: pct(c.p) }} />
                </div>
                <span>{c.v} 题</span>
              </div>
            ))}
          </div>
        </>
      )}
      {diff && (
        <div className="card">
          <h2>Diff · 和上一轮比</h2>
          <div className="grid">
            <div className="metric">
              <span>修好的旧错题</span>
              <b>{diff.fixed_fail_count}</b>
            </div>
            <div className="metric">
              <span>新引入的错题</span>
              <b>{diff.new_fail_count}</b>
            </div>
            <div className="metric">
              <span>仍然不会的</span>
              <b>{diff.still_fail_count}</b>
            </div>
            <div className="metric">
              <span>及格率变化</span>
              <b>{pct((diff.metric_delta as { pass_rate?: number }).pass_rate)}</b>
            </div>
          </div>
          <p className="hint">
            {diff.fingerprint_diff.changed ? "两轮配置确实不同。" : "两轮指纹相同，可能没改到变量。"}
          </p>
        </div>
      )}
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
