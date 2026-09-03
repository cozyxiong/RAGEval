from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.caseutil import apply_case_fields, case_to_out, version_hash
from api.db import get_db
from api.jsonutil import dumps
from api.models import Dataset, DatasetCase, DatasetVersion, Project, utcnow
from api.schemas import (
    CaseIn,
    CaseOut,
    DatasetCreate,
    DatasetOut,
    DatasetVersionOut,
    GenerateIn,
    SampleCalibrationIn,
)
from core.judge import _has_llm_key, _chat_complete
from core.spec import CASE_TYPES
import json
import re

router = APIRouter(prefix="/v1", tags=["datasets"])


def _dataset_or_404(db: Session, dataset_id: str) -> Dataset:
    row = db.get(Dataset, dataset_id)
    if not row:
        raise HTTPException(404, "dataset not found")
    return row


def _version_or_404(db: Session, version_id: str) -> DatasetVersion:
    row = db.get(DatasetVersion, version_id)
    if not row:
        raise HTTPException(404, "dataset version not found")
    return row


def _version_out(db: Session, row: DatasetVersion) -> DatasetVersionOut:
    count = db.query(DatasetCase).filter_by(dataset_version_id=row.id).count()
    return DatasetVersionOut(
        id=row.id,
        dataset_id=row.dataset_id,
        version=row.version,
        confirmed_at=row.confirmed_at,
        hash=row.hash,
        case_count=count,
    )


@router.post("/projects/{project_id}/datasets", response_model=DatasetOut)
def create_dataset(
    project_id: str, body: DatasetCreate, db: Session = Depends(get_db)
) -> DatasetOut:
    if not db.get(Project, project_id):
        raise HTTPException(404, "project not found")
    if body.kind not in ("gold", "calibration"):
        raise HTTPException(400, "kind must be gold or calibration")
    row = Dataset(project_id=project_id, kind=body.kind, name=body.name)
    db.add(row)
    db.flush()
    ver = DatasetVersion(dataset_id=row.id, version=1, hash="")
    db.add(ver)
    db.flush()
    return DatasetOut(id=row.id, project_id=row.project_id, kind=row.kind, name=row.name)


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetOut])
def list_datasets(project_id: str, db: Session = Depends(get_db)) -> list[DatasetOut]:
    if not db.get(Project, project_id):
        raise HTTPException(404, "project not found")
    rows = db.query(Dataset).filter_by(project_id=project_id).all()
    return [DatasetOut(id=r.id, project_id=r.project_id, kind=r.kind, name=r.name) for r in rows]


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: str, db: Session = Depends(get_db)) -> DatasetOut:
    row = _dataset_or_404(db, dataset_id)
    return DatasetOut(id=row.id, project_id=row.project_id, kind=row.kind, name=row.name)


@router.post("/datasets/{dataset_id}/versions", response_model=DatasetVersionOut)
def create_version(dataset_id: str, db: Session = Depends(get_db)) -> DatasetVersionOut:
    ds = _dataset_or_404(db, dataset_id)
    last = (
        db.query(DatasetVersion)
        .filter_by(dataset_id=ds.id)
        .order_by(DatasetVersion.version.desc())
        .first()
    )
    next_v = (last.version + 1) if last else 1
    row = DatasetVersion(dataset_id=ds.id, version=next_v, hash="")
    db.add(row)
    db.flush()
    if last:
        for case in db.query(DatasetCase).filter_by(dataset_version_id=last.id).all():
            db.add(
                DatasetCase(
                    dataset_version_id=row.id,
                    case_id=case.case_id,
                    query=case.query,
                    case_type=case.case_type,
                    expected_behavior=case.expected_behavior,
                    expected_answer=case.expected_answer,
                    expected_source_json=case.expected_source_json,
                    supporting_passage_json=case.supporting_passage_json,
                    relevant_chunks_json=case.relevant_chunks_json,
                    tags_json=case.tags_json,
                )
            )
        db.flush()
    cases = db.query(DatasetCase).filter_by(dataset_version_id=row.id).all()
    row.hash = version_hash(cases)
    db.flush()
    return _version_out(db, row)


@router.get("/datasets/{dataset_id}/versions", response_model=list[DatasetVersionOut])
def list_versions(dataset_id: str, db: Session = Depends(get_db)) -> list[DatasetVersionOut]:
    _dataset_or_404(db, dataset_id)
    rows = (
        db.query(DatasetVersion)
        .filter_by(dataset_id=dataset_id)
        .order_by(DatasetVersion.version.desc())
        .all()
    )
    return [_version_out(db, r) for r in rows]


@router.get("/dataset-versions/{version_id}", response_model=DatasetVersionOut)
def get_version(version_id: str, db: Session = Depends(get_db)) -> DatasetVersionOut:
    return _version_out(db, _version_or_404(db, version_id))


@router.post("/dataset-versions/{version_id}/cases", response_model=list[CaseOut])
def upsert_cases(
    version_id: str, body: list[CaseIn], db: Session = Depends(get_db)
) -> list[CaseOut]:
    ver = _version_or_404(db, version_id)
    if ver.confirmed_at is not None:
        raise HTTPException(400, "confirmed version is immutable; create a new version")
    out: list[CaseOut] = []
    for item in body:
        existing = (
            db.query(DatasetCase)
            .filter_by(dataset_version_id=ver.id, case_id=item.case_id)
            .first()
        )
        if existing:
            apply_case_fields(existing, item)
            row = existing
        else:
            row = DatasetCase(dataset_version_id=ver.id, case_id=item.case_id)
            apply_case_fields(row, item)
            db.add(row)
        db.flush()
        out.append(case_to_out(row))
    cases = db.query(DatasetCase).filter_by(dataset_version_id=ver.id).all()
    ver.hash = version_hash(cases)
    db.flush()
    return out


@router.get("/dataset-versions/{version_id}/cases", response_model=list[CaseOut])
def list_cases(version_id: str, db: Session = Depends(get_db)) -> list[CaseOut]:
    _version_or_404(db, version_id)
    rows = db.query(DatasetCase).filter_by(dataset_version_id=version_id).all()
    return [case_to_out(r) for r in rows]


def _template_drafts(hints: list[str]) -> list[CaseIn]:
    drafts: list[CaseIn] = []
    templates = [
        ("answerable", "answer"),
        ("unanswerable", "refuse"),
        ("ambiguous", "clarify"),
    ]
    if not hints:
        hints = ["总部在哪里", "营收是多少", "办公室在哪"]
    for i, hint in enumerate(hints):
        ctype, behav = templates[i % 3]
        drafts.append(
            CaseIn(
                case_id=f"draft-{i+1:03d}",
                query=hint,
                case_type=ctype,  # type: ignore[arg-type]
                expected_behavior=behav,  # type: ignore[arg-type]
                expected_answer="",
                tags=["draft", "needs-review"],
            )
        )
    return drafts


def _llm_drafts(hints: list[str]) -> list[CaseIn]:
    prompt = (
        "根据 hints 起草 Closed-domain RAG 黄金集 cases。"
        "覆盖 answerable/unanswerable/ambiguous。"
        "只输出 JSON 数组，元素含 case_id,query,case_type,expected_behavior,"
        "expected_answer,expected_source,supporting_passage,tags。"
        f"hints={json.dumps(hints, ensure_ascii=False)}"
    )
    raw = _chat_complete(
        [
            {"role": "system", "content": "You output JSON only."},
            {"role": "user", "content": prompt},
        ],
        model=__import__("os").environ.get("JUDGE_MODEL") or "gpt-4.1-mini",
    )
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text)
        text = re.sub(r"```$", "", text).strip()
    data = json.loads(text)
    out: list[CaseIn] = []
    for i, item in enumerate(data):
        out.append(
            CaseIn(
                case_id=item.get("case_id") or f"draft-{i+1:03d}",
                query=item.get("query") or "",
                case_type=item.get("case_type") or "answerable",
                expected_behavior=item.get("expected_behavior") or "answer",
                expected_answer=item.get("expected_answer") or "",
                expected_source=item.get("expected_source") or [],
                supporting_passage=item.get("supporting_passage") or [],
                tags=list(set((item.get("tags") or []) + ["draft", "needs-review"])),
            )
        )
    return out


@router.post("/dataset-versions/{version_id}/generate", response_model=list[CaseOut])
def generate_cases(
    version_id: str, body: GenerateIn, db: Session = Depends(get_db)
) -> list[CaseOut]:
    ver = _version_or_404(db, version_id)
    if ver.confirmed_at is not None:
        raise HTTPException(400, "confirmed version is immutable")
    drafts = _template_drafts(body.hints)
    if _has_llm_key() and body.hints:
        try:
            drafts = _llm_drafts(body.hints)
        except Exception:
            drafts = _template_drafts(body.hints)
    return upsert_cases(version_id, drafts, db)


@router.post("/dataset-versions/{version_id}/confirm", response_model=DatasetVersionOut)
def confirm_version(version_id: str, db: Session = Depends(get_db)) -> DatasetVersionOut:
    ver = _version_or_404(db, version_id)
    cases = db.query(DatasetCase).filter_by(dataset_version_id=ver.id).all()
    if not cases:
        raise HTTPException(400, "cannot confirm empty dataset version")
    types = {c.case_type for c in cases}
    missing = [t for t in CASE_TYPES if t not in types]
    if missing:
        raise HTTPException(400, f"gold set must cover case_types {CASE_TYPES}, missing {missing}")
    for c in cases:
        if "needs-review" in (c.tags_json or ""):
            # still allow confirm after human edited; only block pure drafts if query empty
            if not c.query.strip():
                raise HTTPException(400, f"case {c.case_id} has empty query")
    ver.hash = version_hash(cases)
    ver.confirmed_at = utcnow()
    db.flush()
    return _version_out(db, ver)


@router.post("/dataset-versions/{version_id}/sample-calibration", response_model=DatasetVersionOut)
def sample_calibration(
    version_id: str, body: SampleCalibrationIn, db: Session = Depends(get_db)
) -> DatasetVersionOut:
    ver = _version_or_404(db, version_id)
    if ver.confirmed_at is None:
        raise HTTPException(400, "sample calibration from a confirmed gold version only")
    ds = _dataset_or_404(db, ver.dataset_id)
    if ds.kind != "gold":
        raise HTTPException(400, "source dataset must be gold")
    cases = db.query(DatasetCase).filter_by(dataset_version_id=ver.id).all()
    grouped: dict[str, list[DatasetCase]] = defaultdict(list)
    for c in cases:
        grouped[c.case_type].append(c)
    sampled: list[DatasetCase] = []
    for ctype in CASE_TYPES:
        bucket = grouped.get(ctype) or []
        sampled.extend(bucket[: max(body.per_type, 0)])
    if not sampled:
        raise HTTPException(400, "no cases to sample")
    cal_ds = Dataset(project_id=ds.project_id, kind="calibration", name=body.name)
    db.add(cal_ds)
    db.flush()
    cal_ver = DatasetVersion(dataset_id=cal_ds.id, version=1, hash="")
    db.add(cal_ver)
    db.flush()
    for src in sampled:
        db.add(
            DatasetCase(
                dataset_version_id=cal_ver.id,
                case_id=src.case_id,
                query=src.query,
                case_type=src.case_type,
                expected_behavior=src.expected_behavior,
                expected_answer=src.expected_answer,
                expected_source_json=src.expected_source_json,
                supporting_passage_json=src.supporting_passage_json,
                relevant_chunks_json=src.relevant_chunks_json,
                tags_json=dumps(["calibration"]),
            )
        )
    db.flush()
    cal_cases = db.query(DatasetCase).filter_by(dataset_version_id=cal_ver.id).all()
    cal_ver.hash = version_hash(cal_cases)
    cal_ver.confirmed_at = utcnow()
    db.flush()
    return _version_out(db, cal_ver)
