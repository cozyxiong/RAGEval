"""Map BaGuLLM (AnythingLLM-compatible) workspace chat onto the eval Adapter contract.

BaGuLLM does not speak POST /eval/rag natively. This wrapper is the only extra
layer — eval math still lives in core/.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

DEFAULT_BASE = "http://127.0.0.1:3001"
DEFAULT_WORKSPACE = "java"


def settings() -> dict[str, str]:
    return {
        "base_url": os.environ.get("BAGULLM_BASE_URL", DEFAULT_BASE).rstrip("/"),
        "api_key": os.environ.get("BAGULLM_API_KEY", "").strip(),
        "workspace": os.environ.get("BAGULLM_WORKSPACE", DEFAULT_WORKSPACE).strip() or DEFAULT_WORKSPACE,
        "mode": os.environ.get("BAGULLM_CHAT_MODE", "query").strip() or "query",
    }


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    """Drop hidden chain-of-thought so Judge sees the user-facing answer only."""
    return _THINK_BLOCK.sub("", text or "").strip()


def sources_to_chunks(sources: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Convert BaGuLLM/AnythingLLM `sources` into retrieved_chunks."""
    chunks: list[dict[str, Any]] = []
    for i, src in enumerate(sources or [], start=1):
        text = str(src.get("chunk") or src.get("text") or src.get("content") or "")
        doc_id = str(src.get("title") or src.get("doc_id") or src.get("filename") or f"doc-{i}")
        chunk_id = str(src.get("id") or src.get("chunk_id") or f"{doc_id}#{i}")
        score_raw = src.get("score", src.get("similarity"))
        try:
            score = float(score_raw) if score_raw is not None else None
        except (TypeError, ValueError):
            score = None
        chunks.append(
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "text": text,
                "rank": i,
                "score": score,
            }
        )
    return chunks


class EvalRequest(BaseModel):
    query: str


app = FastAPI(title="BaGuLLM Adapter", version="0.1.0")


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    cfg = settings()
    url = f"{cfg['base_url']}/api/ping"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            body = resp.json() if resp.content else {}
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"BaGuLLM ping failed: {exc}") from exc
    return {
        "ok": True,
        "adapter": "bagullm",
        "workspace": cfg["workspace"],
        "upstream": body,
    }


@app.post("/eval/rag")
def eval_rag(req: EvalRequest) -> dict[str, Any]:
    cfg = settings()
    if not cfg["api_key"]:
        raise HTTPException(500, "BAGULLM_API_KEY is not set")
    started = time.perf_counter()
    url = f"{cfg['base_url']}/api/v1/workspace/{cfg['workspace']}/chat"
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                url,
                headers=_headers(cfg["api_key"]),
                json={"message": req.query, "mode": cfg["mode"]},
            )
            if resp.status_code >= 400:
                raise HTTPException(502, f"BaGuLLM chat {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"BaGuLLM chat failed: {exc}") from exc
    latency_ms = max(int((time.perf_counter() - started) * 1000), 1)
    if data.get("error") and not data.get("textResponse"):
        raise HTTPException(502, f"BaGuLLM error: {data.get('error')}")
    answer = strip_think(str(data.get("textResponse") or ""))
    chunks = sources_to_chunks(data.get("sources") or [])
    return {
        "actual_answer": answer,
        "retrieved_chunks": chunks,
        "meta": {
            "latency_ms": latency_ms,
            "model": str(data.get("chatModel") or data.get("model") or "bagullm"),
            "request_id": str(data.get("id") or ""),
        },
    }


def main() -> None:
    import uvicorn

    uvicorn.run("adapters.bagullm:app", host="0.0.0.0", port=8101, reload=False)


if __name__ == "__main__":
    main()
