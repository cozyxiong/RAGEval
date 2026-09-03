import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Project } from "../api";
import { PageHead } from "../Layout";

export default function ProjectsPage() {
  const [rows, setRows] = useState<Project[]>([]);
  const [msg, setMsg] = useState("");
  const [ping, setPing] = useState("");

  const load = () => api.listProjects().then(setRows).catch((e) => setMsg(String(e)));
  useEffect(() => {
    load();
  }, []);

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
        kicker="历史"
        title="已接入的系统"
        lead="这里是以前接过的问答系统。要考新系统，去新建页填写接口。"
      />
      <div className="row" style={{ marginBottom: 16 }}>
        <Link to="/new">
          <button>创建</button>
        </Link>
      </div>
      {rows.length === 0 && (
        <div className="card">
          <p className="hint">还没有历史记录。先创建一个系统。</p>
        </div>
      )}
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
            <button className="ghost">打开题库</button>
          </Link>
        </div>
      ))}
      {ping && <p className="muted">{ping}</p>}
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
