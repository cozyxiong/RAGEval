import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import CalibrationPage from "./pages/Calibration";
import DatasetPage from "./pages/Dataset";
import ProjectsPage from "./pages/Projects";
import ReportPage from "./pages/Report";
import RunsPage from "./pages/Runs";

function Subnav() {
  const location = useLocation();
  const match = location.pathname.match(/^\/projects\/([^/]+)/);
  const id = match?.[1];
  if (!id) return null;
  const items = [
    ["dataset", "数据集"],
    ["calibration", "校准"],
    ["runs", "Runs"],
    ["report", "报告"],
  ];
  return (
    <>
      {items.map(([path, label]) => (
        <NavLink key={path} to={`/projects/${id}/${path}`}>
          {label}
        </NavLink>
      ))}
    </>
  );
}

export default function App() {
  return (
    <div>
      <header className="top">
        <div className="brand">RAG Eval</div>
        <nav className="nav">
          <NavLink to="/" end>
            项目
          </NavLink>
          <Subnav />
        </nav>
      </header>
      <main className="wrap">
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:id/dataset" element={<DatasetPage />} />
          <Route path="/projects/:id/calibration" element={<CalibrationPage />} />
          <Route path="/projects/:id/runs" element={<RunsPage />} />
          <Route path="/projects/:id/report" element={<ReportPage />} />
        </Routes>
      </main>
    </div>
  );
}
