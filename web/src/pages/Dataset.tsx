import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type Dataset, type EvalCase, type Version } from "../api";

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
  const [hints, setHints] = useState("总部在哪里");
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

  async function save() {
    if (!vid) return;
    await api.upsertCases(vid, cases);
    setMsg("已保存编辑");
  }
  return (
    <div>
      <h1>数据集</h1>
      <div className="card row">
        <label>
          新建名称
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <button
          onClick={async () => {
            if (!id) return;
            await api.createDataset(id, { kind: "gold", name });
            await loadDs();
          }}
        >
          创建数据集
        </button>
        <label>
          数据集
          <select value={dsId} onChange={(e) => setDsId(e.target.value)}>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.kind})
              </option>
            ))}
          </select>
        </label>
        <label>
          Version
          <select value={vid} onChange={(e) => setVid(e.target.value)}>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version} {v.confirmed_at ? "已确认" : "草稿"} n={v.case_count}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="card row">
        <label>
          Generate hints
          <input value={hints} onChange={(e) => setHints(e.target.value)} />
        </label>
        <button
          className="secondary"
          onClick={async () => {
            const drafted = await api.generate(vid, hints.split(/[,，]/).map((s) => s.trim()).filter(Boolean));
            setCases(drafted);
          }}
        >
          Generate
        </button>
        <button className="ghost" onClick={save}>
          编辑保存
        </button>
        <button
          onClick={async () => {
            try {
              const v = await api.confirm(vid);
              setMsg(`Confirm 成功 hash=${v.hash}`);
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
          className="secondary"
          onClick={async () => {
            try {
              const v = await api.sampleCalibration(vid);
              setMsg(`抽校准集完成 n=${v.case_count}`);
              await loadDs();
            } catch (e) {
              setMsg(String(e));
            }
          }}
        >
          抽校准集
        </button>
        {current?.confirmed_at && <span className="ok">已 Confirm</span>}
      </div>
      <div className="card">
        <button
          className="ghost"
          onClick={() => setCases((cs) => [...cs, emptyCase()])}
        >
          新增 case
        </button>
        <table>
          <thead>
            <tr>
              <th>case_id</th>
              <th>query</th>
              <th>type</th>
              <th>behavior</th>
              <th>expected_answer</th>
              <th>source</th>
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
                    <option>answerable</option>
                    <option>unanswerable</option>
                    <option>ambiguous</option>
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
                    <option>answer</option>
                    <option>refuse</option>
                    <option>clarify</option>
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
                            ? { ...x, expected_source: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }
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
