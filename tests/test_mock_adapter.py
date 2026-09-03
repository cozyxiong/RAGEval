from __future__ import annotations

from fastapi.testclient import TestClient

from adapters.mock_server import app as mock_app
from core.adapter import AdapterClient, AdapterResponse
from core.spec import ALLOWED_META_KEYS


def test_singapore_hq_returns_answer_chunk_and_latency() -> None:
    client = TestClient(mock_app)
    resp = client.post("/eval/rag", json={"query": "Acme Robotics 总部在哪里？"})
    assert resp.status_code == 200
    body = resp.json()
    assert "新加坡" in body["actual_answer"] or "Singapore" in body["actual_answer"]
    assert body["retrieved_chunks"], "must return at least one chunk"
    chunk = body["retrieved_chunks"][0]
    for key in ("chunk_id", "doc_id", "text", "rank", "score"):
        assert key in chunk
    assert "新加坡" in chunk["text"] or "Singapore" in chunk["text"]
    assert "latency_ms" in body["meta"]
    assert body["meta"]["latency_ms"] >= 0
    extra = set(body["meta"]) - ALLOWED_META_KEYS
    assert not extra, extra


def test_unknown_query_refuses() -> None:
    client = TestClient(mock_app)
    resp = client.post("/eval/rag", json={"query": "2024年火星工厂的营收是多少？"})
    assert resp.status_code == 200
    body = resp.json()
    answer = body["actual_answer"]
    assert "无法" in answer or "不知道" in answer or "拒" in answer
    assert "latency_ms" in body["meta"]


def test_health() -> None:
    client = TestClient(mock_app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_adapter_client_against_live_mock(live_mock_url: str) -> None:
    client = AdapterClient(live_mock_url, timeout_ms=5000)
    ping = client.ping()
    assert ping["ok"] is True
    result = client.eval_rag("总部在新加坡吗？")
    assert isinstance(result, AdapterResponse)
    assert result.retrieved_chunks
    assert result.meta.latency_ms >= 0
    assert "新加坡" in result.actual_answer or "Singapore" in result.actual_answer
    refused = client.eval_rag("CEO 年薪多少")
    assert "无法" in refused.actual_answer
