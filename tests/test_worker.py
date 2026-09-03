from __future__ import annotations

import os

from fastapi.testclient import TestClient

from tests.test_datasets import CASES


def test_worker_completes_pending_mock_run(
    api_client: TestClient, live_mock_url: str
) -> None:
    os.environ.pop("OPENAI_API_KEY", None)
    created = api_client.post(
        "/v1/projects",
        json={"name": "worker-demo", "adapter_url": live_mock_url},
    )
    pid = created.json()["id"]
    ds = api_client.post(
        f"/v1/projects/{pid}/datasets", json={"kind": "gold", "name": "gold"}
    ).json()
    vid = api_client.get(f"/v1/datasets/{ds['id']}/versions").json()[0]["id"]
    assert api_client.post(f"/v1/dataset-versions/{vid}/cases", json=CASES).status_code == 200
    assert api_client.post(f"/v1/dataset-versions/{vid}/confirm").status_code == 200
    run = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "rag_version": {"kb": "mock", "generator": "mock"}},
    )
    assert run.status_code == 200, run.text
    rid = run.json()["id"]
    assert run.json()["status"] == "PENDING"

    from workers.evaluation_worker import process_run

    process_run(rid)

    got = api_client.get(f"/v1/runs/{rid}")
    assert got.status_code == 200
    body = got.json()
    assert body["status"] == "COMPLETED"
    assert body["done"] == body["total"] == 3
    assert body["pass_count"] >= 0
    cases = api_client.get(f"/v1/runs/{rid}/cases").json()
    assert len(cases) == 3
    ids = {c["case_id"] for c in cases}
    assert ids == {"g-1", "g-2", "g-3"}
    by_id = {c["case_id"]: c for c in cases}
    hq = by_id["g-1"]
    assert hq["judge_label"] == "pass", (
        f"Singapore HQ must pass default gates, got label={hq['judge_label']} "
        f"relevancy={hq['answer_relevancy']} faith={hq['faithfulness']} "
        f"complete={hq['completeness']} behavior={hq['evaluated_behavior']}"
    )
    for c in cases:
        assert c["judge_label"] in {"pass", "fail"}
        assert c["error"] is None
        retrieval = c["retrieval_metrics"] or {}
        assert "recall" not in retrieval
        assert "expected_source_hit" in retrieval
        assert "passage_hit" in retrieval
        assert c["actual_answer"]
        assert c["latency_ms"] is not None


def test_worker_records_per_case_error_without_aborting(
    api_client: TestClient,
) -> None:
    created = api_client.post(
        "/v1/projects",
        json={"name": "bad-adapter", "adapter_url": "http://127.0.0.1:1"},
    )
    pid = created.json()["id"]
    ds = api_client.post(
        f"/v1/projects/{pid}/datasets", json={"kind": "gold", "name": "gold"}
    ).json()
    vid = api_client.get(f"/v1/datasets/{ds['id']}/versions").json()[0]["id"]
    api_client.post(f"/v1/dataset-versions/{vid}/cases", json=CASES)
    api_client.post(f"/v1/dataset-versions/{vid}/confirm")
    rid = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "rag_version": {"kb": "x"}},
    ).json()["id"]
    from workers.evaluation_worker import process_run

    process_run(rid)
    body = api_client.get(f"/v1/runs/{rid}").json()
    assert body["status"] == "COMPLETED"
    assert body["done"] == 3
    cases = api_client.get(f"/v1/runs/{rid}/cases").json()
    assert all(c["judge_label"] == "fail" for c in cases)
    assert all(c["error"] for c in cases)
