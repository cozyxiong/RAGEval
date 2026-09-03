import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type Calibration, type CaseResult, type JudgeStatus, type Run } from "../api";
import { STATUS_LABEL, pct, shortId } from "../copy";
import { PageHead } from "../Layout";

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
  const st = status?.status || "not_calibrated";

  return (
    <div>
      <PageHead
        kicker="人工复核"
        title="机器打分准不准？"
        lead="抽若干题，你按「过关 / 不过关」标一遍。对得够多，才能把自动分数当成门槛。建议至少标 20 题。"
      />
      <div className="card">
        <p>
          当前校准 status：<b>{STATUS_LABEL[st] || st}</b>
        </p>
        <p className="hint">
          未校准也能看成绩，但不能把自动分数当成「必须过关」的闸门。
        </p>
        <div className="row">
          <label>
            核对哪一轮
            <select value={rid} onChange={(e) => setRid(e.target.value)}>
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {shortId(r.id)} · {STATUS_LABEL[r.status] || r.status}
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
            用已标的题计算校准
          </button>
        </div>
      </div>
      <div className="card">
        <h2>人工标 Pass/Fail</h2>
        <p className="hint">过关 = 你认为这题系统表现合格。先标，再点上面的计算。</p>
        <table>
          <thead>
            <tr>
              <th>题号</th>
              <th>机器</th>
              <th>你的判断</th>
              <th>备注</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.case_id}>
                <td>{c.case_id}</td>
                <td className={c.judge_label === "pass" ? "ok" : "bad"}>
                  {c.judge_label === "pass" ? "过关" : "不过关"}
                </td>
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
                    <option value="pass">过关</option>
                    <option value="fail">不过关</option>
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
                      setMsg(`已保存人工标 ${c.case_id}`);
                    }}
                  >
                    保存
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h2>混淆矩阵</h2>
        <p className="hint">看机器和你是不是经常意见一致。右上角是「机器放过、你认为不行」——假过关，最危险。</p>
        {confusion ? (
          <table>
            <thead>
              <tr>
                <th></th>
                <th>你认为过关</th>
                <th>你认为不过关</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>机器判过关</td>
                <td className="ok">{confusion.tp}</td>
                <td className="bad">{confusion.fp}</td>
              </tr>
              <tr>
                <td>机器判不过关</td>
                <td>{confusion.fn}</td>
                <td>{confusion.tn}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="muted">先完成人工标再计算校准。</p>
        )}
        {(cal || status?.calibration) && (
          <p className="hint">
            共核对 {(cal || status?.calibration)?.n} 题，一致率{" "}
            {pct((cal || status?.calibration)?.accuracy || 0)}，假过关率{" "}
            {pct((cal || status?.calibration)?.false_pass_rate || 0)}。
          </p>
        )}
      </div>
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
