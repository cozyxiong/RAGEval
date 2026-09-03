from __future__ import annotations

from typing import Any

from api.jsonutil import dumps, loads
from api.models import DatasetCase
from api.schemas import CaseIn, CaseOut
from core.spec import canonical_json, sha256_hex


def case_to_out(row: DatasetCase) -> CaseOut:
    return CaseOut(
        id=row.id,
        dataset_version_id=row.dataset_version_id,
        case_id=row.case_id,
        query=row.query,
        case_type=row.case_type,  # type: ignore[arg-type]
        expected_behavior=row.expected_behavior,  # type: ignore[arg-type]
        expected_answer=row.expected_answer,
        expected_source=loads(row.expected_source_json, []),
        supporting_passage=loads(row.supporting_passage_json, []),
        relevant_chunks=loads(row.relevant_chunks_json, []),
        tags=loads(row.tags_json, []),
    )


def apply_case_fields(row: DatasetCase, body: CaseIn) -> None:
    row.query = body.query
    row.case_type = body.case_type
    row.expected_behavior = body.expected_behavior
    row.expected_answer = body.expected_answer
    row.expected_source_json = dumps(body.expected_source)
    row.supporting_passage_json = dumps(body.supporting_passage)
    row.relevant_chunks_json = dumps([c.model_dump() for c in body.relevant_chunks])
    row.tags_json = dumps(body.tags)


def case_payload(row: DatasetCase) -> dict[str, Any]:
    return {
        "case_id": row.case_id,
        "query": row.query,
        "case_type": row.case_type,
        "expected_behavior": row.expected_behavior,
        "expected_answer": row.expected_answer,
        "expected_source": loads(row.expected_source_json, []),
        "supporting_passage": loads(row.supporting_passage_json, []),
        "relevant_chunks": loads(row.relevant_chunks_json, []),
        "tags": loads(row.tags_json, []),
    }


def version_hash(cases: list[DatasetCase]) -> str:
    payload = [case_payload(c) for c in sorted(cases, key=lambda r: r.case_id)]
    return sha256_hex(canonical_json(payload))
