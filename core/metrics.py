"""Eval formulas. This module and core/spec.py are the only Pass/Recall paths."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from core.spec import RELEVANT_LABEL_MIN, EvaluationSpec, parse_spec

Claim = Mapping[str, Any]
Chunk = Mapping[str, Any]
Relevant = Mapping[str, Any]


def faithfulness_score(claims: Sequence[Claim] | None) -> float:
    """supported claims / all claims. No claims (pure refusal) = 1.0."""
    if not claims:
        return 1.0
    supported = sum(1 for c in claims if bool(c.get("supported")))
    return supported / len(claims)


def completeness_score(
    covered_points: int | Sequence[Any] | None,
    total_points: int | Sequence[Any] | None,
) -> float:
    """covered expected_answer points / total points. No points = 1.0."""
    total = _count(total_points)
    if total == 0:
        return 1.0
    covered = min(_count(covered_points), total)
    return covered / total


def _count(value: int | Sequence[Any] | None) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return max(value, 0)
    return len(value)


def behavior_correct(evaluated_behavior: str, expected_behavior: str) -> bool:
    return evaluated_behavior == expected_behavior


def is_faithful(faithfulness: float, spec: EvaluationSpec) -> bool:
    return faithfulness >= spec.pass_gate.faithfulness


def is_complete(completeness: float, expected_behavior: str, spec: EvaluationSpec) -> bool:
    if expected_behavior != "answer":
        return True
    return completeness >= spec.pass_gate.completeness


def is_relevant(relevancy: float, expected_behavior: str, spec: EvaluationSpec) -> bool:
    if expected_behavior != "answer":
        return True
    return relevancy >= spec.pass_gate.relevancy


def pass_(
    *,
    evaluated_behavior: str,
    expected_behavior: str,
    faithfulness: float,
    completeness: float,
    relevancy: float,
    spec: EvaluationSpec | dict[str, Any],
) -> bool:
    """Pass iff BehaviorCorrect AND Faithful AND Complete AND Relevant.

    Complete/Relevant apply only when expected_behavior == answer.
    refuse/clarify skip those gates; claims still feed Faithfulness.
    Thresholds come only from Spec JSON.
    """
    spec_obj = parse_spec(spec)
    ok_behavior = behavior_correct(evaluated_behavior, expected_behavior)
    if spec_obj.pass_gate.behavior and not ok_behavior:
        return False
    if not is_faithful(faithfulness, spec_obj):
        return False
    if not is_complete(completeness, expected_behavior, spec_obj):
        return False
    if not is_relevant(relevancy, expected_behavior, spec_obj):
        return False
    return True


def judge_label_from_pass(passed: bool) -> str:
    return "pass" if passed else "fail"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def expected_source_hit(
    retrieved_chunks: Sequence[Chunk],
    expected_source: Sequence[str] | None,
) -> int:
    if not expected_source:
        return 0
    wanted = {s.strip() for s in expected_source if s and str(s).strip()}
    if not wanted:
        return 0
    for chunk in retrieved_chunks:
        doc_id = str(chunk.get("doc_id") or "")
        chunk_id = str(chunk.get("chunk_id") or "")
        if doc_id in wanted or chunk_id in wanted:
            return 1
    return 0


def passage_hit(
    retrieved_chunks: Sequence[Chunk],
    supporting_passage: Sequence[str] | None,
) -> int:
    if not supporting_passage:
        return 0
    blob = _norm(" ".join(str(c.get("text") or "") for c in retrieved_chunks))
    if not blob:
        return 0
    for passage in supporting_passage:
        needle = _norm(str(passage))
        if needle and needle in blob:
            return 1
    return 0


def _is_relevant_label(item: Relevant) -> bool:
    try:
        return int(item.get("label", 0)) >= RELEVANT_LABEL_MIN
    except (TypeError, ValueError):
        return False


def _chunk_matches_relevant(chunk: Chunk, gold: Relevant) -> bool:
    cid, gid = chunk.get("chunk_id"), gold.get("chunk_id")
    if cid and gid:
        return str(cid) == str(gid)
    did, gdoc = chunk.get("doc_id"), gold.get("doc_id")
    if did and gdoc:
        return str(did) == str(gdoc)
    return False


def _ranked(retrieved_chunks: Sequence[Chunk]) -> list[Chunk]:
    return sorted(
        retrieved_chunks,
        key=lambda c: (int(c.get("rank") or 10**9), -(float(c.get("score") or 0.0))),
    )


def retrieval_metrics(
    *,
    retrieved_chunks: Sequence[Chunk],
    expected_source: Sequence[str] | None,
    supporting_passage: Sequence[str] | None,
    relevant_chunks: Sequence[Relevant] | None,
    spec: EvaluationSpec | dict[str, Any],
) -> dict[str, Any]:
    """Level 1: expected_source_hit, passage_hit (no recall key).
    Level 2: hit, recall, precision, mrr with K=min(spec.k, len(chunks)).
    """
    spec_obj = parse_spec(spec)
    ranked = _ranked(list(retrieved_chunks or []))
    k = min(spec_obj.k, len(ranked)) if ranked else 0
    topk = ranked[:k] if k else []

    level1 = {
        "expected_source_hit": expected_source_hit(topk or ranked, expected_source),
        "passage_hit": passage_hit(topk or ranked, supporting_passage),
        "k": k,
    }
    if spec_obj.retrieval_level == 1:
        assert "recall" not in level1
        return level1

    gold = [r for r in (relevant_chunks or []) if _is_relevant_label(r)]
    retrieved_hits = 0
    first_rank: int | None = None
    matched_gold = 0
    for i, chunk in enumerate(topk, start=1):
        if any(_chunk_matches_relevant(chunk, g) for g in gold):
            retrieved_hits += 1
            if first_rank is None:
                first_rank = i
    for g in gold:
        if any(_chunk_matches_relevant(chunk, g) for chunk in topk):
            matched_gold += 1
    hit = 1 if retrieved_hits > 0 else 0
    recall = (matched_gold / len(gold)) if gold else 0.0
    precision = (retrieved_hits / k) if k else 0.0
    mrr = (1.0 / first_rank) if first_rank else 0.0
    return {
        **level1,
        "hit": hit,
        "recall": recall,
        "precision": precision,
        "mrr": mrr,
    }


def mean(values: Iterable[float | None]) -> float | None:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def calibration_rates(
    pairs: Sequence[tuple[str, str]],
    spec: EvaluationSpec | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """pairs: (judge_label, human_label) each in {pass, fail}.

    Accuracy=(TP+TN)/N; FPR=FP/(FP+TN); FNR=FN/(FN+TP).
    Positive class is pass.
    """
    spec_obj = parse_spec(spec)
    n = len(pairs)
    tp = tn = fp = fn = 0
    for judge, human in pairs:
        j = judge.lower()
        h = human.lower()
        if j == "pass" and h == "pass":
            tp += 1
        elif j == "pass" and h == "fail":
            fp += 1
        elif j == "fail" and h == "pass":
            fn += 1
        elif j == "fail" and h == "fail":
            tn += 1
    accuracy = ((tp + tn) / n) if n else 0.0
    fpr = (fp / (fp + tn)) if (fp + tn) else 0.0
    fnr = (fn / (fn + tp)) if (fn + tp) else 0.0
    status = calibration_status(
        n=n,
        accuracy=accuracy,
        false_pass_rate=fpr,
        spec=spec_obj,
    )
    return {
        "n": n,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": accuracy,
        "false_pass_rate": fpr,
        "false_fail_rate": fnr,
        "status": status,
    }


def calibration_status(
    *,
    n: int,
    accuracy: float,
    false_pass_rate: float,
    spec: EvaluationSpec | dict[str, Any],
) -> str:
    """not_calibrated | insufficient | calibrated.

    Default calibrated: N>=min_n AND Accuracy>=min_accuracy AND FPR<=max_false_pass.
    """
    spec_obj = parse_spec(spec)
    gate = spec_obj.calibration
    if n <= 0:
        return "not_calibrated"
    if n < gate.min_n:
        return "insufficient"
    if accuracy >= gate.min_accuracy and false_pass_rate <= gate.max_false_pass:
        return "calibrated"
    return "insufficient"
