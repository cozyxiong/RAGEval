import type { ReactNode } from "react";
import { NavLink, useLocation, useParams } from "react-router-dom";

const STEPS = [
  { path: "", label: "① 连接系统", hint: "告诉平台考哪套问答" },
  { path: "dataset", label: "② 准备题目", hint: "题库确认后才能开考" },
  { path: "runs", label: "③ 开始评测", hint: "提交后后台逐题打分" },
  { path: "report", label: "④ 看成绩", hint: "及格率、错因、和上次对比" },
  { path: "calibration", label: "人工复核", hint: "抽查看机器打分准不准" },
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
          <span className="logo">评</span>
          <div>
            <strong>问答评测台</strong>
            <small>给已上线的 RAG 打分</small>
          </div>
        </NavLink>
        <p className="side-note">
          不改对方系统。接上接口、准备考题、跑一轮，就能看到「答对了多少、错在检索还是胡编」。
        </p>
        <nav className="side-nav">
          <NavLink to="/" end>
            全部系统
          </NavLink>
          {pid &&
            STEPS.filter((s) => s.path).map((s) => (
              <NavLink key={s.path} to={`/projects/${pid}/${s.path}`}>
                {s.label}
                <em>{s.hint}</em>
              </NavLink>
            ))}
        </nav>
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

