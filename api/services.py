from __future__ import annotations

from sqlalchemy.orm import Session

from api.jsonutil import dumps, loads
from api.models import JudgeCalibration, JudgeConfig, Project, Run, utcnow
from api.schemas import RagVersionIn, RunOut
from core.judge import JUDGE_SYSTEM_PROMPT, prompt_hash
from core.spec import parse_spec
from core.version import fingerprint, normalize_rag_version


def latest_judge_status(db: Session, project_id: str, judge_config_id: str | None = None) -> str:
    q = db.query(JudgeCalibration).filter_by(project_id=project_id)
    if judge_config_id:
        q = q.filter_by(judge_config_id=judge_config_id)
    row = q.order_by(JudgeCalibration.created_at.desc()).first()
    return row.status if row else "not_calibrated"


def get_or_create_judge_config(
    db: Session,
    project: Project,
    judge_config_id: str | None = None,
    provider: str = "builtin",
    model: str | None = None,
    prompt_text: str | None = None,
) -> JudgeConfig:
    if judge_config_id:
        cfg = db.get(JudgeConfig, judge_config_id)
        if not cfg or cfg.project_id != project.id:
            raise ValueError("judge config not found")
        return cfg
    existing = (
        db.query(JudgeConfig)
        .filter_by(project_id=project.id, provider=provider)
        .order_by(JudgeConfig.id)
        .first()
    )
    if existing and not prompt_text:
        return existing
    spec = parse_spec(loads(project.spec_json, {}))
    text = prompt_text or JUDGE_SYSTEM_PROMPT
    cfg = JudgeConfig(
        project_id=project.id,
        provider=provider,
        model=model or spec.judge.model,
        prompt_text=text,
        prompt_hash=prompt_hash(text),
    )
    db.add(cfg)
    db.flush()
    return cfg


def run_to_out(row: Run) -> RunOut:
    return RunOut(
        id=row.id,
        project_id=row.project_id,
        dataset_version_id=row.dataset_version_id,
        judge_config_id=row.judge_config_id,
        spec=loads(row.spec_json, {}),
        spec_hash=row.spec_hash,
        rag_version=loads(row.rag_version_json, {}),
        fingerprint=row.fingerprint,
        status=row.status,
        total=row.total,
        done=row.done,
        pass_count=row.pass_count,
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def make_run(
    db: Session,
    project: Project,
    dataset_version_id: str,
    judge_cfg: JudgeConfig,
    rag_version: RagVersionIn | dict,
    total: int,
) -> Run:
    spec = parse_spec(loads(project.spec_json, {}))
    spec_dict = spec.to_json_dict()
    spec_h = spec.spec_hash()
    rv = normalize_rag_version(rag_version.model_dump() if hasattr(rag_version, "model_dump") else rag_version)
    fp = fingerprint(rv, dataset_version_id, judge_cfg.prompt_hash, spec_h)
    row = Run(
        project_id=project.id,
        dataset_version_id=dataset_version_id,
        judge_config_id=judge_cfg.id,
        spec_json=dumps(spec_dict),
        spec_hash=spec_h,
        rag_version_json=dumps(rv),
        fingerprint=fp,
        status="PENDING",
        total=total,
        done=0,
        pass_count=0,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return row
