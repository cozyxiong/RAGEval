import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Dataset, type EvalCase, type Version } from "../api";
import { BEHAVE_LABEL, TYPE_LABEL } from "../copy";
import { PageHead } from "../Layout";

const emptyCase = (): EvalCase => ({
  case_id: "",
  query: "",
  case_type: "answerable",
  expected_behavior: "answer",
  expected_answer: "",
  expected_source: [],
  supporting_passage: [],
  tags: [],
});

export default function DatasetPage() {
  const { id } = useParams();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dsId, setDsId] = useState("");
  const [versions, setVersions] = useState<Version[]>([]);
  const [vid, setVid] = useState("");
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [hints, setHints] = useState("什么是 RAG");
  const [msg, setMsg] = useState("");
  const [name, setName] = useState("gold");

  async function loadDs() {
    if (!id) return;
    const rows = await api.listDatasets(id);
    setDatasets(rows);
    if (rows[0] && !dsId) setDsId(rows[0].id);
  }
  useEffect(() => {
    loadDs().catch((e) => setMsg(String(e)));
  }, [id]);
  useEffect(() => {
    if (!dsId) return;
    api.listVersions(dsId).then((vs) => {
      setVersions(vs);
      if (vs[0]) setVid(vs[0].id);
    });
  }, [dsId]);
  useEffect(() => {
    if (!vid) return;
    api.listCases(vid).then(setCases).catch((e) => setMsg(String(e)));
  }, [vid]);

  const current = versions.find((v) => v.id === vid);
  const n = cases.length;
  const counts = {
    a: cases.filter((c) => c.case_type === "answerable").length,
    u: cases.filter((c) => c.case_type === "unanswerable").length,
    m: cases.filter((c) => c.case_type === "ambiguous").length,
  };

  return (
    <div>
      <PageHead
        kicker="② 准备题目"
        title="用同一套考题衡量系统"
        lead="题目要覆盖三种情况：资料里有答案、资料里没有该拒绝、问法含糊该追问。建议 50–100 题。点 Confirm 锁定后才能开考。"
      />
      <div className="grid" style={{ marginBottom: 16 }}>
        <div className="metric">
          <span>题目总数</span>
          <b>{n}</b>
          <small>{n < 50 ? "偏少，判断会飘" : n <= 100 ? "规模合适" : "可以再精炼"}</small>
        </div>
        <div className="metric">
          <span>资料里有答案</span>
          <b>{counts.a}</b>
        </div>
        <div className="metric">
          <span>该拒绝</span>
          <b>{counts.u}</b>
        </div>
        <div className="metric">
          <span>该追问</span>
          <b>{counts.m}</b>
        </div>
      </div>
      <div className="card">
        <div className="row">
          <label>
            题库名称
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <button
            className="ghost"
            onClick={async () => {
              if (!id) return;
              await api.createDataset(id, { kind: "gold", name });
              await loadDs();
            }}
          >
            新建题库
          </button>
          <label>
            当前题库
            <select value={dsId} onChange={(e) => setDsId(e.target.value)}>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}（{TYPE_LABEL[d.kind] || d.kind}）
                </option>
              ))}
            </select>
          </label>
          <label>
            版本
            <select value={vid} onChange={(e) => setVid(e.target.value)}>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  第 {v.version} 版 {v.confirmed_at ? "已锁定" : "草稿"} · {v.case_count} 题
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <div className="card">
        <div className="row">
          <label>
            Generate 出题提示
            <input value={hints} onChange={(e) => setHints(e.target.value)} />
          </label>
          <button
            className="secondary"
            onClick={async () => {
              const drafted = await api.generate(
                vid,
                hints.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
              );
              setCases(drafted);
            }}
          >
            Generate
          </button>
          <button
            className="ghost"
            onClick={async () => {
              if (!vid) return;
              await api.upsertCases(vid, cases);
              setMsg("已保存编辑");
            }}
          >
            编辑保存
          </button>
          <button
            onClick={async () => {
              try {
                const v = await api.confirm(vid);
                setMsg(`Confirm 成功，这套题已锁定，可以去开考。hash=${v.hash.slice(0, 8)}`);
                const vs = await api.listVersions(dsId);
                setVersions(vs);
              } catch (e) {
                setMsg(String(e));
              }
            }}
          >
            Confirm
          </button>
          <button
            className="ghost"
            onClick={async () => {
              try {
                const v = await api.sampleCalibration(vid);
                setMsg(`抽校准集完成，抽了 ${v.case_count} 题给人核对。`);
                await loadDs();
              } catch (e) {
                setMsg(String(e));
              }
            }}
          >
            抽校准集
          </button>
          {current?.confirmed_at && <span className="chip ok">已 Confirm，可开考</span>}
        </div>
        <p className="hint">BaGuLLM 正式考题请用命令 python -m api.seed_bagullm 写入 85 道库内真题。</p>
      </div>
      <div className="card">
        <div className="row" style={{ marginBottom: 8 }}>
          <button className="ghost" onClick={() => setCases((cs) => [...cs, emptyCase()])}>
            新增一题
          </button>
          {id && (
            <Link to={`/projects/${id}/runs`}>
              <button disabled={!current?.confirmed_at}>去开考</button>
            </Link>
          )}
        </div>
        <table>
          <thead>
            <tr>
              <th>编号</th>
              <th>问题</th>
              <th>题型</th>
              <th>期望表现</th>
              <th>标准答案要点</th>
              <th>应命中文档</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c, i) => (
              <tr key={i}>
                <td>
                  <input
                    value={c.case_id}
                    onChange={(e) =>
                      setCases((cs) => cs.map((x, j) => (j === i ? { ...x, case_id: e.target.value } : x)))
                    }
                  />
                </td>
                <td>
                  <input
                    value={c.query}
                    onChange={(e) =>
                      setCases((cs) => cs.map((x, j) => (j === i ? { ...x, query: e.target.value } : x)))
                    }
                  />
                </td>
                <td>
                  <select
                    value={c.case_type}
                    onChange={(e) =>
                      setCases((cs) => cs.map((x, j) => (j === i ? { ...x, case_type: e.target.value } : x)))
                    }
                  >
                    <option value="answerable">{TYPE_LABEL.answerable}</option>
                    <option value="unanswerable">{TYPE_LABEL.unanswerable}</option>
                    <option value="ambiguous">{TYPE_LABEL.ambiguous}</option>
                  </select>
                </td>
                <td>
                  <select
                    value={c.expected_behavior}
                    onChange={(e) =>
                      setCases((cs) =>
                        cs.map((x, j) => (j === i ? { ...x, expected_behavior: e.target.value } : x))
                      )
                    }
                  >
                    <option value="answer">{BEHAVE_LABEL.answer}</option>
                    <option value="refuse">{BEHAVE_LABEL.refuse}</option>
                    <option value="clarify">{BEHAVE_LABEL.clarify}</option>
                  </select>
                </td>
                <td>
                  <input
                    value={c.expected_answer}
                    onChange={(e) =>
                      setCases((cs) =>
                        cs.map((x, j) => (j === i ? { ...x, expected_answer: e.target.value } : x))
                      )
                    }
                  />
                </td>
                <td>
                  <input
                    value={(c.expected_source || []).join(",")}
                    onChange={(e) =>
                      setCases((cs) =>
                        cs.map((x, j) =>
                          j === i
                            ? {
                                ...x,
                                expected_source: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                              }
                            : x
                        )
                      )
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
