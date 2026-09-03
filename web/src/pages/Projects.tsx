import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Project } from "../api";

const DEFAULT_SPEC = `{
  "product_mode": "closed_domain",
  "retrieval_level": 1,
  "k": 8,
  "pass_gate": {"behavior": true, "faithfulness": 0.85, "completeness": 0.75, "relevancy": 0.85}
}`;

export default function ProjectsPage() {
  const [rows, setRows] = useState<Project[]>([]);
  const [name, setName] = useState("Demo");
  const [adapter, setAdapter] = useState("http://127.0.0.1:8100");
  const [spec, setSpec] = useState(DEFAULT_SPEC);
  const [msg, setMsg] = useState("");
  const [ping, setPing] = useState("");

  const load = () => api.listProjects().then(setRows).catch((e) => setMsg(String(e)));
  useEffect(() => {
    load();
  }, []);

  async function create() {
    setMsg("");
    try {
      await api.createProject({
        name,
        adapter_url: adapter,
        spec: JSON.parse(spec),
      });
      await load();
    } catch (e) {
      setMsg(String(e));
    }
  }

  async function save(p: Project) {
    try {
      await api.patchProject(p.id, {
        adapter_url: p.adapter_url,
        spec: p.spec,
        name: p.name,
      });
      await load();
    } catch (e) {
      setMsg(String(e));
    }
  }

  async function doPing(id: string) {
    setPing("…");
    try {
      const r = await api.ping(id);
      setPing(JSON.stringify(r));
    } catch (e) {
      setPing(String(e));
    }
  }

  return (
    <div>
      <h1>项目</h1>
      <div className="card">
        <div className="row">
          <label>
            名称
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            Adapter URL
            <input value={adapter} onChange={(e) => setAdapter(e.target.value)} />
          </label>
          <button onClick={create}>创建</button>
        </div>
        <label>
          Spec JSON
          <textarea value={spec} onChange={(e) => setSpec(e.target.value)} />
        </label>
        {msg && <p className="err">{msg}</p>}
      </div>
      {rows.map((p) => (
        <div className="card" key={p.id}>
          <div className="row">
            <strong>{p.name}</strong>
            <span className="chip">{p.product_mode}</span>
            <Link to={`/projects/${p.id}/dataset`}>打开</Link>
          </div>
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
          <label>
            Spec
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
          </label>
        </div>
      ))}
      {ping && <p className="muted">Ping 结果：{ping}</p>}
    </div>
  );
}
