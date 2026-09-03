# RAG Eval

通用 RAG 评测平台（V1）。不替代 RAG，只通过 HTTP Adapter 评测已经开发好的系统。

Dataset → Run → Judge → Human Calibration → Retrieval Metrics → Diagnosis → Experiment（一轮一变量）→ 同集 Regression。

人走 Web，程序走 REST，同一 Eval Core。默认 Closed-domain：答案只能依据本次检索 Context。

## 技术栈（锁定）

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 · SQLite `./data/eval.db`  
Worker：`python -m workers.evaluation_worker`（轮询 PENDING，不强制 Redis）  
Web：Vite + React + TypeScript，只调 `/v1`  
LLM Judge：`OPENAI_API_KEY` / `OPENAI_BASE_URL` / `JUDGE_MODEL`；无 Key 时用 heuristic Judge，Mock 可演示。

评测公式只在 `core/metrics.py` 与 `core/spec.py`。API 不算 Pass、不算 Recall。不引入 RAGAS，不做 MCP。

## 本地启动（四个进程）

在仓库根目录，Python 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env
```

终端 1 — Mock Adapter `:8100`

```powershell
.\.venv\Scripts\python.exe -m adapters.mock_server
```

终端 2 — API `:8000`

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

终端 3 — Worker

```powershell
.\.venv\Scripts\python.exe -m workers.evaluation_worker
```

终端 4 — Web（把 `/v1` 代理到 API）

```powershell
cd web
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5173

写入 Demo 种子（≥8 条、三类 case_type、Confirm 后跑 1 次 Run）：

```powershell
.\.venv\Scripts\python.exe -m api.seed
```

陌生人路径：打开项目 Demo → 数据集已 Confirm → Runs 看进度 → 报告页查看 pass_rate / retrieval / 切片。

## Adapter 合同

`POST {adapter_url}/eval/rag`

```json
{ "query": "总部在哪里？" }
```

响应：`actual_answer`，`retrieved_chunks[{chunk_id,doc_id,text,rank,score}]`，`meta.latency_ms` 必填。`meta` 只允许再带 `model` / `embedding_model` / `rerank_model` / `request_id`。

健康检查：`GET {adapter_url}/health`。接入 BaGuLLM 时，若它还不会说 `/eval/rag`，加一层薄包装，不要另写一套评测语义。

### 接入 BaGuLLM

BaGuLLM 走 AnythingLLM 的 `POST /api/v1/workspace/{slug}/chat`。本仓库提供包装进程，把该接口映射成评测合同：

```powershell
$env:BAGULLM_BASE_URL="http://127.0.0.1:3001"
$env:BAGULLM_API_KEY="你的 BaGuLLM API Key"
$env:BAGULLM_WORKSPACE="java"
$env:BAGULLM_CHAT_MODE="query"
.\.venv\Scripts\python.exe -m adapters.bagullm
```

包装监听 `:8101`。当前名为 `java` 的工作区实际索引的是 AI 笔记（RAG.md / Agent.md / 基本概念.md），不是 Java 语言。黄金集必须按库里真实文档出题：

```powershell
.\.venv\Scripts\python.exe -m api.seed_bagullm
```

Worker 会把新建的 PENDING Run 跑完。评测公式仍只走 `core/`。

## Web 五页

1. 项目：创建、Adapter、Ping、Spec
2. 数据集：编辑、Generate、Confirm、抽校准集
3. 校准：人工标、混淆矩阵、status
4. Runs：填写 rag_version、Start、进度、fail 列表
5. 报告：切片、Diff、创建 experiment

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 评测语义摘要

Pass 当且仅当 BehaviorCorrect AND Faithful AND Complete AND Relevant。门槛只来自 Spec JSON。  
Level 1 只报 `expected_source_hit`、`passage_hit`，报告 JSON 禁止出现 `recall`。  
Level 2 报 Hit / Recall / Precision / MRR，`K=min(spec.k, len(chunks))`。  
Experiment：baseline 与 result 的 fingerprint 相比，仅允许 `rag_version` 中一个 key 不同。
