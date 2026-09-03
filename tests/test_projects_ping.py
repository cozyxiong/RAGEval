from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_list_get_patch_project(api_client: TestClient) -> None:
    created = api_client.post(
        "/v1/projects",
        json={"name": "demo", "adapter_url": "http://127.0.0.1:8100"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "demo"
    assert body["adapter_url"] == "http://127.0.0.1:8100"
    assert body["spec"]["pass_gate"]["faithfulness"] == 0.85
    pid = body["id"]

    listed = api_client.get("/v1/projects")
    assert listed.status_code == 200
    assert any(p["id"] == pid for p in listed.json())

    got = api_client.get(f"/v1/projects/{pid}")
    assert got.status_code == 200
    assert got.json()["id"] == pid

    patched = api_client.patch(
        f"/v1/projects/{pid}",
        json={"name": "demo-2", "spec": {"k": 4, "retrieval_level": 1}},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "demo-2"
    assert patched.json()["spec"]["k"] == 4


def test_adapter_ping_via_api(api_client: TestClient, live_mock_url: str) -> None:
    created = api_client.post(
        "/v1/projects",
        json={"name": "ping-me", "adapter_url": live_mock_url},
    )
    pid = created.json()["id"]
    ping = api_client.post(f"/v1/projects/{pid}/adapter/ping")
    assert ping.status_code == 200, ping.text
    assert ping.json()["ok"] is True


def test_health(api_client: TestClient) -> None:
    resp = api_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
