import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Dataset, type Version } from "../api";
import { RV_LABEL } from "../copy";
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

export default function RunCreate() {
  const { id } = useParams();
  const nav = useNavigate();
  const [rv, setRv] = useState({ ...EMPTY_RV });
  const [vid, setVid] = useState("");
  const [versions, setVersions] = useState<Version[]>([]);
  const [gate, setGate] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!id) return;
    (async () => {
      const dss: Dataset[] = await api.listDatasets(id);
      const all: Version[] = [];
      for (const d of dss) all.push(...(await api.listVersions(d.id)));
      setVersions(all);
      const confirmed = all.find((v) => v.confirmed_at) || all[0];
      if (confirmed) setVid(confirmed.id);
    })().catch((e) => setMsg(String(e)));
  }, [id]);

  return (
    <div>
      <PageHead
        kicker="新建评测"
        title="开始新的一轮"
        lead="每次只改一个变量（比如提示词或检索），才能判断到底是哪一处改好了。点 Start 后去历史页看进度。"
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
        </div>
        <div className="row" style={{ marginTop: 18 }}>
          <button
            onClick={async () => {
              if (!id) return;
              try {
                await api.createRun(id, {
                  dataset_version_id: vid,
                  rag_version: rv,
                  use_as_gate: gate,
                });
                nav(`/projects/${id}/runs`);
              } catch (e) {
                setMsg(String(e));
              }
            }}
          >
            Start
          </button>
          <button className="ghost" onClick={() => id && nav(`/projects/${id}/runs`)}>
            返回历史
          </button>
        </div>
        {msg && <p className="err">{msg}</p>}
      </div>
    </div>
  );
}
