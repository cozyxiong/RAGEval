from __future__ import annotations

import os

from fastapi.testclient import TestClient

from adapters.mock_server import app as mock_app
from core.judge import heuristic_judge, judge
from core.metrics import completeness_score, faithfulness_score, pass_
from core.spec import DEFAULT_SPEC, EvaluationSpec, PassGate

HQ_QUERY = "总部在哪里？"
HQ_ANSWER = "Acme Robotics 总部在新加坡。"
HQ_CHUNKS = [
    {
        "chunk_id": "c-hq-1",
        "doc_id": "doc-hq",
        "text": "Acme Robotics 总部设在新加坡（Singapore）。公司注册地址位于新加坡滨海湾金融中心。",
        "rank": 1,
        "score": 0.96,
    }
]


def test_heuristic_refuse_has_no_claims_and_faithfulness_one() -> None:
    os.environ.pop("OPENAI_API_KEY", None)
    result = heuristic_judge(
        query="营收多少",
        actual_answer="根据本次检索到的资料，我无法回答该问题。",
        retrieved_chunks=[],
        expected_answer="",
        expected_behavior="refuse",
    )
    assert result["evaluated_behavior"] == "refuse"
    assert result["claims"] == []
    assert result["provider"] == "heuristic"
    assert "pass" not in result
    assert faithfulness_score(result["claims"]) == 1.0


def test_heuristic_hq_answer_uses_passage() -> None:
    result = heuristic_judge(
        query=HQ_QUERY,
        actual_answer=HQ_ANSWER,
        retrieved_chunks=HQ_CHUNKS,
        expected_answer="新加坡",
        expected_behavior="answer",
    )
    assert result["evaluated_behavior"] == "answer"
    assert result["claims"]
    assert any(c["supported"] for c in result["claims"])


def test_cjk_query_relevancy_without_expected_answer_meets_default_gate() -> None:
    """re.split(\\W+) would score 总部在哪里 vs 总部在新加坡 as 0.0."""
    os.environ.pop("OPENAI_API_KEY", None)
    spec = EvaluationSpec()
    result = heuristic_judge(
        query=HQ_QUERY,
        actual_answer=HQ_ANSWER,
        retrieved_chunks=HQ_CHUNKS,
        expected_answer="",
        expected_behavior="answer",
    )
    assert result["answer_relevancy"] >= spec.pass_gate.relevancy


def test_mock_singapore_hq_passes_default_spec_heuristic() -> None:
    os.environ.pop("OPENAI_API_KEY", None)
    spec = EvaluationSpec()
    assert spec.pass_gate.relevancy == DEFAULT_SPEC.pass_gate.relevancy
    client = TestClient(mock_app)
    body = client.post("/eval/rag", json={"query": HQ_QUERY}).json()
    assert "新加坡" in body["actual_answer"] or "Singapore" in body["actual_answer"]
    verdict = judge(
        query=HQ_QUERY,
        actual_answer=body["actual_answer"],
        retrieved_chunks=body["retrieved_chunks"],
        expected_answer="新加坡",
        expected_behavior="answer",
        spec=spec,
    )
    assert verdict["provider"] == "heuristic"
    passed = pass_(
        evaluated_behavior=verdict["evaluated_behavior"],
        expected_behavior="answer",
        faithfulness=faithfulness_score(verdict["claims"]),
        completeness=completeness_score(
            verdict.get("covered_points"), verdict.get("expected_points")
        ),
        relevancy=verdict["answer_relevancy"],
        spec=spec,
    )
    assert verdict["answer_relevancy"] >= spec.pass_gate.relevancy
    assert passed is True


def test_judge_without_key_is_heuristic_and_label_from_metrics() -> None:
    os.environ.pop("OPENAI_API_KEY", None)
    spec = EvaluationSpec(pass_gate=PassGate(faithfulness=0.5, completeness=0.5, relevancy=0.1))
    verdict = judge(
        query="总部在哪里？",
        actual_answer="总部在新加坡。",
        retrieved_chunks=[
            {
                "chunk_id": "c-hq-1",
                "doc_id": "doc-hq",
                "text": "总部设在新加坡",
                "rank": 1,
                "score": 1.0,
            }
        ],
        expected_answer="新加坡",
        expected_behavior="answer",
        spec=spec,
    )
    assert verdict["provider"] == "heuristic"
    passed = pass_(
        evaluated_behavior=verdict["evaluated_behavior"],
        expected_behavior="answer",
        faithfulness=faithfulness_score(verdict["claims"]),
        completeness=completeness_score(
            verdict.get("covered_points"), verdict.get("expected_points")
        ),
        relevancy=verdict["answer_relevancy"],
        spec=spec,
    )
    assert isinstance(passed, bool)
    assert verdict.get("judge_label") is None
    assert "pass" not in verdict or verdict.get("pass") is None
