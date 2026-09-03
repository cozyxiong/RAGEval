import type { ReactNode } from "react";
import { NavLink, useLocation, useParams } from "react-router-dom";

const PROJECT_NAV = [
  { path: "dataset", label: "题库" },
  { path: "runs/new", label: "新建评测" },
  { path: "runs", label: "评测历史" },
  { path: "report", label: "报告" },
  { path: "calibration", label: "校准" },
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
            历史系统
          </NavLink>
          <NavLink to="/new">新建系统</NavLink>
          {pid && (
            <>
              <div className="side-label">当前系统</div>
              {PROJECT_NAV.map((s) => (
                <NavLink key={s.path} to={`/projects/${pid}/${s.path}`} end={s.path === "runs"}>
                  {s.label}
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
            {[
              { href: `/projects/${pid}/dataset`, label: "题库", on: loc.pathname.includes("/dataset") },
              { href: `/projects/${pid}/runs/new`, label: "新建", on: loc.pathname.endsWith("/runs/new") },
              { href: `/projects/${pid}/runs`, label: "历史", on: loc.pathname.endsWith("/runs") },
              { href: `/projects/${pid}/report`, label: "报告", on: loc.pathname.includes("/report") },
              { href: `/projects/${pid}/calibration`, label: "校准", on: loc.pathname.includes("/calibration") },
            ].map((s) => (
              <li key={s.label} className={s.on ? "on" : ""}>
                <NavLink to={s.href}>{s.label}</NavLink>
              </li>
            ))}
          </ol>
        )}
        {!pid && (
          <ol className="steps">
            <li className={loc.pathname === "/" ? "on" : ""}>
              <NavLink to="/">历史</NavLink>
            </li>
            <li className={loc.pathname === "/new" ? "on" : ""}>
              <NavLink to="/new">新建</NavLink>
            </li>
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
