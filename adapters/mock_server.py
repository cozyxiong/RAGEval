"""Builtin Mock RAG Adapter. Listens on :8100. Closed-domain fake KB."""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

MOCK_CHUNKS: list[dict[str, Any]] = [
    {
        "chunk_id": "c-hq-1",
        "doc_id": "doc-hq",
        "text": "Acme Robotics 总部设在新加坡（Singapore）。公司注册地址位于新加坡滨海湾金融中心。",
        "rank": 1,
        "score": 0.96,
    },
    {
        "chunk_id": "c-product-1",
        "doc_id": "doc-product",
        "text": "Acme Robotics 主要生产仓储机器人（warehouse robots），用于仓库分拣与搬运。",
        "rank": 1,
        "score": 0.93,
    },
    {
        "chunk_id": "c-history-1",
        "doc_id": "doc-history",
        "text": "Acme Robotics 成立于 2018 年，是一家工业机器人公司。",
        "rank": 1,
        "score": 0.91,
    },
]

HQ_TERMS = ("总部", "headquarter", "headquarters", "hq", "新加坡", "singapore", "注册地址")
PRODUCT_TERMS = ("生产", "产品", "机器人", "warehouse", "product", "做什么", "业务")
HISTORY_TERMS = ("成立", "创办", "哪年", "founded", "2018")
AMBIGUOUS_OFFICE_TERMS = ("办公室", "office", "办事处")


class EvalRequest(BaseModel):
    query: str


app = FastAPI(title="RAG Eval Mock Adapter", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "adapter": "mock"}


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _route(query: str) -> tuple[str, list[dict[str, Any]]]:
    if _contains_any(query, HQ_TERMS):
        return (
            "Acme Robotics 总部在新加坡。",
            [MOCK_CHUNKS[0]],
        )
    if _contains_any(query, AMBIGUOUS_OFFICE_TERMS) and not _contains_any(query, HQ_TERMS):
        return (
            "请问您指的是总部还是其他办事处？本次资料只提到总部在新加坡。",
            [MOCK_CHUNKS[0]],
        )
    if _contains_any(query, PRODUCT_TERMS):
        return (
            "Acme Robotics 生产仓储机器人，用于仓库分拣与搬运。",
            [MOCK_CHUNKS[1]],
        )
    if _contains_any(query, HISTORY_TERMS):
        return (
            "Acme Robotics 成立于 2018 年。",
            [MOCK_CHUNKS[2]],
        )
    return (
        "根据本次检索到的资料，我无法回答该问题。",
        [],
    )


@app.post("/eval/rag")
def eval_rag(req: EvalRequest) -> dict[str, Any]:
    started = time.perf_counter()
    answer, chunks = _route(req.query)
    latency_ms = max(int((time.perf_counter() - started) * 1000), 1)
    return {
        "actual_answer": answer,
        "retrieved_chunks": chunks,
        "meta": {
            "latency_ms": latency_ms,
            "model": "mock-generator",
            "embedding_model": "mock-embed",
            "request_id": "mock-req",
        },
    }


def main() -> None:
    import uvicorn

    uvicorn.run("adapters.mock_server:app", host="0.0.0.0", port=8100, reload=False)


if __name__ == "__main__":
    main()
