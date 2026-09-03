from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web" / "src"


def _read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_five_pages_exist_with_spec_actions() -> None:
    projects = _read("pages", "Projects.tsx")
    dataset = _read("pages", "Dataset.tsx")
    calibration = _read("pages", "Calibration.tsx")
    runs = _read("pages", "Runs.tsx")
    report = _read("pages", "Report.tsx")
    api = _read("api.ts")

    assert "创建" in projects and "Ping" in projects and "Adapter" in projects and "Spec" in projects
    assert "编辑" in dataset and "Generate" in dataset and "Confirm" in dataset and "抽校准集" in dataset
    assert "人工标" in calibration and "混淆矩阵" in calibration and "status" in calibration
    assert "rag_version" in runs and "Start" in runs and "进度" in runs and "fail 列表" in runs
    assert "切片" in report and "Diff" in report and "创建 experiment" in report

    for src in (projects, dataset, calibration, runs, report, api):
        assert "/v1" in src or "from \"../api\"" in src or "from \"./api\"" in src
        assert "openai.com" not in src.lower()
        assert "ragas" not in src.lower()


def test_web_only_calls_rest_prefix() -> None:
    api = _read("api.ts")
    assert 'const BASE = "/v1"' in api
    assert "fetch(`${BASE}" in api or "fetch(`${BASE}${path}`" in api
