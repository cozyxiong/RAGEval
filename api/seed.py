"""Seed a Demo project against the Mock adapter."""

from __future__ import annotations

from api.db import SessionLocal, init_db
from api.jsonutil import dumps
from api.models import Dataset, DatasetCase, DatasetVersion, Project
from api.caseutil import version_hash
from api.models import utcnow
from api.services import get_or_create_judge_config, make_run
from core.spec import DEFAULT_SPEC, normalize_rag_version
from workers.evaluation_worker import process_run

DEMO_NAME = "Demo"
DEMO_ADAPTER = "http://127.0.0.1:8100"

DEMO_CASES = [
    {
        "case_id": "gold-hq-where",
        "query": "Acme Robotics 总部在哪里？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "新加坡",
        "expected_source": ["doc-hq"],
        "supporting_passage": ["总部设在新加坡"],
        "relevant_chunks": [{"chunk_id": "c-hq-1", "doc_id": "doc-hq", "label": 2}],
        "tags": ["hq"],
    },
    {
        "case_id": "gold-hq-city",
        "query": "Acme Robotics 总部位于哪个城市？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "新加坡",
        "expected_source": ["doc-hq"],
        "supporting_passage": ["总部设在新加坡"],
        "relevant_chunks": [{"chunk_id": "c-hq-1", "doc_id": "doc-hq", "label": 2}],
        "tags": ["hq"],
    },
    {
        "case_id": "gold-hq-country",
        "query": "公司总部在哪个国家？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "新加坡",
        "expected_source": ["doc-hq"],
        "supporting_passage": ["新加坡"],
        "relevant_chunks": [{"chunk_id": "c-hq-1", "doc_id": "doc-hq", "label": 2}],
        "tags": ["hq"],
    },
    {
        "case_id": "gold-product",
        "query": "Acme Robotics 生产什么产品？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "仓储机器人",
        "expected_source": ["doc-product"],
        "supporting_passage": ["仓储机器人"],
        "relevant_chunks": [{"chunk_id": "c-product-1", "doc_id": "doc-product", "label": 2}],
        "tags": ["product"],
    },
    {
        "case_id": "gold-founded",
        "query": "Acme Robotics 是哪年成立的？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "2018",
        "expected_source": ["doc-history"],
        "supporting_passage": ["成立于 2018"],
        "relevant_chunks": [{"chunk_id": "c-history-1", "doc_id": "doc-history", "label": 2}],
        "tags": ["history"],
    },
    {
        "case_id": "gold-salary",
        "query": "公司 CEO 年薪是多少？",
        "case_type": "unanswerable",
        "expected_behavior": "refuse",
        "expected_answer": "",
        "expected_source": [],
        "supporting_passage": [],
        "relevant_chunks": [],
        "tags": ["finance"],
    },
    {
        "case_id": "gold-revenue",
        "query": "2024 年营收是多少？",
        "case_type": "unanswerable",
        "expected_behavior": "refuse",
        "expected_answer": "",
        "expected_source": [],
        "supporting_passage": [],
        "relevant_chunks": [],
        "tags": ["finance"],
    },
    {
        "case_id": "gold-office",
        "query": "办公室在哪？",
        "case_type": "ambiguous",
        "expected_behavior": "clarify",
        "expected_answer": "",
        "expected_source": ["doc-hq"],
        "supporting_passage": [],
        "relevant_chunks": [{"chunk_id": "c-hq-1", "doc_id": "doc-hq", "label": 1}],
        "tags": ["office"],
    },
    {
        "case_id": "gold-mars",
        "query": "火星工厂有多少员工？",
        "case_type": "unanswerable",
        "expected_behavior": "refuse",
        "expected_answer": "",
        "expected_source": [],
        "supporting_passage": [],
        "relevant_chunks": [],
        "tags": ["ood"],
    },
]


def seed_demo(adapter_url: str = DEMO_ADAPTER, process: bool = True) -> dict[str, str]:
    init_db()
    db = SessionLocal()
    try:
        project = db.query(Project).filter_by(name=DEMO_NAME).first()
        if not project:
            project = Project(
                name=DEMO_NAME,
                adapter_url=adapter_url.rstrip("/"),
                product_mode="closed_domain",
                spec_json=dumps(DEFAULT_SPEC.to_json_dict()),
                created_at=utcnow(),
            )
            db.add(project)
            db.flush()
        else:
            project.adapter_url = adapter_url.rstrip("/")
        ds = (
            db.query(Dataset)
            .filter_by(project_id=project.id, kind="gold", name="demo-gold")
            .first()
        )
        if not ds:
            ds = Dataset(project_id=project.id, kind="gold", name="demo-gold")
            db.add(ds)
            db.flush()
        ver = (
            db.query(DatasetVersion)
            .filter_by(dataset_id=ds.id)
            .order_by(DatasetVersion.version.desc())
            .first()
        )
        if not ver:
            ver = DatasetVersion(dataset_id=ds.id, version=1, hash="")
            db.add(ver)
            db.flush()
        if ver.confirmed_at is None:
            db.query(DatasetCase).filter_by(dataset_version_id=ver.id).delete()
            for item in DEMO_CASES:
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
            ver.hash = version_hash(cases)
            ver.confirmed_at = utcnow()
        types = {
            c.case_type
            for c in db.query(DatasetCase).filter_by(dataset_version_id=ver.id).all()
        }
        if not {"answerable", "unanswerable", "ambiguous"} <= types:
            raise RuntimeError(f"seed cases missing types: {types}")
        n = db.query(DatasetCase).filter_by(dataset_version_id=ver.id).count()
        if n < 8:
            raise RuntimeError(f"seed needs >=8 cases, got {n}")
        judge_cfg = get_or_create_judge_config(db, project)
        from api.models import Run

        existing = (
            db.query(Run)
            .filter_by(project_id=project.id, dataset_version_id=ver.id, status="COMPLETED")
            .first()
        )
        if existing:
            run_id = existing.id
        else:
            rag = normalize_rag_version(
                {
                    "kb": "mock-kb",
                    "chunk": "naive",
                    "embedding": "mock-embed",
                    "retrieval": "keyword",
                    "rerank": "none",
                    "generator": "mock-generator",
                    "prompt": "closed-v1",
                }
            )
            run = make_run(db, project, ver.id, judge_cfg, rag, n)
            run_id = run.id
            db.commit()
            if process:
                process_run(run_id)
            return {
                "project_id": project.id,
                "dataset_version_id": ver.id,
                "run_id": run_id,
                "n": str(n),
            }
        db.commit()
        return {
            "project_id": project.id,
            "dataset_version_id": ver.id,
            "run_id": run_id,
            "n": str(n),
        }
    finally:
        db.close()


def main() -> None:
    info = seed_demo()
    print(info)


if __name__ == "__main__":
    main()
