"""HTTP Adapter client. Speaks POST {adapter_url}/eval/rag only."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.spec import ALLOWED_META_KEYS


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    rank: int
    score: float | None = None


class AdapterMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    latency_ms: int
    model: str | None = None
    embedding_model: str | None = None
    rerank_model: str | None = None
    request_id: str | None = None

    @field_validator("latency_ms")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("latency_ms must be >= 0")
        return v

    def allowed_dict(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        return {k: v for k, v in data.items() if k in ALLOWED_META_KEYS}


class AdapterResponse(BaseModel):
    actual_answer: str
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    meta: AdapterMeta


class AdapterError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AdapterClient:
    def __init__(self, adapter_url: str, timeout_ms: int = 60_000) -> None:
        self.base_url = adapter_url.rstrip("/")
        self.timeout_s = max(timeout_ms, 1) / 1000.0

    def ping(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/health")
                resp.raise_for_status()
                body = resp.json() if resp.content else {"ok": True}
                if not isinstance(body, dict):
                    body = {"ok": True, "body": body}
                body.setdefault("ok", True)
                return body
        except httpx.HTTPError as exc:
            raise AdapterError(f"adapter ping failed: {exc}") from exc

    def eval_rag(self, query: str) -> AdapterResponse:
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.post(
                    f"{self.base_url}/eval/rag",
                    json={"query": query},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                return AdapterResponse.model_validate(resp.json())
        except httpx.HTTPError as exc:
            status = exc.response.status_code if getattr(exc, "response", None) is not None else None
            raise AdapterError(f"adapter eval failed: {exc}", status_code=status) from exc
