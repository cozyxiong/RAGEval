"""Single-variable experiment check. API returns 400 unless exactly one rag_version key differs."""

from __future__ import annotations

from typing import Any

from core.version import rag_version_diff


class ExperimentError(ValueError):
    pass


def single_variable_change(
    *,
    baseline_fingerprint: str,
    result_fingerprint: str,
    baseline_rag_version: dict[str, Any],
    result_rag_version: dict[str, Any],
    baseline_dataset_version_id: str,
    result_dataset_version_id: str,
    baseline_prompt_hash: str,
    result_prompt_hash: str,
    baseline_spec_hash: str,
    result_spec_hash: str,
) -> dict[str, str]:
    if baseline_dataset_version_id != result_dataset_version_id:
        raise ExperimentError("dataset_version_id must be identical")
    if baseline_prompt_hash != result_prompt_hash:
        raise ExperimentError("judge prompt_hash must be identical")
    if baseline_spec_hash != result_spec_hash:
        raise ExperimentError("spec_hash must be identical")
    if baseline_fingerprint == result_fingerprint:
        raise ExperimentError("fingerprints are identical; no variable changed")
    changed = rag_version_diff(baseline_rag_version, result_rag_version)
    if len(changed) != 1:
        raise ExperimentError(
            f"exactly one rag_version key may differ, got {changed or 'none'}"
        )
    key = changed[0]
    return {
        "modified_variable": key,
        "modified_from": str(baseline_rag_version.get(key, "")),
        "modified_to": str(result_rag_version.get(key, "")),
    }
