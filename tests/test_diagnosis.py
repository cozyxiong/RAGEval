from __future__ import annotations

from core.diagnosis import diagnose
from core.spec import EvaluationSpec, PassGate


def _base(**overrides):
    data = dict(
        case_type="unanswerable",
        expected_source=["doc-hq"],
        expected_behavior="answer",
        evaluated_behavior="answer",
        faithfulness=1.0,
        completeness=1.0,
        relevancy=1.0,
        retrieval={"expected_source_hit": 1, "passage_hit": 1, "hit": 1, "precision": 0.9},
        spec=EvaluationSpec(retrieval_level=1, pass_gate=PassGate()),
        passed=False,
    )
    data.update(overrides)
    return diagnose(**data)


def test_rule1_answerable_empty_source_is_dataset_issue() -> None:
    d = _base(case_type="answerable", expected_source=[], retrieval={"expected_source_hit": 0})
    assert d["primary_cause"] == "评测集"


def test_rule2_level1_source_miss_is_recall_gap() -> None:
    d = _base(
        case_type="answerable",
        expected_source=["doc-hq"],
        retrieval={"expected_source_hit": 0, "hit": 0},
        spec=EvaluationSpec(retrieval_level=1),
    )
    assert d["primary_cause"] == "检索漏召回"


def test_rule2_level2_hit_zero() -> None:
    d = _base(
        spec=EvaluationSpec(retrieval_level=2),
        retrieval={"hit": 0, "precision": 0.0, "expected_source_hit": 0},
    )
    assert d["primary_cause"] == "检索漏召回"


def test_rule3_level2_hit_with_low_precision_is_noise() -> None:
    d = _base(
        spec=EvaluationSpec(retrieval_level=2),
        retrieval={"hit": 1, "precision": 0.2, "expected_source_hit": 1},
    )
    assert d["primary_cause"] == "检索噪声"


def test_rule4_hit_low_faithfulness_is_hallucination() -> None:
    d = _base(
        faithfulness=0.1,
        retrieval={"expected_source_hit": 1, "hit": 1, "precision": 0.9},
    )
    assert d["primary_cause"] == "生成幻觉"


def test_rule5_hit_low_completeness_is_poor_generation() -> None:
    d = _base(
        completeness=0.1,
        relevancy=1.0,
        retrieval={"expected_source_hit": 1, "hit": 1, "precision": 0.9},
    )
    assert d["primary_cause"] == "生成答差"


def test_rule6_behavior_mismatch() -> None:
    d = _base(
        expected_behavior="refuse",
        evaluated_behavior="answer",
        case_type="unanswerable",
        retrieval={"expected_source_hit": 1, "hit": 1, "precision": 0.9},
        spec=EvaluationSpec(retrieval_level=1),
    )
    assert d["primary_cause"] == "行为错误"
    assert "Should-Refuse-but-Answered" in d["failure_type"]


def test_first_matching_rule_wins() -> None:
    d = _base(
        case_type="answerable",
        expected_source=[],
        evaluated_behavior="refuse",
        faithfulness=0.0,
        retrieval={"expected_source_hit": 0, "hit": 0},
    )
    assert d["primary_cause"] == "评测集"
    matched = [c["cause"] for c in d["candidates"] if c["matched"]]
    assert matched[0] == "评测集"


def test_passed_has_no_primary_cause() -> None:
    d = _base(passed=True)
    assert d["primary_cause"] is None
