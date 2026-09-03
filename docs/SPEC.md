# RAG Eval V1 — 实现规格（澄清版）

语义与 V1 范围以桌面原稿为准。本文只澄清实现边界，不发明第二套评测语义，不更换技术栈。

## 锁定

- 技术栈：Python 3.12，FastAPI，Pydantic v2，SQLAlchemy 2，SQLite `./data/eval.db`，Vite+React+TS，pytest。
- 公式只在 `core/metrics.py` 与 `core/spec.py`。
- 不做 MCP / Skill / RAGAS / 改对方 RAG / 自动调参 / Level 3 UI / 多租户 / K8s。

## 澄清

1. Adapter ping：`GET {adapter_url}/health`；API `POST /v1/projects/{id}/adapter/ping`。
2. `expected_source_hit`：任一 retrieved `doc_id` 或 `chunk_id` 落在 `expected_source` 则为 1。
3. `passage_hit`：任一 `supporting_passage` 是 retrieved `text` 的子串（大小写不敏感）。
4. Level 2 相关匹配：优先 `chunk_id`，否则 `doc_id`。relevant = `label >= 2`。
5. 「precision 低」：Level 2 且 `hit==1` 且 `precision < 0.5`（诊断规则，不是 Pass 门槛）。
6. 校准：从已 Confirm 黄金集分层抽到 calibration version；人工 PATCH case_results；`POST /v1/judge-configs/{id}/calibrate` 用 `core.metrics.calibration_rates`。
7. Experiment：同一 `dataset_version_id`、同一 judge `prompt_hash`、同一 `spec_hash`，且 `rag_version` 恰好一个 key 不同，否则 400。
8. Adapter `meta` 多余键：校验时丢弃，只持久化允许键。
9. Generate 无 LLM Key：按 hints 写草稿；有 Key 则尝试 LLM 起草。未 Confirm 不能跑 Run。
10. BaGuLLM：走同一 `POST /eval/rag` 合同；不兼容时只允许 Adapter 包装。

## 默认 Spec

见 `core.spec.DEFAULT_SPEC` / 原稿 JSON。阈值禁止在 metrics 里写死 0.85。
