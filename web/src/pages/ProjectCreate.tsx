import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../Layout";

const DEFAULT_SPEC = {
  product_mode: "closed_domain",
  retrieval_level: 1,
  k: 8,
  pass_gate: { behavior: true, faithfulness: 0.85, completeness: 0.75, relevancy: 0.85 },
};

export default function ProjectCreate() {
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [adapter, setAdapter] = useState("http://127.0.0.1:8100");
  const [specText, setSpecText] = useState(JSON.stringify(DEFAULT_SPEC, null, 2));
  const [msg, setMsg] = useState("");

  async function create() {
    setMsg("");
    try {
      const p = await api.createProject({
        name: name || "未命名系统",
        adapter_url: adapter,
        spec: JSON.parse(specText),
      });
      nav(`/projects/${p.id}/dataset`);
    } catch (e) {
      setMsg(String(e));
    }
  }

  return (
    <div>
      <PageHead
        kicker="新建"
        title="接入一套问答系统"
        lead="填名称和 Adapter 接口。平台不会改对方系统，只按同一套考题提问并打分。"
      />
      <div className="card">
        <div className="row">
          <label>
            系统名称
            <input placeholder="例如：BaGuLLM 知识库" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            Adapter 问答接口地址
            <input value={adapter} onChange={(e) => setAdapter(e.target.value)} />
          </label>
        </div>
        <p className="hint">Mock 演示填 http://127.0.0.1:8100 ；BaGuLLM 填 http://127.0.0.1:8101 。</p>
        <details className="advanced">
          <summary>高级：Spec 打分门槛（一般不用改）</summary>
          <textarea value={specText} onChange={(e) => setSpecText(e.target.value)} />
        </details>
        <div className="row" style={{ marginTop: 18 }}>
          <button onClick={create}>创建</button>
          <button className="ghost" onClick={() => nav("/")}>
            返回历史
          </button>
        </div>
        {msg && <p className="err">{msg}</p>}
      </div>
    </div>
  );
}
