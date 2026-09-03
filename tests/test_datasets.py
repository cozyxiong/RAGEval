from __future__ import annotations

from fastapi.testclient import TestClient


def _project(client: TestClient) -> str:
    resp = client.post(
        "/v1/projects",
        json={"name": "ds", "adapter_url": "http://127.0.0.1:8100"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


CASES = [
    {
        "case_id": "g-1",
        "query": "总部在哪里？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "新加坡",
        "expected_source": ["doc-hq"],
        "supporting_passage": ["总部设在新加坡"],
        "relevant_chunks": [{"chunk_id": "c-hq-1", "doc_id": "doc-hq", "label": 2}],
        "tags": ["hq"],
    },
    {
        "case_id": "g-2",
        "query": "2024营收多少？",
        "case_type": "unanswerable",
        "expected_behavior": "refuse",
        "expected_answer": "",
        "expected_source": [],
        "supporting_passage": [],
        "relevant_chunks": [],
        "tags": ["finance"],
    },
    {
        "case_id": "g-3",
        "query": "办公室在哪？",
        "case_type": "ambiguous",
        "expected_behavior": "clarify",
        "expected_answer": "",
        "expected_source": ["doc-hq"],
        "supporting_passage": [],
        "relevant_chunks": [],
        "tags": ["office"],
    },
]


def test_dataset_crud_generate_confirm_and_sample(api_client: TestClient) -> None:
    pid = _project(api_client)
    created = api_client.post(
        f"/v1/projects/{pid}/datasets",
        json={"kind": "gold", "name": "gold-v1"},
    )
    assert created.status_code == 200, created.text
    ds_id = created.json()["id"]
    versions = api_client.get(f"/v1/datasets/{ds_id}/versions")
    assert versions.status_code == 200
    vid = versions.json()[0]["id"]
    assert versions.json()[0]["confirmed_at"] is None

    written = api_client.post(f"/v1/dataset-versions/{vid}/cases", json=CASES)
    assert written.status_code == 200, written.text
    assert len(written.json()) == 3

    listed = api_client.get(f"/v1/dataset-versions/{vid}/cases")
    assert len(listed.json()) == 3

    gen = api_client.post(
        f"/v1/dataset-versions/{vid}/generate",
        json={"hints": ["产品是什么"]},
    )
    assert gen.status_code == 200
    assert any(c["case_id"].startswith("draft-") for c in gen.json())

    # drafts include needs-review; confirm still allowed if queries present,
    # but we replace with the three typed cases by creating a new version.
    new_ver = api_client.post(f"/v1/datasets/{ds_id}/versions")
    assert new_ver.status_code == 200
    vid2 = new_ver.json()["id"]
    # cloned cases exist; rewrite the three gold cases on a clean version
    # by posting onto a brand-new empty dataset
    created2 = api_client.post(
        f"/v1/projects/{pid}/datasets",
        json={"kind": "gold", "name": "gold-clean"},
    )
    vid_clean = api_client.get(f"/v1/datasets/{created2.json()['id']}/versions").json()[0]["id"]
    api_client.post(f"/v1/dataset-versions/{vid_clean}/cases", json=CASES)
    confirmed = api_client.post(f"/v1/dataset-versions/{vid_clean}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["confirmed_at"] is not None
    assert confirmed.json()["hash"]

    immutable = api_client.post(
        f"/v1/dataset-versions/{vid_clean}/cases",
        json=CASES,
    )
    assert immutable.status_code == 400

    sampled = api_client.post(
        f"/v1/dataset-versions/{vid_clean}/sample-calibration",
        json={"per_type": 1, "name": "cal-1"},
    )
    assert sampled.status_code == 200, sampled.text
    assert sampled.json()["confirmed_at"] is not None
    assert sampled.json()["case_count"] == 3


def test_unconfirmed_run_returns_400(api_client: TestClient) -> None:
    pid = _project(api_client)
    ds = api_client.post(
        f"/v1/projects/{pid}/datasets", json={"kind": "gold", "name": "g"}
    ).json()
    vid = api_client.get(f"/v1/datasets/{ds['id']}/versions").json()[0]["id"]
    api_client.post(f"/v1/dataset-versions/{vid}/cases", json=CASES)
    run = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "rag_version": {"kb": "v1"}},
    )
    assert run.status_code == 400, run.text
    assert "not confirmed" in run.json()["detail"]

    api_client.post(f"/v1/dataset-versions/{vid}/confirm")
    ok = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "rag_version": {"kb": "v1"}},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "PENDING"
    assert ok.json()["total"] == 3
    assert ok.json()["fingerprint"]


def test_use_as_gate_without_calibration_400(api_client: TestClient) -> None:
    pid = _project(api_client)
    ds = api_client.post(
        f"/v1/projects/{pid}/datasets", json={"kind": "gold", "name": "g"}
    ).json()
    vid = api_client.get(f"/v1/datasets/{ds['id']}/versions").json()[0]["id"]
    api_client.post(f"/v1/dataset-versions/{vid}/cases", json=CASES)
    api_client.post(f"/v1/dataset-versions/{vid}/confirm")
    run = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={
            "dataset_version_id": vid,
            "use_as_gate": True,
            "rag_version": {"kb": "v1"},
        },
    )
    assert run.status_code == 400
    assert "calibrated" in run.json()["detail"]
