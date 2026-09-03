from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter_url: Mapped[str] = mapped_column(String(500), nullable=False)
    product_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="closed_domain")
    spec_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    datasets: Mapped[list[Dataset]] = relationship(back_populates="project")
    judge_configs: Mapped[list[JudgeConfig]] = relationship(back_populates="project")
    runs: Mapped[list[Run]] = relationship(back_populates="project")
    experiments: Mapped[list[Experiment]] = relationship(back_populates="project")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    project: Mapped[Project] = relationship(back_populates="datasets")
    versions: Mapped[list[DatasetVersion]] = relationship(back_populates="dataset")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version", name="uq_dataset_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    dataset: Mapped[Dataset] = relationship(back_populates="versions")
    cases: Mapped[list[DatasetCase]] = relationship(back_populates="version")


class DatasetCase(Base):
    __tablename__ = "dataset_cases"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "case_id", name="uq_version_case"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    case_type: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_behavior: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_source_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    supporting_passage_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    relevant_chunks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    version: Mapped[DatasetVersion] = relationship(back_populates="cases")


class JudgeConfig(Base):
    __tablename__ = "judge_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="builtin")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-4.1-mini")
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    project: Mapped[Project] = relationship(back_populates="judge_configs")
    calibrations: Mapped[list[JudgeCalibration]] = relationship(back_populates="judge_config")


class JudgeCalibration(Base):
    __tablename__ = "judge_calibrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    judge_config_id: Mapped[str] = mapped_column(ForeignKey("judge_configs.id"), nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), nullable=False)
    n: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    false_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    false_fail_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_calibrated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    judge_config: Mapped[JudgeConfig] = relationship(back_populates="calibrations")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), nullable=False)
    judge_config_id: Mapped[str] = mapped_column(ForeignKey("judge_configs.id"), nullable=False)
    spec_json: Mapped[str] = mapped_column(Text, nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    rag_version_json: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="runs")
    case_results: Mapped[list[CaseResult]] = relationship(back_populates="run")


class CaseResult(Base):
    __tablename__ = "case_results"
    __table_args__ = (UniqueConstraint("run_id", "case_id", name="uq_run_case"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False)
    actual_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_chunks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluated_behavior: Mapped[str | None] = mapped_column(String(32), nullable=True)
    claims_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_relevancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_label: Mapped[str | None] = mapped_column(String(16), nullable=True)
    judge_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_label: Mapped[str | None] = mapped_column(String(16), nullable=True)
    human_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieval_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_type_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_cause: Mapped[str | None] = mapped_column(String(50), nullable=True)
    secondary_cause: Mapped[str | None] = mapped_column(String(50), nullable=True)
    diagnosis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship(back_populates="case_results")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    baseline_run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    result_run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    modified_variable: Mapped[str] = mapped_column(String(50), nullable=False)
    modified_from: Mapped[str] = mapped_column(Text, nullable=False)
    modified_to: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="experiments")
