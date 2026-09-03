from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_datasets import CASES
from workers.evaluation_worker import process_run


def _gold_run(client: TestClient, adapter_url: str, spec: dict | None = None) -> tuple[str, str, str]:
    body: dict = {"name": "rep", "adapter_url": adapter_url}
    if spec:
        body["spec"] = spec
    pid = client.post("/v1/projects", json=body).json()["id"]
    ds = client.post(
        f"/v1/projects/{pid}/datasets", json={"kind": "gold", "name": "gold"}
    ).json()
    vid = client.get(f"/v1/datasets/{ds['id']}/versions").json()[0]["id"]
    client.post(f"/v1/dataset-versions/{vid}/cases", json=CASES)
    client.post(f"/v1/dataset-versions/{vid}/confirm")
    return pid, vid, ds["id"]


def test_level1_report_has_required_fields_and_no_recall(
    api_client: TestClient, live_mock_url: str
) -> None:
    pid, vid, _ = _gold_run(api_client, live_mock_url)
    rid = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "rag_version": {"kb": "a"}},
    ).json()["id"]
    process_run(rid)
    report = api_client.get(f"/v1/runs/{rid}/report")
    assert report.status_code == 200, report.text
    body = report.json()
    for key in (
        "fingerprint",
        "pass_rate",
        "n",
        "means",
        "retrieval_level",
        "retrieval",
        "slices",
        "primary_cause_dist",
        "judge_status",
    ):
        assert key in body, key
    assert body["n"] == 3
    assert body["retrieval_level"] == 1
    assert "recall" not in body["retrieval"]
    assert "expected_source_hit" in body["retrieval"]
    assert "passage_hit" in body["retrieval"]
    assert 0 <= body["pass_rate"] <= 1


def test_diff_and_single_variable_experiment(
    api_client: TestClient, live_mock_url: str
) -> None:
    pid, vid, _ = _gold_run(api_client, live_mock_url)
    r1 = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "rag_version": {"kb": "a", "rerank": "none"}},
    ).json()
    r2 = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "rag_version": {"kb": "a", "rerank": "bge"}},
    ).json()
    r3 = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "rag_version": {"kb": "b", "rerank": "bge"}},
    ).json()
    process_run(r1["id"])
    process_run(r2["id"])
    diff = api_client.get(f"/v1/runs/{r1['id']}/diff/{r2['id']}")
    assert diff.status_code == 200, diff.text
    dbody = diff.json()
    assert "metric_delta" in dbody
    assert "fixed_fail_count" in dbody
    assert "new_fail_count" in dbody
    assert dbody["fingerprint_diff"]["changed"] is True

    ok = api_client.post(
        f"/v1/projects/{pid}/experiments",
        json={"baseline_run_id": r1["id"], "result_run_id": r2["id"]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["modified_variable"] == "rerank"
    assert ok.json()["modified_from"] == "none"
    assert ok.json()["modified_to"] == "bge"

    bad = api_client.post(
        f"/v1/projects/{pid}/experiments",
        json={"baseline_run_id": r1["id"], "result_run_id": r3["id"]},
    )
    assert bad.status_code == 400
    assert "exactly one" in bad.json()["detail"]


def test_calibration_confusion_and_use_as_gate(
    api_client: TestClient, live_mock_url: str
) -> None:
    spec = {
        "calibration": {"min_n": 2, "min_accuracy": 0.5, "max_false_pass": 0.5},
        "retrieval_level": 1,
    }
    pid, vid, _ = _gold_run(api_client, live_mock_url, spec=spec)
    rid = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "rag_version": {"kb": "a"}},
    ).json()["id"]
    process_run(rid)
    cases = api_client.get(f"/v1/runs/{rid}/cases").json()
    for c in cases:
        label = c["judge_label"] or "fail"
        patched = api_client.patch(
            f"/v1/runs/{rid}/cases/{c['case_id']}/human",
            json={"human_label": label, "human_reason": "agree"},
        )
        assert patched.status_code == 200, patched.text
    run = api_client.get(f"/v1/runs/{rid}").json()
    cfg_id = run["judge_config_id"]
    cal = api_client.post(
        f"/v1/judge-configs/{cfg_id}/calibrate",
        json={"run_id": rid},
    )
    assert cal.status_code == 200, cal.text
    body = cal.json()
    assert body["n"] == 3
    assert body["accuracy"] == 1.0
    assert body["status"] == "calibrated"
    assert body["confusion"]["tp"] + body["confusion"]["tn"] == 3
    status = api_client.get(f"/v1/projects/{pid}/judge-status")
    assert status.json()["status"] == "calibrated"

    gated = api_client.post(
        f"/v1/projects/{pid}/runs",
        json={"dataset_version_id": vid, "use_as_gate": True, "rag_version": {"kb": "b"}},
    )
    assert gated.status_code == 200, gated.text
