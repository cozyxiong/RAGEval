from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db
from api.jsonutil import dumps, loads
from api.models import Project, utcnow
from api.schemas import ProjectCreate, ProjectOut, ProjectPatch
from core.adapter import AdapterClient, AdapterError
from core.spec import DEFAULT_SPEC, parse_spec

router = APIRouter(prefix="/v1", tags=["projects"])


def _out(row: Project) -> ProjectOut:
    return ProjectOut(
        id=row.id,
        name=row.name,
        adapter_url=row.adapter_url,
        product_mode=row.product_mode,
        spec=loads(row.spec_json, {}),
        created_at=row.created_at,
    )


@router.post("/projects", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    spec = parse_spec(body.spec)
    row = Project(
        name=body.name,
        adapter_url=body.adapter_url.rstrip("/"),
        product_mode=body.product_mode,
        spec_json=dumps(spec.to_json_dict()),
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return _out(row)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    rows = db.query(Project).order_by(Project.created_at.desc()).all()
    return [_out(r) for r in rows]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    row = db.get(Project, project_id)
    if not row:
        raise HTTPException(404, "project not found")
    return _out(row)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def patch_project(
    project_id: str, body: ProjectPatch, db: Session = Depends(get_db)
) -> ProjectOut:
    row = db.get(Project, project_id)
    if not row:
        raise HTTPException(404, "project not found")
    if body.name is not None:
        row.name = body.name
    if body.adapter_url is not None:
        row.adapter_url = body.adapter_url.rstrip("/")
    if body.product_mode is not None:
        row.product_mode = body.product_mode
    if body.spec is not None:
        row.spec_json = dumps(parse_spec(body.spec).to_json_dict())
    db.flush()
    return _out(row)


@router.post("/projects/{project_id}/adapter/ping")
def ping_adapter(project_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(Project, project_id)
    if not row:
        raise HTTPException(404, "project not found")
    spec = parse_spec(loads(row.spec_json, DEFAULT_SPEC.to_json_dict()))
    client = AdapterClient(row.adapter_url, timeout_ms=spec.adapter.timeout_ms)
    try:
        return client.ping()
    except AdapterError as exc:
        raise HTTPException(502, str(exc)) from exc
