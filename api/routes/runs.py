from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db
from api.jsonutil import loads
from api.models import CaseResult, DatasetCase, DatasetVersion, Project, Run, utcnow
from api.schemas import CaseResultOut, HumanLabelIn, RunCreate, RunOut
from api.services import get_or_create_judge_config, latest_judge_status, make_run, run_to_out

router = APIRouter(prefix="/v1", tags=["runs"])


def _result_out(row: CaseResult) -> CaseResultOut:
    return CaseResultOut(
        id=row.id,
        run_id=row.run_id,
        case_id=row.case_id,
        actual_answer=row.actual_answer,
        retrieved_chunks=loads(row.retrieved_chunks_json, []),
        meta=loads(row.meta_json, {}),
        latency_ms=row.latency_ms,
        evaluated_behavior=row.evaluated_behavior,
        claims=loads(row.claims_json, []),
        faithfulness=row.faithfulness,
        completeness=row.completeness,
        answer_relevancy=row.answer_relevancy,
        judge_label=row.judge_label,
        judge_reason=row.judge_reason,
        human_label=row.human_label,
        human_reason=row.human_reason,
        retrieval_metrics=loads(row.retrieval_metrics_json, {}),
        failure_type=loads(row.failure_type_json, []),
        primary_cause=row.primary_cause,
        secondary_cause=row.secondary_cause,
        diagnosis=loads(row.diagnosis_json, {}),
        error=row.error,
    )


@router.post("/projects/{project_id}/runs", response_model=RunOut)
def create_run(project_id: str, body: RunCreate, db: Session = Depends(get_db)) -> RunOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    ver = db.get(DatasetVersion, body.dataset_version_id)
    if not ver:
        raise HTTPException(404, "dataset version not found")
    if ver.confirmed_at is None:
        raise HTTPException(400, "dataset version is not confirmed")
    try:
        judge_cfg = get_or_create_judge_config(db, project, body.judge_config_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if body.use_as_gate:
        status = latest_judge_status(db, project.id, judge_cfg.id)
        if status != "calibrated":
            raise HTTPException(400, f"use_as_gate requires calibrated judge, status={status}")
    total = db.query(DatasetCase).filter_by(dataset_version_id=ver.id).count()
    if total == 0:
        raise HTTPException(400, "dataset version has no cases")
    try:
        row = make_run(db, project, ver.id, judge_cfg, body.rag_version, total)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return run_to_out(row)


@router.get("/projects/{project_id}/runs", response_model=list[RunOut])
def list_runs(project_id: str, db: Session = Depends(get_db)) -> list[RunOut]:
    if not db.get(Project, project_id):
        raise HTTPException(404, "project not found")
    rows = db.query(Run).filter_by(project_id=project_id).order_by(Run.created_at.desc()).all()
    return [run_to_out(r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunOut:
    row = db.get(Run, run_id)
    if not row:
        raise HTTPException(404, "run not found")
    return run_to_out(row)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: str, db: Session = Depends(get_db)) -> RunOut:
    row = db.get(Run, run_id)
    if not row:
        raise HTTPException(404, "run not found")
    if row.status in ("COMPLETED", "FAILED", "CANCELLED"):
        return run_to_out(row)
    row.status = "CANCELLED"
    row.finished_at = utcnow()
    db.flush()
    return run_to_out(row)


@router.get("/runs/{run_id}/cases", response_model=list[CaseResultOut])
def list_run_cases(run_id: str, db: Session = Depends(get_db)) -> list[CaseResultOut]:
    row = db.get(Run, run_id)
    if not row:
        raise HTTPException(404, "run not found")
    results = db.query(CaseResult).filter_by(run_id=run_id).all()
    return [_result_out(r) for r in results]


@router.patch("/runs/{run_id}/cases/{case_id}/human", response_model=CaseResultOut)
def patch_human(
    run_id: str, case_id: str, body: HumanLabelIn, db: Session = Depends(get_db)
) -> CaseResultOut:
    row = (
        db.query(CaseResult).filter_by(run_id=run_id, case_id=case_id).first()
    )
    if not row:
        raise HTTPException(404, "case result not found")
    row.human_label = body.human_label
    row.human_reason = body.human_reason
    db.flush()
    return _result_out(row)
