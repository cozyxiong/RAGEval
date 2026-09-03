"""Poll PENDING runs and evaluate cases asynchronously.

Never invoked from HTTP handlers for a full dataset.
Usage: python -m workers.evaluation_worker
"""

from __future__ import annotations

import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from api.db import SessionLocal, init_db  # noqa: E402
from api.jsonutil import dumps, loads  # noqa: E402
from api.models import CaseResult, DatasetCase, Project, Run, utcnow  # noqa: E402
from core.adapter import AdapterClient, AdapterError  # noqa: E402
from core.diagnosis import diagnose  # noqa: E402
from core.judge import judge  # noqa: E402
from core.metrics import (  # noqa: E402
    completeness_score,
    faithfulness_score,
    judge_label_from_pass,
    pass_,
    retrieval_metrics,
)
from core.spec import parse_spec  # noqa: E402

POLL_SECONDS = 1.0


def _fail_case(row: CaseResult, message: str) -> None:
    row.error = message
    row.judge_label = "fail"
    row.judge_reason = message


def evaluate_case(
    *,
    case: DatasetCase,
    adapter: AdapterClient,
    spec,
) -> dict[str, Any]:
    payload = {
        "actual_answer": None,
        "retrieved_chunks": [],
        "meta": {},
        "latency_ms": None,
        "evaluated_behavior": None,
        "claims": [],
        "faithfulness": None,
        "completeness": None,
        "answer_relevancy": None,
        "judge_label": "fail",
        "judge_reason": None,
        "retrieval_metrics": {},
        "failure_type": [],
        "primary_cause": None,
        "secondary_cause": None,
        "diagnosis": {},
        "error": None,
    }
    try:
        adapter_resp = adapter.eval_rag(case.query)
    except AdapterError as exc:
        payload["error"] = str(exc)
        payload["judge_reason"] = str(exc)
        return payload

    chunks = [c.model_dump() for c in adapter_resp.retrieved_chunks]
    meta = adapter_resp.meta.allowed_dict()
    payload["actual_answer"] = adapter_resp.actual_answer
    payload["retrieved_chunks"] = chunks
    payload["meta"] = meta
    payload["latency_ms"] = adapter_resp.meta.latency_ms

    verdict = judge(
        query=case.query,
        actual_answer=adapter_resp.actual_answer,
        retrieved_chunks=chunks,
        expected_answer=case.expected_answer,
        expected_behavior=case.expected_behavior,
        spec=spec,
    )
    claims = verdict.get("claims") or []
    faith = faithfulness_score(claims)
    comp = completeness_score(
        verdict.get("covered_points"),
        verdict.get("expected_points"),
    )
    rel = float(verdict.get("answer_relevancy") or 0.0)
    behavior = str(verdict.get("evaluated_behavior") or "refuse")
    passed = pass_(
        evaluated_behavior=behavior,
        expected_behavior=case.expected_behavior,
        faithfulness=faith,
        completeness=comp,
        relevancy=rel,
        spec=spec,
    )
    retrieval = retrieval_metrics(
        retrieved_chunks=chunks,
        expected_source=loads(case.expected_source_json, []),
        supporting_passage=loads(case.supporting_passage_json, []),
        relevant_chunks=loads(case.relevant_chunks_json, []),
        spec=spec,
    )
    if spec.retrieval_level == 1 and "recall" in retrieval:
        raise RuntimeError("Level 1 retrieval metrics must not contain recall")
    diag = diagnose(
        case_type=case.case_type,
        expected_source=loads(case.expected_source_json, []),
        expected_behavior=case.expected_behavior,
        evaluated_behavior=behavior,
        faithfulness=faith,
        completeness=comp,
        relevancy=rel,
        retrieval=retrieval,
        spec=spec,
        passed=passed,
    )
    payload.update(
        {
            "evaluated_behavior": behavior,
            "claims": claims,
            "faithfulness": faith,
            "completeness": comp,
            "answer_relevancy": rel,
            "judge_label": judge_label_from_pass(passed),
            "judge_reason": verdict.get("reason"),
            "retrieval_metrics": retrieval,
            "failure_type": diag.get("failure_type") or [],
            "primary_cause": diag.get("primary_cause"),
            "secondary_cause": diag.get("secondary_cause"),
            "diagnosis": diag,
        }
    )
    return payload


def process_run(run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if not run or run.status != "PENDING":
            return
        project = db.get(Project, run.project_id)
        if not project:
            run.status = "FAILED"
            run.error = "project missing"
            run.finished_at = utcnow()
            db.commit()
            return
        spec = parse_spec(loads(run.spec_json, {}))
        adapter = AdapterClient(project.adapter_url, timeout_ms=spec.adapter.timeout_ms)
        run.status = "RUNNING"
        run.started_at = utcnow()
        db.commit()

        cases = (
            db.query(DatasetCase)
            .filter_by(dataset_version_id=run.dataset_version_id)
            .order_by(DatasetCase.case_id)
            .all()
        )
        for case in cases:
            db.refresh(run)
            if run.status == "CANCELLED":
                run.finished_at = utcnow()
                db.commit()
                return
            row = (
                db.query(CaseResult)
                .filter_by(run_id=run.id, case_id=case.case_id)
                .first()
            )
            if row is None:
                row = CaseResult(run_id=run.id, case_id=case.case_id)
                db.add(row)
            try:
                result = evaluate_case(case=case, adapter=adapter, spec=spec)
            except Exception as exc:  # per-case failure must not abort the run
                result = {
                    "error": str(exc),
                    "judge_label": "fail",
                    "judge_reason": str(exc),
                    "retrieval_metrics": {},
                    "failure_type": [],
                    "diagnosis": {},
                }
            row.actual_answer = result.get("actual_answer")
            row.retrieved_chunks_json = dumps(result.get("retrieved_chunks") or [])
            row.meta_json = dumps(result.get("meta") or {})
            row.latency_ms = result.get("latency_ms")
            row.evaluated_behavior = result.get("evaluated_behavior")
            row.claims_json = dumps(result.get("claims") or [])
            row.faithfulness = result.get("faithfulness")
            row.completeness = result.get("completeness")
            row.answer_relevancy = result.get("answer_relevancy")
            row.judge_label = result.get("judge_label")
            row.judge_reason = result.get("judge_reason")
            row.retrieval_metrics_json = dumps(result.get("retrieval_metrics") or {})
            row.failure_type_json = dumps(result.get("failure_type") or [])
            row.primary_cause = result.get("primary_cause")
            row.secondary_cause = result.get("secondary_cause")
            row.diagnosis_json = dumps(result.get("diagnosis") or {})
            row.error = result.get("error")
            run.done = min(run.done + 1, run.total)
            if row.judge_label == "pass":
                run.pass_count += 1
            db.commit()

        db.refresh(run)
        if run.status != "CANCELLED":
            run.status = "COMPLETED"
            run.finished_at = utcnow()
            db.commit()
    except Exception as exc:
        db.rollback()
        run = db.get(Run, run_id)
        if run and run.status not in ("COMPLETED", "CANCELLED"):
            run.status = "FAILED"
            run.error = str(exc)
            run.finished_at = utcnow()
            db.commit()
        raise
    finally:
        db.close()


def process_next_pending() -> str | None:
    db = SessionLocal()
    try:
        run = (
            db.query(Run)
            .filter(Run.status == "PENDING")
            .order_by(Run.created_at.asc())
            .first()
        )
        if not run:
            return None
        run_id = run.id
    finally:
        db.close()
    process_run(run_id)
    return run_id


def main() -> None:
    init_db()
    while True:
        processed = process_next_pending()
        if processed is None:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
