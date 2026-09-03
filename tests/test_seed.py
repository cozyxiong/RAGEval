from __future__ import annotations

from fastapi.testclient import TestClient

from api.models import DatasetCase, DatasetVersion
from api.seed import DEMO_CASES, seed_demo
from api.db import SessionLocal


def test_seed_demo_has_eight_typed_cases_and_completed_run(
    api_client: TestClient, live_mock_url: str, db_path
) -> None:
    assert len(DEMO_CASES) >= 8
    types = {c["case_type"] for c in DEMO_CASES}
    assert types == {"answerable", "unanswerable", "ambiguous"}
    info = seed_demo(adapter_url=live_mock_url, process=True)
    assert info["run_id"]
    db = SessionLocal()
    try:
        ver = db.get(DatasetVersion, info["dataset_version_id"])
        assert ver is not None
        assert ver.confirmed_at is not None
        n = db.query(DatasetCase).filter_by(dataset_version_id=ver.id).count()
        assert n >= 8
    finally:
        db.close()
    run = api_client.get(f"/v1/runs/{info['run_id']}").json()
    assert run["status"] == "COMPLETED"
    report = api_client.get(f"/v1/runs/{info['run_id']}/report").json()
    assert report["n"] >= 8
    assert "fingerprint" in report
    assert "pass_rate" in report
    assert report["retrieval_level"] == 1
    assert "recall" not in report["retrieval"]
