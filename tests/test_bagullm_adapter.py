from __future__ import annotations

from adapters.bagullm import app as bagullm_app
from adapters.bagullm import sources_to_chunks, strip_think, wrap_query
from core.spec import ALLOWED_META_KEYS


def test_bagullm_adapter_exposes_eval_contract() -> None:
    paths = {getattr(r, "path", None) for r in bagullm_app.routes}
    assert "/eval/rag" in paths
    assert "/health" in paths


def test_sources_to_chunks_maps_anythingllm_shape() -> None:
    sources = [
        {
            "id": "vec-1",
            "title": "java-generics.md",
            "chunk": "Generics were added in Java 5.",
            "score": 0.81,
        },
        {
            "title": "collections.txt",
            "text": "ArrayList implements List.",
        },
    ]
    chunks = sources_to_chunks(sources)
    assert chunks[0]["chunk_id"] == "vec-1"
    assert chunks[0]["doc_id"] == "java-generics.md"
    assert "Java 5" in chunks[0]["text"]
    assert chunks[0]["rank"] == 1
    assert chunks[0]["score"] == 0.81
    assert chunks[1]["rank"] == 2
    assert chunks[1]["doc_id"] == "collections.txt"
    for ch in chunks:
        for key in ("chunk_id", "doc_id", "text", "rank", "score"):
            assert key in ch


def test_wrap_query_closed_refuse_is_single_prompt_variable() -> None:
    q = "火星工厂现在有多少员工？"
    assert wrap_query(q, "plain") == q
    wrapped = wrap_query(q, "closed-refuse-v2")
    assert wrapped.startswith("【评测约束】")
    assert wrapped.endswith(q)
    assert "明确拒绝" in wrapped
    assert "追问澄清" in wrapped


def test_strip_think_keeps_visible_answer() -> None:
    raw = "<think>hidden</think>\nRAG 的全称是检索增强生成。"
    assert "hidden" not in strip_think(raw)
    assert "检索增强生成" in strip_think(raw)


def test_eval_response_meta_keys_are_allowed() -> None:
    meta = {"latency_ms": 12, "model": "bagullm", "request_id": "abc"}
    assert set(meta) <= ALLOWED_META_KEYS
