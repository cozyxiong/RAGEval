"""Run fingerprint and rag_version helpers."""

from __future__ import annotations

from typing import Any

from core.spec import RAG_VERSION_KEYS, canonical_json, normalize_rag_version, sha256_hex


def fingerprint(
    rag_version: dict[str, Any],
    dataset_version_id: str,
    judge_prompt_hash: str,
    spec_hash: str,
) -> str:
    payload = (
        canonical_json(normalize_rag_version(rag_version))
        + str(dataset_version_id)
        + str(judge_prompt_hash)
        + str(spec_hash)
    )
    return sha256_hex(payload)


def rag_version_diff(baseline: dict[str, Any], result: dict[str, Any]) -> list[str]:
    """Return rag_version keys whose values differ."""
    a = normalize_rag_version(baseline)
    b = normalize_rag_version(result)
    return [k for k in RAG_VERSION_KEYS if a[k] != b[k]]
