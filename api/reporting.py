from __future__ import annotations

from sqlalchemy.orm import Session

from api.jsonutil import loads
from api.models import CaseResult, DatasetCase, JudgeCalibration, Run
from api.services import latest_judge_status
from core.regression import build_report, diff_reports
from core.spec import parse_spec


def run_case_rows(db: Session, run: Run) -> list[dict]:
    results = db.query(CaseResult).filter_by(run_id=run.id).all()
    gold = {
        c.case_id: c
        for c in db.query(DatasetCase).filter_by(dataset_version_id=run.dataset_version_id).all()
    }
    rows: list[dict] = []
    for r in results:
        g = gold.get(r.case_id)
        rows.append(
            {
                "case_id": r.case_id,
                "judge_label": r.judge_label,
                "case_type": g.case_type if g else "unknown",
                "expected_behavior": g.expected_behavior if g else "unknown",
                "faithfulness": r.faithfulness,
                "completeness": r.completeness,
                "answer_relevancy": r.answer_relevancy,
                "retrieval_metrics": loads(r.retrieval_metrics_json, {}),
                "primary_cause": r.primary_cause,
            }
        )
    return rows


def report_for_run(db: Session, run: Run) -> dict:
    spec = parse_spec(loads(run.spec_json, {}))
    status = latest_judge_status(db, run.project_id, run.judge_config_id)
    report = build_report(
        fingerprint=run.fingerprint,
        retrieval_level=spec.retrieval_level,
        judge_status=status,
        cases=run_case_rows(db, run),
    )
    if spec.retrieval_level == 1 and "recall" in (report.get("retrieval") or {}):
        raise RuntimeError("Level 1 report must not contain recall")
    return report


def fail_ids(db: Session, run: Run) -> list[str]:
    rows = db.query(CaseResult).filter_by(run_id=run.id, judge_label="fail").all()
    return [r.case_id for r in rows]
