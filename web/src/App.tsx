import type { ReactNode } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import Shell from "./Layout";
import CalibrationPage from "./pages/Calibration";
import DatasetPage from "./pages/Dataset";
import ProjectCreate from "./pages/ProjectCreate";
import ProjectsPage from "./pages/Projects";
import ReportPage from "./pages/Report";
import RunCreate from "./pages/RunCreate";
import RunsPage from "./pages/Runs";

function Frame({ children }: { children: ReactNode }) {
  return (
    <Shell>
      <div className="steps" style={{ display: "none" }}>
        <NavLink to="/">项目</NavLink>
      </div>
      {children}
    </Shell>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Frame><ProjectsPage /></Frame>} />
      <Route path="/new" element={<Frame><ProjectCreate /></Frame>} />
      <Route path="/projects/:id/dataset" element={<Frame><DatasetPage /></Frame>} />
      <Route path="/projects/:id/calibration" element={<Frame><CalibrationPage /></Frame>} />
      <Route path="/projects/:id/runs/new" element={<Frame><RunCreate /></Frame>} />
      <Route path="/projects/:id/runs" element={<Frame><RunsPage /></Frame>} />
      <Route path="/projects/:id/report" element={<Frame><ReportPage /></Frame>} />
    </Routes>
  );
}
