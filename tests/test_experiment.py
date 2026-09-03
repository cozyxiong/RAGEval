from __future__ import annotations

import pytest

from core.experiment import ExperimentError, single_variable_change
from core.spec import EvaluationSpec
from core.version import fingerprint


def _rv(**kwargs) -> dict[str, str]:
    base = {
        "kb": "kb1",
        "chunk": "512",
        "embedding": "bge",
        "retrieval": "top8",
        "rerank": "none",
        "generator": "gpt",
        "prompt": "p1",
    }
    base.update(kwargs)
    return base


def test_fingerprint_changes_with_each_component() -> None:
    spec_h = EvaluationSpec().spec_hash()
    a = fingerprint(_rv(), "dv1", "ph1", spec_h)
    b = fingerprint(_rv(kb="kb2"), "dv1", "ph1", spec_h)
    c = fingerprint(_rv(), "dv2", "ph1", spec_h)
    d = fingerprint(_rv(), "dv1", "ph2", spec_h)
    e = fingerprint(_rv(), "dv1", "ph1", EvaluationSpec(k=4).spec_hash())
    assert len({a, b, c, d, e}) == 5
    assert a == fingerprint(_rv(), "dv1", "ph1", spec_h)


def test_single_key_ok() -> None:
    spec_h = "s"
    base = _rv()
    result = _rv(rerank="bge-rerank")
    info = single_variable_change(
        baseline_fingerprint=fingerprint(base, "dv", "p", spec_h),
        result_fingerprint=fingerprint(result, "dv", "p", spec_h),
        baseline_rag_version=base,
        result_rag_version=result,
        baseline_dataset_version_id="dv",
        result_dataset_version_id="dv",
        baseline_prompt_hash="p",
        result_prompt_hash="p",
        baseline_spec_hash=spec_h,
        result_spec_hash=spec_h,
    )
    assert info["modified_variable"] == "rerank"
    assert info["modified_from"] == "none"
    assert info["modified_to"] == "bge-rerank"


def test_two_keys_raise() -> None:
    spec_h = "s"
    base = _rv()
    result = _rv(kb="kb2", generator="other")
    with pytest.raises(ExperimentError, match="exactly one"):
        single_variable_change(
            baseline_fingerprint=fingerprint(base, "dv", "p", spec_h),
            result_fingerprint=fingerprint(result, "dv", "p", spec_h),
            baseline_rag_version=base,
            result_rag_version=result,
            baseline_dataset_version_id="dv",
            result_dataset_version_id="dv",
            baseline_prompt_hash="p",
            result_prompt_hash="p",
            baseline_spec_hash=spec_h,
            result_spec_hash=spec_h,
        )


def test_identical_fingerprints_raise() -> None:
    spec_h = "s"
    rv = _rv()
    fp = fingerprint(rv, "dv", "p", spec_h)
    with pytest.raises(ExperimentError, match="identical"):
        single_variable_change(
            baseline_fingerprint=fp,
            result_fingerprint=fp,
            baseline_rag_version=rv,
            result_rag_version=rv,
            baseline_dataset_version_id="dv",
            result_dataset_version_id="dv",
            baseline_prompt_hash="p",
            result_prompt_hash="p",
            baseline_spec_hash=spec_h,
            result_spec_hash=spec_h,
        )
