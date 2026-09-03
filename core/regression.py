"""Run report aggregation and two-run diff. No Pass/Recall arithmetic here —
those values are read from case_results produced by core.metrics."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from core.metrics import mean


def _slice_key(case: Mapping[str, Any]) -> tuple[str, str]:
    return (str(case.get("case_type") or "unknown"), str(case.get("expected_behavior") or "unknown"))


def build_report(
    *,
    fingerprint: str,
    retrieval_level: int,
    judge_status: str,
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    n = len(cases)
    passed = [c for c in cases if c.get("judge_label") == "pass"]
    pass_rate = (len(passed) / n) if n else 0.0
    retrieval_rows = [c.get("retrieval_metrics") or {} for c in cases]

    retrieval_summary: dict[str, Any]
    if retrieval_level == 1:
        hits = [int(r.get("expected_source_hit") or 0) for r in retrieval_rows]
        passages = [int(r.get("passage_hit") or 0) for r in retrieval_rows]
        retrieval_summary = {
            "expected_source_hit": (sum(hits) / n) if n else 0.0,
            "passage_hit": (sum(passages) / n) if n else 0.0,
        }
        assert "recall" not in retrieval_summary
    else:
        retrieval_summary = {
            "hit": mean([r.get("hit") for r in retrieval_rows]) or 0.0,
            "recall": mean([r.get("recall") for r in retrieval_rows]) or 0.0,
            "precision": mean([r.get("precision") for r in retrieval_rows]) or 0.0,
            "mrr": mean([r.get("mrr") for r in retrieval_rows]) or 0.0,
        }

    slices: dict[str, Any] = {}
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for c in cases:
        grouped[_slice_key(c)].append(c)
    for (ctype, behav), rows in grouped.items():
        key = f"{ctype}|{behav}"
        pn = len(rows)
        pp = sum(1 for r in rows if r.get("judge_label") == "pass")
        slices[key] = {
            "n": pn,
            "pass_rate": (pp / pn) if pn else 0.0,
            "case_type": ctype,
            "expected_behavior": behav,
        }

    causes = Counter(c.get("primary_cause") for c in cases if c.get("primary_cause"))
    return {
        "fingerprint": fingerprint,
        "pass_rate": pass_rate,
        "n": n,
        "means": {
            "faithfulness": mean(c.get("faithfulness") for c in cases),
            "completeness": mean(c.get("completeness") for c in cases),
            "answer_relevancy": mean(c.get("answer_relevancy") for c in cases),
        },
        "retrieval_level": retrieval_level,
        "retrieval": retrieval_summary,
        "slices": slices,
        "primary_cause_dist": dict(causes),
        "judge_status": judge_status,
    }


def diff_reports(
    old: Mapping[str, Any],
    new: Mapping[str, Any],
    *,
    old_fail_ids: Sequence[str],
    new_fail_ids: Sequence[str],
    old_fingerprint: str,
    new_fingerprint: str,
) -> dict[str, Any]:
    old_fail = set(old_fail_ids)
    new_fail = set(new_fail_ids)
    metric_delta: dict[str, Any] = {
        "pass_rate": (new.get("pass_rate") or 0) - (old.get("pass_rate") or 0),
        "means": {},
        "retrieval": {},
    }
    old_means = old.get("means") or {}
    new_means = new.get("means") or {}
    for key in ("faithfulness", "completeness", "answer_relevancy"):
        ov, nv = old_means.get(key), new_means.get(key)
        if ov is None or nv is None:
            metric_delta["means"][key] = None
        else:
            metric_delta["means"][key] = nv - ov
    old_ret = old.get("retrieval") or {}
    new_ret = new.get("retrieval") or {}
    for key in sorted(set(old_ret) | set(new_ret)):
        if key == "recall" and old.get("retrieval_level") == 1 and new.get("retrieval_level") == 1:
            continue
        try:
            metric_delta["retrieval"][key] = float(new_ret.get(key) or 0) - float(old_ret.get(key) or 0)
        except (TypeError, ValueError):
            metric_delta["retrieval"][key] = None
    return {
        "metric_delta": metric_delta,
        "fixed_fail_count": len(old_fail - new_fail),
        "new_fail_count": len(new_fail - old_fail),
        "still_fail_count": len(old_fail & new_fail),
        "fingerprint_diff": {
            "old": old_fingerprint,
            "new": new_fingerprint,
            "changed": old_fingerprint != new_fingerprint,
        },
    }
