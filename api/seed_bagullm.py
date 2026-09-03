"""Gold set grounded in the BaGuLLM `java` workspace vault.

That workspace is named Java but indexed files are AI notes
(RAG.md / Agent.md / 基本概念.md / LLM.md / MCP.md), not the Java language.
Cases live in gold_bagullm.json (50-100 items).
"""

from __future__ import annotations

import json
from pathlib import Path

from api.caseutil import version_hash
from api.db import SessionLocal, init_db
from api.jsonutil import dumps
from api.models import Dataset, DatasetCase, DatasetVersion, Project, utcnow
from api.services import get_or_create_judge_config, make_run
from core.spec import EvaluationSpec, normalize_rag_version

PROJECT_NAME = "BaGuLLM-Java"
ADAPTER_URL = "http://127.0.0.1:8101"
GOLD_PATH = Path(__file__).with_name("gold_bagullm.json")
BAGULLM_CASES: list[dict] = json.loads(GOLD_PATH.read_text(encoding="utf-8"))


def seed_bagullm(adapter_url: str = ADAPTER_URL, process: bool = False) -> dict[str, str]:
    init_db()
    db = SessionLocal()
    try:
        spec = EvaluationSpec()
        spec.adapter.timeout_ms = 180_000
        project = db.query(Project).filter_by(name=PROJECT_NAME).first()
        if not project:
            project = Project(
                name=PROJECT_NAME,
                adapter_url=adapter_url.rstrip("/"),
                product_mode="closed_domain",
                spec_json=dumps(spec.to_json_dict()),
                created_at=utcnow(),
            )
            db.add(project)
            db.flush()
        else:
            project.adapter_url = adapter_url.rstrip("/")
            project.spec_json = dumps(spec.to_json_dict())
        ds = (
            db.query(Dataset)
            .filter_by(project_id=project.id, kind="gold", name="bagu-gold")
            .first()
        )
        if not ds:
            ds = Dataset(project_id=project.id, kind="gold", name="bagu-gold")
            db.add(ds)
            db.flush()
        last = (
            db.query(DatasetVersion)
            .filter_by(dataset_id=ds.id)
            .order_by(DatasetVersion.version.desc())
            .first()
        )
        ver = DatasetVersion(dataset_id=ds.id, version=(last.version + 1) if last else 1, hash="")
        db.add(ver)
        db.flush()
        for item in BAGULLM_CASES:
            db.add(
                DatasetCase(
                    dataset_version_id=ver.id,
                    case_id=item["case_id"],
                    query=item["query"],
                    case_type=item["case_type"],
                    expected_behavior=item["expected_behavior"],
                    expected_answer=item["expected_answer"],
                    expected_source_json=dumps(item["expected_source"]),
                    supporting_passage_json=dumps(item["supporting_passage"]),
                    relevant_chunks_json=dumps(item["relevant_chunks"]),
                    tags_json=dumps(item["tags"]),
                )
            )
        db.flush()
        cases = db.query(DatasetCase).filter_by(dataset_version_id=ver.id).all()
        types = {c.case_type for c in cases}
        if not {"answerable", "unanswerable", "ambiguous"} <= types:
            raise RuntimeError(f"bagullm gold missing types: {types}")
        if not (50 <= len(cases) <= 100):
            raise RuntimeError(f"bagullm gold must be 50-100 cases, got {len(cases)}")
        ver.hash = version_hash(cases)
        ver.confirmed_at = utcnow()
        db.commit()
        run_id = ""
        if process:
            judge_cfg = get_or_create_judge_config(db, project)
            rag = normalize_rag_version(
                {
                    "kb": "java-vault",
                    "chunk": "vault-section",
                    "embedding": "bagullm",
                    "retrieval": "query-mode",
                    "rerank": "none",
                    "generator": "bagullm",
                    "prompt": "closed-v1",
                }
            )
            run = make_run(db, project, ver.id, judge_cfg, rag, len(cases))
            db.commit()
            from workers.evaluation_worker import process_run

            process_run(run.id)
            run_id = run.id
        return {
            "project_id": project.id,
            "dataset_version_id": ver.id,
            "run_id": run_id,
            "n": str(len(cases)),
        }
    finally:
        db.close()


def main() -> None:
    print(seed_bagullm(process=False))


if __name__ == "__main__":
    main()
