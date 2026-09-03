from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db
from api.models import CaseResult, JudgeCalibration, JudgeConfig, Project, Run, utcnow
from api.schemas import (
    CalibrateIn,
    JudgeCalibrationOut,
    JudgeConfigCreate,
    JudgeConfigOut,
)
from api.services import get_or_create_judge_config, latest_judge_status
from core.metrics import calibration_rates
from core.spec import parse_spec
from api.jsonutil import loads

router = APIRouter(prefix="/v1", tags=["judge"])


def _cfg_out(row: JudgeConfig) -> JudgeConfigOut:
    return JudgeConfigOut(
        id=row.id,
        project_id=row.project_id,
        provider=row.provider,
        model=row.model,
        prompt_hash=row.prompt_hash,
        prompt_text=row.prompt_text,
    )


@router.post("/projects/{project_id}/judge-configs", response_model=JudgeConfigOut)
def create_judge_config(
    project_id: str, body: JudgeConfigCreate, db: Session = Depends(get_db)
) -> JudgeConfigOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    cfg = get_or_create_judge_config(
        db,
        project,
        provider=body.provider,
        model=body.model,
        prompt_text=body.prompt_text or None,
    )
    if body.prompt_text:
        from core.judge import prompt_hash

        cfg.prompt_text = body.prompt_text
        cfg.prompt_hash = prompt_hash(body.prompt_text)
        if body.model:
            cfg.model = body.model
        db.flush()
    return _cfg_out(cfg)


@router.get("/projects/{project_id}/judge-configs", response_model=list[JudgeConfigOut])
def list_judge_configs(project_id: str, db: Session = Depends(get_db)) -> list[JudgeConfigOut]:
    if not db.get(Project, project_id):
        raise HTTPException(404, "project not found")
    rows = db.query(JudgeConfig).filter_by(project_id=project_id).all()
    return [_cfg_out(r) for r in rows]


@router.get("/projects/{project_id}/judge-status")
def judge_status(project_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Project, project_id):
        raise HTTPException(404, "project not found")
    latest = (
        db.query(JudgeCalibration)
        .filter_by(project_id=project_id)
        .order_by(JudgeCalibration.created_at.desc())
        .first()
    )
    return {
        "status": latest.status if latest else "not_calibrated",
        "calibration": (
            JudgeCalibrationOut(
                id=latest.id,
                project_id=latest.project_id,
                judge_config_id=latest.judge_config_id,
                dataset_version_id=latest.dataset_version_id,
                n=latest.n,
                accuracy=latest.accuracy,
                false_pass_rate=latest.false_pass_rate,
                false_fail_rate=latest.false_fail_rate,
                status=latest.status,
                created_at=latest.created_at,
            ).model_dump()
            if latest
            else None
        ),
    }


@router.post("/judge-configs/{config_id}/calibrate", response_model=JudgeCalibrationOut)
def calibrate(config_id: str, body: CalibrateIn, db: Session = Depends(get_db)) -> JudgeCalibrationOut:
    cfg = db.get(JudgeConfig, config_id)
    if not cfg:
        raise HTTPException(404, "judge config not found")
    run = db.get(Run, body.run_id)
    if not run or run.project_id != cfg.project_id:
        raise HTTPException(404, "run not found")
    if run.judge_config_id != cfg.id:
        raise HTTPException(400, "run was not produced by this judge config")
    results = db.query(CaseResult).filter_by(run_id=run.id).all()
    pairs = [
        (r.judge_label, r.human_label)
        for r in results
        if r.judge_label in {"pass", "fail"} and r.human_label in {"pass", "fail"}
    ]
    project = db.get(Project, cfg.project_id)
    spec = parse_spec(loads(project.spec_json, {}) if project else {})
    rates = calibration_rates(pairs, spec)
    row = JudgeCalibration(
        project_id=cfg.project_id,
        judge_config_id=cfg.id,
        dataset_version_id=run.dataset_version_id,
        n=rates["n"],
        accuracy=rates["accuracy"],
        false_pass_rate=rates["false_pass_rate"],
        false_fail_rate=rates["false_fail_rate"],
        status=rates["status"],
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return JudgeCalibrationOut(
        id=row.id,
        project_id=row.project_id,
        judge_config_id=row.judge_config_id,
        dataset_version_id=row.dataset_version_id,
        n=row.n,
        accuracy=row.accuracy,
        false_pass_rate=row.false_pass_rate,
        false_fail_rate=row.false_fail_rate,
        status=row.status,
        created_at=row.created_at,
        confusion={"tp": rates["tp"], "tn": rates["tn"], "fp": rates["fp"], "fn": rates["fn"]},
    )


@router.get("/judge-calibrations/{cal_id}", response_model=JudgeCalibrationOut)
def get_calibration(cal_id: str, db: Session = Depends(get_db)) -> JudgeCalibrationOut:
    row = db.get(JudgeCalibration, cal_id)
    if not row:
        raise HTTPException(404, "calibration not found")
    return JudgeCalibrationOut(
        id=row.id,
        project_id=row.project_id,
        judge_config_id=row.judge_config_id,
        dataset_version_id=row.dataset_version_id,
        n=row.n,
        accuracy=row.accuracy,
        false_pass_rate=row.false_pass_rate,
        false_fail_rate=row.false_fail_rate,
        status=row.status,
        created_at=row.created_at,
    )
