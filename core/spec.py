"""Evaluation Spec models, canonical JSON, hashes, and Spec-owned constants.

Pass thresholds and calibration gates live here (or are read from Spec JSON).
Do not hard-code 0.85 (or any pass threshold) in metrics or API layers.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field

RAG_VERSION_KEYS: tuple[str, ...] = (
    "kb",
    "chunk",
    "embedding",
    "retrieval",
    "rerank",
    "generator",
    "prompt",
)

ALLOWED_META_KEYS: frozenset[str] = frozenset(
    {"latency_ms", "model", "embedding_model", "rerank_model", "request_id"}
)

RELEVANT_LABEL_MIN = 2
"""retrieved chunk is relevant iff label >= 2."""

NOISE_PRECISION_MAX = 0.5
"""Level-2 diagnosis: precision below this is 检索噪声. Not a Pass gate."""

CALIBRATION_STATUSES = ("not_calibrated", "insufficient", "calibrated")
RUN_STATUSES = ("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED")
CASE_TYPES = ("answerable", "unanswerable", "ambiguous")
BEHAVIORS = ("answer", "refuse", "clarify")
DATASET_KINDS = ("gold", "calibration")
PRODUCT_MODES = ("closed_domain",)

FAILURE_TYPES = (
    "Incorrect",
    "Incomplete",
    "Irrelevant",
    "Ungrounded",
    "Wrong Refusal",
    "Should-Refuse-but-Answered",
    "Missing Clarification",
)

PRIMARY_CAUSES = (
    "评测集",
    "检索漏召回",
    "检索噪声",
    "生成幻觉",
    "生成答差",
    "行为错误",
)


def canonical_json(obj: Any) -> str:
    """Stable JSON used for hashes and fingerprints."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PassGate(BaseModel):
    behavior: bool = True
    faithfulness: float = 0.85
    completeness: float = 0.75
    relevancy: float = 0.85


class JudgeSpec(BaseModel):
    provider: str = "builtin"
    model: str = "gpt-4.1-mini"
    prompt_version: str = "judge-v1"


class AdapterSpec(BaseModel):
    timeout_ms: int = 60_000


class HumanSpec(BaseModel):
    fail_review: str = "all"
    pass_sample_rate: float = 0.15


class CalibrationGate(BaseModel):
    min_n: int = 20
    min_accuracy: float = 0.80
    max_false_pass: float = 0.15


class EvaluationSpec(BaseModel):
    product_mode: Literal["closed_domain"] = "closed_domain"
    retrieval_level: Literal[1, 2] = 1
    k: int = 8
    pass_gate: PassGate = Field(default_factory=PassGate)
    judge: JudgeSpec = Field(default_factory=JudgeSpec)
    adapter: AdapterSpec = Field(default_factory=AdapterSpec)
    human: HumanSpec = Field(default_factory=HumanSpec)
    calibration: CalibrationGate = Field(default_factory=CalibrationGate)

    def to_json_dict(self) -> dict[str, Any]:
        return json.loads(self.model_dump_json())

    def spec_hash(self) -> str:
        return sha256_hex(canonical_json(self.to_json_dict()))


DEFAULT_SPEC = EvaluationSpec()


def parse_spec(raw: dict[str, Any] | EvaluationSpec | None) -> EvaluationSpec:
    if raw is None:
        return EvaluationSpec()
    if isinstance(raw, EvaluationSpec):
        return raw
    return EvaluationSpec.model_validate(raw)


def normalize_rag_version(raw: dict[str, Any] | None) -> dict[str, str]:
    src = raw or {}
    out: dict[str, str] = {}
    for key in RAG_VERSION_KEYS:
        value = src.get(key, "")
        out[key] = "" if value is None else str(value)
    extra = sorted(k for k in src if k not in RAG_VERSION_KEYS)
    if extra:
        raise ValueError(f"unknown rag_version keys: {extra}")
    return out
