from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db import get_db
from api.models import Run
from api.reporting import fail_ids, report_for_run
from core.regression import diff_reports

router = APIRouter(prefix="/v1", tags=["reports"])


@router.get("/runs/{run_id}/report")
def get_report(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return report_for_run(db, run)


@router.get("/runs/{run_id}/diff/{other_id}")
def get_diff(run_id: str, other_id: str, db: Session = Depends(get_db)) -> dict:
    old = db.get(Run, run_id)
    new = db.get(Run, other_id)
    if not old or not new:
        raise HTTPException(404, "run not found")
    old_report = report_for_run(db, old)
    new_report = report_for_run(db, new)
    return diff_reports(
        old_report,
        new_report,
        old_fail_ids=fail_ids(db, old),
        new_fail_ids=fail_ids(db, new),
        old_fingerprint=old.fingerprint,
        new_fingerprint=new.fingerprint,
    )
