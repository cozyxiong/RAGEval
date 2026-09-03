from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.spec import EvaluationSpec


class ProjectCreate(BaseModel):
    name: str
    adapter_url: str
    product_mode: Literal["closed_domain"] = "closed_domain"
    spec: EvaluationSpec | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    adapter_url: str | None = None
    product_mode: Literal["closed_domain"] | None = None
    spec: EvaluationSpec | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    adapter_url: str
    product_mode: str
    spec: dict[str, Any]
    created_at: datetime


class DatasetCreate(BaseModel):
    kind: Literal["gold", "calibration"] = "gold"
    name: str


class DatasetOut(BaseModel):
    id: str
    project_id: str
    kind: str
    name: str


class RelevantChunkIn(BaseModel):
    chunk_id: str | None = None
    doc_id: str | None = None
    label: int = 2


class CaseIn(BaseModel):
    case_id: str
    query: str
    case_type: Literal["answerable", "unanswerable", "ambiguous"]
    expected_behavior: Literal["answer", "refuse", "clarify"]
    expected_answer: str = ""
    expected_source: list[str] = Field(default_factory=list)
    supporting_passage: list[str] = Field(default_factory=list)
    relevant_chunks: list[RelevantChunkIn] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CaseOut(CaseIn):
    id: str
    dataset_version_id: str


class DatasetVersionOut(BaseModel):
    id: str
    dataset_id: str
    version: int
    confirmed_at: datetime | None
    hash: str
    case_count: int = 0


class GenerateIn(BaseModel):
    hints: list[str] = Field(default_factory=list)


class SampleCalibrationIn(BaseModel):
    per_type: int = 2
    name: str = "calibration"


class JudgeConfigCreate(BaseModel):
    provider: str = "builtin"
    model: str | None = None
    prompt_text: str | None = None


class JudgeConfigOut(BaseModel):
    id: str
    project_id: str
    provider: str
    model: str
    prompt_hash: str
    prompt_text: str


class CalibrateIn(BaseModel):
    run_id: str


class JudgeCalibrationOut(BaseModel):
    id: str
    project_id: str
    judge_config_id: str
    dataset_version_id: str
    n: int
    accuracy: float
    false_pass_rate: float
    false_fail_rate: float
    status: str
    created_at: datetime
    confusion: dict[str, int] | None = None


class RagVersionIn(BaseModel):
    kb: str = ""
    chunk: str = ""
    embedding: str = ""
    retrieval: str = ""
    rerank: str = ""
    generator: str = ""
    prompt: str = ""


class RunCreate(BaseModel):
    dataset_version_id: str
    judge_config_id: str | None = None
    rag_version: RagVersionIn = Field(default_factory=RagVersionIn)
    use_as_gate: bool = False


class RunOut(BaseModel):
    id: str
    project_id: str
    dataset_version_id: str
    judge_config_id: str
    spec: dict[str, Any]
    spec_hash: str
    rag_version: dict[str, Any]
    fingerprint: str
    status: str
    total: int
    done: int
    pass_count: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class HumanLabelIn(BaseModel):
    human_label: Literal["pass", "fail"]
    human_reason: str = ""


class CaseResultOut(BaseModel):
    id: str
    run_id: str
    case_id: str
    actual_answer: str | None
    retrieved_chunks: Any
    meta: Any
    latency_ms: int | None
    evaluated_behavior: str | None
    claims: Any
    faithfulness: float | None
    completeness: float | None
    answer_relevancy: float | None
    judge_label: str | None
    judge_reason: str | None
    human_label: str | None
    human_reason: str | None
    retrieval_metrics: Any
    failure_type: Any
    primary_cause: str | None
    secondary_cause: str | None
    diagnosis: Any
    error: str | None


class ExperimentCreate(BaseModel):
    baseline_run_id: str
    result_run_id: str


class ExperimentOut(BaseModel):
    id: str
    project_id: str
    baseline_run_id: str
    result_run_id: str
    modified_variable: str
    modified_from: str
    modified_to: str
    created_at: datetime
