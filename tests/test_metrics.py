from __future__ import annotations

import inspect

import core.metrics as metrics
from core.spec import EvaluationSpec, PassGate


def test_pass_is_conjunction_of_four_gates() -> None:
    spec = EvaluationSpec(
        pass_gate=PassGate(behavior=True, faithfulness=0.8, completeness=0.7, relevancy=0.7)
    )
    kwargs = dict(
        evaluated_behavior="answer",
        expected_behavior="answer",
        faithfulness=0.9,
        completeness=0.9,
        relevancy=0.9,
        spec=spec,
    )
    assert metrics.pass_(**kwargs) is True
    assert metrics.pass_(**{**kwargs, "evaluated_behavior": "refuse"}) is False
    assert metrics.pass_(**{**kwargs, "faithfulness": 0.79}) is False
    assert metrics.pass_(**{**kwargs, "completeness": 0.69}) is False
    assert metrics.pass_(**{**kwargs, "relevancy": 0.69}) is False


def test_complete_and_relevant_skipped_for_refuse_and_clarify() -> None:
    spec = EvaluationSpec(
        pass_gate=PassGate(behavior=True, faithfulness=0.5, completeness=0.99, relevancy=0.99)
    )
    refuse_pass = metrics.pass_(
        evaluated_behavior="refuse",
        expected_behavior="refuse",
        faithfulness=1.0,
        completeness=0.0,
        relevancy=0.0,
        spec=spec,
    )
    clarify_pass = metrics.pass_(
        evaluated_behavior="clarify",
        expected_behavior="clarify",
        faithfulness=0.6,
        completeness=0.0,
        relevancy=0.0,
        spec=spec,
    )
    answer_fail = metrics.pass_(
        evaluated_behavior="answer",
        expected_behavior="answer",
        faithfulness=1.0,
        completeness=0.0,
        relevancy=0.0,
        spec=spec,
    )
    assert refuse_pass is True
    assert clarify_pass is True
    assert answer_fail is False


def test_faithfulness_no_claims_is_one() -> None:
    assert metrics.faithfulness_score([]) == 1.0
    assert metrics.faithfulness_score(None) == 1.0
    claims = [
        {"text": "a", "supported": True},
        {"text": "b", "supported": False},
        {"text": "c", "supported": True},
    ]
    assert metrics.faithfulness_score(claims) == 2 / 3


def test_completeness_no_points_is_one() -> None:
    assert metrics.completeness_score(0, 0) == 1.0
    assert metrics.completeness_score([], []) == 1.0
    assert metrics.completeness_score(["a"], ["a", "b", "c"]) == 1 / 3
    assert metrics.completeness_score(2, 4) == 0.5


def test_thresholds_come_from_spec_json_not_literals() -> None:
    source = inspect.getsource(metrics.pass_) + inspect.getsource(metrics.is_faithful)
    assert "0.85" not in source
    loose = EvaluationSpec(pass_gate=PassGate(faithfulness=0.4, completeness=0.1, relevancy=0.1))
    tight = EvaluationSpec(pass_gate=PassGate(faithfulness=0.95, completeness=0.1, relevancy=0.1))
    mid = 0.7
    assert (
        metrics.pass_(
            evaluated_behavior="answer",
            expected_behavior="answer",
            faithfulness=mid,
            completeness=1.0,
            relevancy=1.0,
            spec=loose,
        )
        is True
    )
    assert (
        metrics.pass_(
            evaluated_behavior="answer",
            expected_behavior="answer",
            faithfulness=mid,
            completeness=1.0,
            relevancy=1.0,
            spec=tight,
        )
        is False
    )


def test_level1_has_hits_and_no_recall() -> None:
    spec = EvaluationSpec(retrieval_level=1, k=8)
    chunks = [
        {"chunk_id": "c1", "doc_id": "doc-hq", "text": "总部设在新加坡", "rank": 1, "score": 0.9},
        {"chunk_id": "c2", "doc_id": "other", "text": "无关", "rank": 2, "score": 0.1},
    ]
    result = metrics.retrieval_metrics(
        retrieved_chunks=chunks,
        expected_source=["doc-hq"],
        supporting_passage=["总部设在新加坡"],
        relevant_chunks=[{"chunk_id": "c1", "doc_id": "doc-hq", "label": 2}],
        spec=spec,
    )
    assert result["expected_source_hit"] == 1
    assert result["passage_hit"] == 1
    assert "recall" not in result
    assert set(result) <= {"expected_source_hit", "passage_hit", "k"}


def test_level2_hit_recall_precision_mrr_uses_min_k() -> None:
    spec = EvaluationSpec(retrieval_level=2, k=8)
    chunks = [
        {"chunk_id": "c-noise", "doc_id": "d0", "text": "n", "rank": 1, "score": 0.99},
        {"chunk_id": "c-rel", "doc_id": "d1", "text": "gold", "rank": 2, "score": 0.8},
        {"chunk_id": "c-other", "doc_id": "d2", "text": "x", "rank": 3, "score": 0.1},
    ]
    relevant = [
        {"chunk_id": "c-rel", "doc_id": "d1", "label": 2},
        {"chunk_id": "c-miss", "doc_id": "d9", "label": 3},
        {"chunk_id": "c-ignore", "doc_id": "d8", "label": 1},
    ]
    result = metrics.retrieval_metrics(
        retrieved_chunks=chunks,
        expected_source=["d1"],
        supporting_passage=["gold"],
        relevant_chunks=relevant,
        spec=spec,
    )
    assert result["k"] == 3  # min(8, 3)
    assert result["hit"] == 1
    assert result["recall"] == 1 / 2  # two gold ids c-rel/d1 and c-miss/d9; one hit
    assert result["precision"] == 1 / 3
    assert result["mrr"] == 0.5  # first relevant at rank 2
    assert "expected_source_hit" in result


def test_relevant_requires_label_at_least_two() -> None:
    spec = EvaluationSpec(retrieval_level=2, k=2)
    chunks = [{"chunk_id": "c1", "doc_id": "d1", "text": "t", "rank": 1, "score": 1.0}]
    result = metrics.retrieval_metrics(
        retrieved_chunks=chunks,
        expected_source=[],
        supporting_passage=[],
        relevant_chunks=[{"chunk_id": "c1", "doc_id": "d1", "label": 1}],
        spec=spec,
    )
    assert result["hit"] == 0
    assert result["recall"] == 0.0


def test_calibration_status_transitions() -> None:
    spec = EvaluationSpec()
    empty = metrics.calibration_rates([], spec)
    assert empty["status"] == "not_calibrated"
    assert empty["accuracy"] == 0.0

    small = [("pass", "pass")] * 10 + [("fail", "fail")] * 5
    insuff = metrics.calibration_rates(small, spec)
    assert insuff["n"] == 15
    assert insuff["status"] == "insufficient"

    good = [("pass", "pass")] * 16 + [("fail", "fail")] * 4
    cal = metrics.calibration_rates(good, spec)
    assert cal["n"] == 20
    assert cal["accuracy"] == 1.0
    assert cal["false_pass_rate"] == 0.0
    assert cal["status"] == "calibrated"

    noisy = [("pass", "fail")] * 8 + [("fail", "fail")] * 12
    bad = metrics.calibration_rates(noisy, spec)
    assert bad["n"] == 20
    assert bad["false_pass_rate"] == 8 / 20
    assert bad["status"] == "insufficient"

    custom = EvaluationSpec()
    custom.calibration.min_n = 5
    custom.calibration.min_accuracy = 0.5
    custom.calibration.max_false_pass = 0.5
    custom_ok = metrics.calibration_rates([("pass", "pass")] * 3 + [("fail", "fail")] * 2, custom)
    assert custom_ok["status"] == "calibrated"
