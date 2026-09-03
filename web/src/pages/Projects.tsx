import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Project } from "../api";
import { PageHead } from "../Layout";

const DEFAULT_SPEC = {
  product_mode: "closed_domain",
  retrieval_level: 1,
  k: 8,
  pass_gate: { behavior: true, faithfulness: 0.85, completeness: 0.75, relevancy: 0.85 },
};

export default function ProjectsPage() {
  const [rows, setRows] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [adapter, setAdapter] = useState("http://127.0.0.1:8100");
  const [specText, setSpecText] = useState(JSON.stringify(DEFAULT_SPEC, null, 2));
  const [msg, setMsg] = useState("");
  const [ping, setPing] = useState("");

  const load = () => api.listProjects().then(setRows).catch((e) => setMsg(String(e)));
  useEffect(() => {
    load();
  }, []);

  async function create() {
    setMsg("");
    try {
      await api.createProject({ name: name || "未命名系统", adapter_url: adapter, spec: JSON.parse(specText) });
      setName("");
      await load();
    } catch (e) {
      setMsg(String(e));
    }
  }

  async function save(p: Project) {
    try {
      await api.patchProject(p.id, { adapter_url: p.adapter_url, spec: p.spec, name: p.name });
      await load();
      setMsg("已保存");
    } catch (e) {
      setMsg(String(e));
    }
  }

  async function doPing(id: string) {
    setPing("正在测连通…");
    try {
      const r = await api.ping(id);
      setPing(r.ok === false ? "没连上" : "已连通，可以出题开考");
    } catch (e) {
      setPing(`没连上：${e}`);
    }
  }

  return (
    <div>
      <PageHead
        kicker="① 连接系统"
        title="你要给哪套问答打分？"
        lead="把已经开发好的 RAG 接口填进来。平台不会改它，只按同一套考题逐题提问并打分。"
      />
      <div className="card">
        <h2>接入一套新系统</h2>
        <div className="row">
          <label>
            系统名称
            <input placeholder="例如：BaGuLLM 知识库" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            Adapter 问答接口地址
            <input value={adapter} onChange={(e) => setAdapter(e.target.value)} />
          </label>
          <button onClick={create}>创建</button>
        </div>
        <p className="hint">Mock 演示填 http://127.0.0.1:8100 ；BaGuLLM 填 http://127.0.0.1:8101 。</p>
        <details className="advanced">
          <summary>高级：Spec 打分门槛（一般不用改）</summary>
          <textarea value={specText} onChange={(e) => setSpecText(e.target.value)} />
        </details>
        {msg && <p className="err">{msg}</p>}
      </div>
      {rows.map((p) => (
        <div className="card sys-card" key={p.id}>
          <div>
            <h3>{p.name}</h3>
            <span className="chip">只根据检索资料作答</span>
            <p className="hint">接口 {p.adapter_url}</p>
            <div className="row">
              <label>
                Adapter
                <input
                  value={p.adapter_url}
                  onChange={(e) =>
                    setRows((rs) => rs.map((x) => (x.id === p.id ? { ...x, adapter_url: e.target.value } : x)))
                  }
                />
              </label>
              <button className="secondary" onClick={() => doPing(p.id)}>
                Ping
              </button>
              <button className="ghost" onClick={() => save(p)}>
                保存 Spec
              </button>
            </div>
            <details className="advanced">
              <summary>Spec</summary>
              <textarea
                value={JSON.stringify(p.spec, null, 2)}
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value);
                    setRows((rs) => rs.map((x) => (x.id === p.id ? { ...x, spec: parsed } : x)));
                  } catch {
                    /* keep editing */
                  }
                }}
              />
            </details>
          </div>
          <Link to={`/projects/${p.id}/dataset`}>
            <button>去准备题目</button>
          </Link>
        </div>
      ))}
      {ping && <p className="muted">{ping}</p>}
    </div>
  );
}
