from __future__ import annotations

from api.seed_bagullm import BAGULLM_CASES


def test_bagullm_gold_covers_three_types_and_real_sources() -> None:
    assert 50 <= len(BAGULLM_CASES) <= 100
    types = {c["case_type"] for c in BAGULLM_CASES}
    assert types == {"answerable", "unanswerable", "ambiguous"}
    answerable = [c for c in BAGULLM_CASES if c["case_type"] == "answerable"]
    unans = [c for c in BAGULLM_CASES if c["case_type"] == "unanswerable"]
    amb = [c for c in BAGULLM_CASES if c["case_type"] == "ambiguous"]
    assert len(answerable) >= 40
    assert len(unans) >= 10
    assert len(amb) >= 8
    assert all(c["expected_source"] for c in answerable)
    assert all(c["supporting_passage"] for c in answerable)
    sources = {s for c in answerable for s in c["expected_source"]}
    assert {"RAG.md", "Agent.md", "基本概念.md"} <= sources
    assert any("Java" in c["query"] for c in unans)
