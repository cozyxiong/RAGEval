"""Rule-based diagnosis. First matching rule is primary_cause."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.spec import FAILURE_TYPES, NOISE_PRECISION_MAX, EvaluationSpec, parse_spec

RULES: tuple[tuple[int, str], ...] = (
    (1, "评测集"),
    (2, "检索漏召回"),
    (3, "检索噪声"),
    (4, "生成幻觉"),
    (5, "生成答差"),
    (6, "行为错误"),
)


def _hit(retrieval: Mapping[str, Any], spec: EvaluationSpec) -> bool:
    if spec.retrieval_level == 2:
        return int(retrieval.get("hit") or 0) == 1
    return int(retrieval.get("expected_source_hit") or 0) == 1


def failure_types(
    *,
    expected_behavior: str,
    evaluated_behavior: str | None,
    faithfulness: float | None,
    completeness: float | None,
    relevancy: float | None,
    spec: EvaluationSpec,
) -> list[str]:
    types: list[str] = []
    ev = evaluated_behavior or ""
    if ev != expected_behavior:
        types.append("Incorrect")
        if expected_behavior == "refuse" and ev == "answer":
            types.append("Should-Refuse-but-Answered")
        if expected_behavior == "answer" and ev == "refuse":
            types.append("Wrong Refusal")
        if expected_behavior == "clarify" and ev != "clarify":
            types.append("Missing Clarification")
    gate = spec.pass_gate
    if faithfulness is not None and faithfulness < gate.faithfulness:
        types.append("Ungrounded")
    if expected_behavior == "answer":
        if completeness is not None and completeness < gate.completeness:
            types.append("Incomplete")
        if relevancy is not None and relevancy < gate.relevancy:
            types.append("Irrelevant")
    # stable unique
    seen: set[str] = set()
    out: list[str] = []
    for t in types:
        if t in FAILURE_TYPES and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def diagnose(
    *,
    case_type: str,
    expected_source: Sequence[str] | None,
    expected_behavior: str,
    evaluated_behavior: str | None,
    faithfulness: float | None,
    completeness: float | None,
    relevancy: float | None,
    retrieval: Mapping[str, Any] | None,
    spec: EvaluationSpec | dict[str, Any],
    passed: bool,
) -> dict[str, Any]:
    spec_obj = parse_spec(spec)
    retrieval = retrieval or {}
    candidates: list[dict[str, Any]] = []

    def add(rule_id: int, cause: str, matched: bool, detail: str) -> None:
        candidates.append(
            {"rule": rule_id, "cause": cause, "matched": matched, "detail": detail}
        )

    empty_source = not list(expected_source or [])
    add(
        1,
        "评测集",
        case_type == "answerable" and empty_source,
        "answerable and expected_source empty",
    )
    l1_miss = spec_obj.retrieval_level == 1 and int(retrieval.get("expected_source_hit") or 0) == 0
    l2_miss = spec_obj.retrieval_level == 2 and int(retrieval.get("hit") or 0) == 0
    add(2, "检索漏召回", l1_miss or l2_miss, "source_hit/hit is 0")
    precision = float(retrieval.get("precision") or 0.0)
    l2_noise = (
        spec_obj.retrieval_level == 2
        and int(retrieval.get("hit") or 0) == 1
        and precision < NOISE_PRECISION_MAX
    )
    add(3, "检索噪声", l2_noise, f"hit=1 and precision={precision} < {NOISE_PRECISION_MAX}")
    already_hit = _hit(retrieval, spec_obj)
    faith = 1.0 if faithfulness is None else faithfulness
    add(
        4,
        "生成幻觉",
        already_hit and faith < spec_obj.pass_gate.faithfulness,
        "hit and faithfulness below gate",
    )
    comp = 1.0 if completeness is None else completeness
    rel = 1.0 if relevancy is None else relevancy
    gen_poor = already_hit and (
        (expected_behavior == "answer" and comp < spec_obj.pass_gate.completeness)
        or (expected_behavior == "answer" and rel < spec_obj.pass_gate.relevancy)
    )
    add(5, "生成答差", gen_poor, "hit and completeness/relevancy below gate")
    add(
        6,
        "行为错误",
        (evaluated_behavior or "") != expected_behavior,
        "evaluated_behavior != expected_behavior",
    )

    primary = None
    secondary = None
    if not passed:
        matched = [c for c in candidates if c["matched"]]
        if matched:
            primary = matched[0]["cause"]
            if len(matched) > 1:
                secondary = matched[1]["cause"]

    ftypes = failure_types(
        expected_behavior=expected_behavior,
        evaluated_behavior=evaluated_behavior,
        faithfulness=faithfulness,
        completeness=completeness,
        relevancy=relevancy,
        spec=spec_obj,
    )
    return {
        "primary_cause": primary,
        "secondary_cause": secondary,
        "failure_type": ftypes,
        "candidates": candidates,
        "rule": "v1-order-1-6",
    }
