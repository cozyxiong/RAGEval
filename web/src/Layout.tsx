import type { ReactNode } from "react";
import { NavLink, useLocation, useParams } from "react-router-dom";

const STEPS = [
  { path: "", label: "系统", hint: "连接要评测的问答" },
  { path: "dataset", label: "题库", hint: "确认后才能开考" },
  { path: "runs", label: "评测", hint: "后台逐题打分" },
  { path: "report", label: "报告", hint: "及格率与错因" },
  { path: "calibration", label: "校准", hint: "核对机器打分" },
];

export default function Shell({ children }: { children: ReactNode }) {
  const { id } = useParams();
  const loc = useLocation();
  const match = loc.pathname.match(/^\/projects\/([^/]+)/);
  const pid = id || match?.[1];

  return (
    <div className="app">
      <aside className="side">
        <NavLink to="/" className="brand">
          <span className="logo">R</span>
          <div>
            <strong>RAG Eval</strong>
            <small>问答评测</small>
          </div>
        </NavLink>
        <nav className="side-nav">
          <div className="side-label">工作区</div>
          <NavLink to="/" end>
            全部系统
          </NavLink>
          {pid && (
            <>
              <div className="side-label">当前系统</div>
              {STEPS.filter((s) => s.path).map((s) => (
                <NavLink key={s.path} to={`/projects/${pid}/${s.path}`}>
                  {s.label}
                  <em>{s.hint}</em>
                </NavLink>
              ))}
            </>
          )}
        </nav>
        <p className="side-note">不改对方系统。接上接口、准备考题、跑一轮，即可看到答对多少、错在检索还是胡编。</p>
      </aside>
      <div className="main">
        {pid && (
          <ol className="steps">
            {STEPS.map((s) => {
              const href = s.path ? `/projects/${pid}/${s.path}` : "/";
              const on = s.path
                ? loc.pathname.includes(`/projects/${pid}/${s.path}`)
                : loc.pathname === "/";
              return (
                <li key={s.label} className={on ? "on" : ""}>
                  <NavLink to={href}>{s.label}</NavLink>
                </li>
              );
            })}
          </ol>
        )}
        {children}
      </div>
    </div>
  );
}

export function PageHead({
  kicker,
  title,
  lead,
}: {
  kicker?: string;
  title: string;
  lead: string;
}) {
  return (
    <header className="page-head">
      {kicker && <p className="kicker">{kicker}</p>}
      <h1>{title}</h1>
      <p className="lead">{lead}</p>
    </header>
  );
}
