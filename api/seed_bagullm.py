"""Gold set grounded in the BaGuLLM `java` workspace vault.

That workspace is named Java but indexed files are AI notes
(RAG.md / Agent.md / 基本概念.md / LLM.md / MCP.md), not the Java language.
"""

from __future__ import annotations

from api.caseutil import version_hash
from api.db import SessionLocal, init_db
from api.jsonutil import dumps
from api.models import Dataset, DatasetCase, DatasetVersion, Project, utcnow
from api.services import get_or_create_judge_config, make_run
from core.spec import EvaluationSpec, normalize_rag_version

PROJECT_NAME = "BaGuLLM-Java"
ADAPTER_URL = "http://127.0.0.1:8101"

BAGULLM_CASES = [
    {
        "case_id": "bagu-rag-def",
        "query": "什么是 RAG？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "检索增强生成",
        "expected_source": ["RAG.md"],
        "supporting_passage": ["Retrieval-Augmented Generation"],
        "relevant_chunks": [{"doc_id": "RAG.md", "label": 2}],
        "tags": ["rag"],
    },
    {
        "case_id": "bagu-rag-flow",
        "query": "RAG 的核心逻辑分成哪两步？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "先从资料库中检索相关内容，再基于这些内容生成答案",
        "expected_source": ["RAG.md"],
        "supporting_passage": ["先从资料库中检索相关内容"],
        "relevant_chunks": [{"doc_id": "RAG.md", "label": 2}],
        "tags": ["rag"],
    },
    {
        "case_id": "bagu-rag-chunk",
        "query": "RAG 离线阶段的分块是做什么？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "将完整的文档切分为多个小片段",
        "expected_source": ["RAG.md"],
        "supporting_passage": ["将完整的文档切分为多个小片段"],
        "relevant_chunks": [{"doc_id": "RAG.md", "label": 2}],
        "tags": ["rag"],
    },
    {
        "case_id": "bagu-agent-formula",
        "query": "资料里 Agent 的组成公式是什么？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "LLM + 记忆 + 规划 + 工具使用",
        "expected_source": ["Agent.md"],
        "supporting_passage": ["Agent = LLM  + 记忆 + 规划 + 工具使用"],
        "relevant_chunks": [{"doc_id": "Agent.md", "label": 2}],
        "tags": ["agent"],
    },
    {
        "case_id": "bagu-agent-cursor",
        "query": "资料里 Cursor 被归为什么类型的 Agent？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "编程类 Agent",
        "expected_source": ["Agent.md"],
        "supporting_passage": ["Cursor：编程类 Agent"],
        "relevant_chunks": [{"doc_id": "Agent.md", "label": 2}],
        "tags": ["agent"],
    },
    {
        "case_id": "bagu-token",
        "query": "什么是 Token？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "大模型处理文本的最小单位",
        "expected_source": ["基本概念.md"],
        "supporting_passage": ["大模型处理文本的最小单位"],
        "relevant_chunks": [{"doc_id": "基本概念.md", "label": 2}],
        "tags": ["llm"],
    },
    {
        "case_id": "bagu-mcp",
        "query": "MCP 是用来解决什么问题的？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "不同平台工具接入规范不统一",
        "expected_source": ["基本概念.md", "MCP.md"],
        "supporting_passage": ["工具接入的统一标准"],
        "relevant_chunks": [{"doc_id": "基本概念.md", "label": 2}],
        "tags": ["mcp"],
    },
    {
        "case_id": "bagu-llm-transformer",
        "query": "资料里 LLM 的底层架构是什么？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "Transformer",
        "expected_source": ["基本概念.md", "MCP.md"],
        "supporting_passage": ["基于 Transformer"],
        "relevant_chunks": [{"doc_id": "基本概念.md", "label": 2}],
        "tags": ["llm"],
    },
    {
        "case_id": "bagu-llm-flash",
        "query": "Flash/Turbo 这类模型适合什么场景？",
        "case_type": "answerable",
        "expected_behavior": "answer",
        "expected_answer": "高并发或实时",
        "expected_source": ["LLM.md"],
        "supporting_passage": ["适合高并发或实时场景"],
        "relevant_chunks": [{"doc_id": "LLM.md", "label": 2}],
        "tags": ["llm"],
    },
    {
        "case_id": "bagu-unans-java-generics",
        "query": "Java 泛型是在哪个版本加入的？",
        "case_type": "unanswerable",
        "expected_behavior": "refuse",
        "expected_answer": "",
        "expected_source": [],
        "supporting_passage": [],
        "relevant_chunks": [],
        "tags": ["ood"],
    },
    {
        "case_id": "bagu-unans-revenue",
        "query": "OpenAI 2024 年营收是多少？",
        "case_type": "unanswerable",
        "expected_behavior": "refuse",
        "expected_answer": "",
        "expected_source": [],
        "supporting_passage": [],
        "relevant_chunks": [],
        "tags": ["ood"],
    },
    {
        "case_id": "bagu-unans-mars",
        "query": "火星工厂现在有多少员工？",
        "case_type": "unanswerable",
        "expected_behavior": "refuse",
        "expected_answer": "",
        "expected_source": [],
        "supporting_passage": [],
        "relevant_chunks": [],
        "tags": ["ood"],
    },
    {
        "case_id": "bagu-amb-model",
        "query": "那个模型应该怎么选？",
        "case_type": "ambiguous",
        "expected_behavior": "clarify",
        "expected_answer": "",
        "expected_source": ["LLM.md"],
        "supporting_passage": [],
        "relevant_chunks": [{"doc_id": "LLM.md", "label": 1}],
        "tags": ["ambiguous"],
    },
    {
        "case_id": "bagu-amb-memory",
        "query": "记忆是指哪一层？",
        "case_type": "ambiguous",
        "expected_behavior": "clarify",
        "expected_answer": "",
        "expected_source": ["Agent.md"],
        "supporting_passage": [],
        "relevant_chunks": [{"doc_id": "Agent.md", "label": 1}],
        "tags": ["ambiguous"],
    },
    {
        "case_id": "bagu-amb-agent-how",
        "query": "Agent 怎么做？",
        "case_type": "ambiguous",
        "expected_behavior": "clarify",
        "expected_answer": "",
        "expected_source": ["Agent.md"],
        "supporting_passage": [],
        "relevant_chunks": [{"doc_id": "Agent.md", "label": 1}],
        "tags": ["ambiguous"],
    },
]


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
        if len(cases) < 8:
            raise RuntimeError(f"bagullm gold needs >=8 cases, got {len(cases)}")
        ver.hash = version_hash(cases)
        ver.confirmed_at = utcnow()
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
        if process:
            from workers.evaluation_worker import process_run

            process_run(run.id)
        return {
            "project_id": project.id,
            "dataset_version_id": ver.id,
            "run_id": run.id,
            "n": str(len(cases)),
        }
    finally:
        db.close()


def main() -> None:
    print(seed_bagullm(process=False))


if __name__ == "__main__":
    main()
