from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db
from api.jsonutil import loads
from api.models import Experiment, JudgeConfig, Project, Run, utcnow
from api.schemas import ExperimentCreate, ExperimentOut
from core.experiment import ExperimentError, single_variable_change

router = APIRouter(prefix="/v1", tags=["experiments"])


def _out(row: Experiment) -> ExperimentOut:
    return ExperimentOut(
        id=row.id,
        project_id=row.project_id,
        baseline_run_id=row.baseline_run_id,
        result_run_id=row.result_run_id,
        modified_variable=row.modified_variable,
        modified_from=row.modified_from,
        modified_to=row.modified_to,
        created_at=row.created_at,
    )


def _prompt_hash(db: Session, run: Run) -> str:
    cfg = db.get(JudgeConfig, run.judge_config_id)
    return cfg.prompt_hash if cfg else ""


@router.post("/projects/{project_id}/experiments", response_model=ExperimentOut)
def create_experiment(
    project_id: str, body: ExperimentCreate, db: Session = Depends(get_db)
) -> ExperimentOut:
    if not db.get(Project, project_id):
        raise HTTPException(404, "project not found")
    baseline = db.get(Run, body.baseline_run_id)
    result = db.get(Run, body.result_run_id)
    if not baseline or not result:
        raise HTTPException(404, "run not found")
    if baseline.project_id != project_id or result.project_id != project_id:
        raise HTTPException(400, "runs must belong to the project")
    try:
        info = single_variable_change(
            baseline_fingerprint=baseline.fingerprint,
            result_fingerprint=result.fingerprint,
            baseline_rag_version=loads(baseline.rag_version_json, {}),
            result_rag_version=loads(result.rag_version_json, {}),
            baseline_dataset_version_id=baseline.dataset_version_id,
            result_dataset_version_id=result.dataset_version_id,
            baseline_prompt_hash=_prompt_hash(db, baseline),
            result_prompt_hash=_prompt_hash(db, result),
            baseline_spec_hash=baseline.spec_hash,
            result_spec_hash=result.spec_hash,
        )
    except ExperimentError as exc:
        raise HTTPException(400, str(exc)) from exc
    row = Experiment(
        project_id=project_id,
        baseline_run_id=baseline.id,
        result_run_id=result.id,
        modified_variable=info["modified_variable"],
        modified_from=info["modified_from"],
        modified_to=info["modified_to"],
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return _out(row)


@router.get("/experiments/{exp_id}", response_model=ExperimentOut)
def get_experiment(exp_id: str, db: Session = Depends(get_db)) -> ExperimentOut:
    row = db.get(Experiment, exp_id)
    if not row:
        raise HTTPException(404, "experiment not found")
    return _out(row)


@router.get("/projects/{project_id}/experiments", response_model=list[ExperimentOut])
def list_experiments(project_id: str, db: Session = Depends(get_db)) -> list[ExperimentOut]:
    if not db.get(Project, project_id):
        raise HTTPException(404, "project not found")
    rows = (
        db.query(Experiment)
        .filter_by(project_id=project_id)
        .order_by(Experiment.created_at.desc())
        .all()
    )
    return [_out(r) for r in rows]
