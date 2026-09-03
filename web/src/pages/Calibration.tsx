import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type Calibration, type CaseResult, type JudgeStatus, type Run } from "../api";

export default function CalibrationPage() {
  const { id } = useParams();
  const [status, setStatus] = useState<JudgeStatus | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [rid, setRid] = useState("");
  const [cases, setCases] = useState<CaseResult[]>([]);
  const [cal, setCal] = useState<Calibration | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!id) return;
    api.judgeStatus(id).then(setStatus);
    api.listRuns(id).then((rs) => {
      setRuns(rs);
      if (rs[0]) setRid(rs[0].id);
    });
  }, [id]);

  useEffect(() => {
    if (!rid) return;
    api.runCases(rid).then(setCases);
  }, [rid]);

  const confusion = cal?.confusion || status?.calibration?.confusion;

  return (
    <div>
      <h1>校准</h1>
      <div className="card">
        <p>
          status：<b>{status?.status || "not_calibrated"}</b>
        </p>
        <div className="row">
          <label>
            Run
            <select value={rid} onChange={(e) => setRid(e.target.value)}>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id.slice(0, 8)} {r.status}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={async () => {
              try {
                const run = runs.find((r) => r.id === rid);
                if (!run) return;
                const result = await api.calibrate(run.judge_config_id, rid);
                setCal(result);
                if (id) setStatus(await api.judgeStatus(id));
              } catch (e) {
                setMsg(String(e));
              }
            }}
          >
            计算校准
          </button>
        </div>
      </div>
      <div className="card">
        <h2>人工标 Pass/Fail</h2>
        <table>
          <thead>
            <tr>
              <th>case</th>
              <th>judge</th>
              <th>human</th>
              <th>原因</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.case_id}>
                <td>{c.case_id}</td>
                <td className={c.judge_label === "pass" ? "ok" : "bad"}>{c.judge_label}</td>
                <td>
                  <select
                    value={c.human_label || ""}
                    onChange={(e) =>
                      setCases((cs) =>
                        cs.map((x) => (x.case_id === c.case_id ? { ...x, human_label: e.target.value } : x))
                      )
                    }
                  >
                    <option value="">未标</option>
                    <option value="pass">pass</option>
                    <option value="fail">fail</option>
                  </select>
                </td>
                <td>
                  <input
                    value={c.human_reason || ""}
                    onChange={(e) =>
                      setCases((cs) =>
                        cs.map((x) => (x.case_id === c.case_id ? { ...x, human_reason: e.target.value } : x))
                      )
                    }
                  />
                </td>
                <td>
                  <button
                    className="ghost"
                    onClick={async () => {
                      if (!c.human_label) return;
                      await api.patchHuman(rid, c.case_id, {
                        human_label: c.human_label,
                        human_reason: c.human_reason || "",
                      });
                      setMsg(`已标注 ${c.case_id}`);
                    }}
                  >
                    保存人工标
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h2>混淆矩阵</h2>
        {confusion ? (
          <table>
            <thead>
              <tr>
                <th></th>
                <th>human pass</th>
                <th>human fail</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>judge pass</td>
                <td>{confusion.tp}</td>
                <td>{confusion.fp}</td>
              </tr>
              <tr>
                <td>judge fail</td>
                <td>{confusion.fn}</td>
                <td>{confusion.tn}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="muted">先完成人工标再计算校准。</p>
        )}
        {(cal || status?.calibration) && (
          <p>
            n={(cal || status?.calibration)?.n} accuracy=
            {(cal || status?.calibration)?.accuracy} FPR=
            {(cal || status?.calibration)?.false_pass_rate} FNR=
            {(cal || status?.calibration)?.false_fail_rate}
          </p>
        )}
      </div>
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
