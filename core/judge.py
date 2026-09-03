"""Builtin Judge. LLM JSON when OPENAI_API_KEY is set; heuristic otherwise.

judge_label is NEVER taken from the model. Callers must run metrics.pass_.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Sequence

import httpx

from core.spec import EvaluationSpec, parse_spec, sha256_hex

JUDGE_SYSTEM_PROMPT = """你是 Closed-domain RAG 评测 Judge。只依据本次检索到的 chunks，不得使用世界知识。
任务：
1. 识别 actual_answer 的行为 evaluated_behavior：answer / refuse / clarify。
2. 将答案拆成原子 claims，每条标记 supported：该 claim 是否被本次 chunks 支撑。
3. 对照 expected_answer 列出要点 expected_points，并给出 covered_points（被答案覆盖的要点）。
4. 输出 faithfulness、completeness、answer_relevancy，均为 0 到 1 的小数。
5. 不得因措辞不同直接判失败。
6. 只输出 JSON，不要 Markdown。

JSON 形状：
{
  "evaluated_behavior": "answer|refuse|clarify",
  "claims": [{"text": "...", "supported": true}],
  "expected_points": ["..."],
  "covered_points": ["..."],
  "faithfulness": 0.0,
  "completeness": 0.0,
  "answer_relevancy": 0.0,
  "reason": "..."
}
"""

REFUSE_KEYWORDS = (
    "无法回答",
    "无法作答",
    "无法根据",
    "没有足够",
    "资料不足",
    "检索到的资料",
    "不知道",
    "不清楚",
    "不能回答",
    "超出",
    "拒绝",
    "i don't know",
    "i do not know",
    "cannot answer",
    "can't answer",
    "not enough information",
    "insufficient information",
    "unable to answer",
)

CLARIFY_KEYWORDS = (
    "请问",
    "能否明确",
    "你指的是",
    "您指的是",
    "需要更多信息",
    "请补充",
    "哪一个",
    "clarify",
    "could you specify",
    "which one",
)


def prompt_hash(prompt_text: str | None = None) -> str:
    return sha256_hex(prompt_text or JUDGE_SYSTEM_PROMPT)


def _has_llm_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _detect_behavior(answer: str) -> str:
    text = answer.strip()
    lower = text.lower()
    if any(k.lower() in lower for k in CLARIFY_KEYWORDS):
        return "clarify"
    if any(k.lower() in lower for k in REFUSE_KEYWORDS):
        return "refuse"
    if not text:
        return "refuse"
    return "answer"


_LATIN_WORD = re.compile(r"[A-Za-z0-9]+")
_CJK_RUN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]+")
_CONTENT_STOP = frozenset(
    {
        "哪",
        "里",
        "儿",
        "吗",
        "呢",
        "谁",
        "何",
        "几",
        "啊",
        "吧",
        "么",
        "呀",
        "的",
        "了",
        "是",
        "有",
        "和",
        "与",
        "或",
        "也",
        "都",
        "吗呢",
        "哪里",
        "哪儿",
        "什么",
        "怎么",
        "如何",
        "多少",
        "为何",
        "为什么",
        "是否",
        "可否",
        "哪个",
        "哪些",
        "怎样",
        "在哪",
        "什么样",
        "what",
        "where",
        "when",
        "who",
        "whom",
        "which",
        "how",
        "why",
        "is",
        "are",
        "was",
        "were",
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "does",
        "do",
        "did",
        "please",
    }
)


def _content_tokens(text: str) -> list[str]:
    """Latin words plus CJK bigrams. ``re.split(\\W+)`` keeps a CJK clause as one token
    and cannot score 总部在哪里 against 总部在新加坡.
    """
    if not text:
        return []
    raw = text.lower()
    tokens: list[str] = []
    for match in _LATIN_WORD.finditer(raw):
        word = match.group(0)
        if len(word) >= 2 and word not in _CONTENT_STOP:
            tokens.append(word)
    for match in _CJK_RUN.finditer(raw):
        run = match.group(0)
        if len(run) == 1:
            if run not in _CONTENT_STOP:
                tokens.append(run)
            continue
        for i in range(len(run) - 1):
            bigram = run[i : i + 2]
            if bigram not in _CONTENT_STOP:
                tokens.append(bigram)
    return tokens


def _token_overlap(query: str, haystack: str) -> float:
    q_tokens = _content_tokens(query)
    if not q_tokens:
        return 0.5
    h_tokens = set(_content_tokens(haystack))
    h_lower = haystack.lower()
    hits = sum(1 for tok in q_tokens if tok in h_tokens or tok in h_lower)
    return min(1.0, max(0.0, hits / len(q_tokens)))


def _split_claims(answer: str) -> list[str]:
    parts = re.split(r"[。；;.\n]+", answer)
    return [p.strip() for p in parts if p.strip()]


def _supported(claim: str, chunks: Sequence[dict[str, Any]]) -> bool:
    blob = " ".join(str(c.get("text") or "") for c in chunks)
    if not blob:
        return False
    tokens = _content_tokens(claim)
    if not tokens:
        return claim.lower() in blob.lower()
    blob_l = blob.lower()
    blob_tokens = set(_content_tokens(blob))
    hits = sum(1 for tok in tokens if tok in blob_tokens or tok in blob_l)
    return hits >= max(1, (len(tokens) + 2) // 3)


def _expected_points(expected_answer: str) -> list[str]:
    return _split_claims(expected_answer)


def heuristic_judge(
    *,
    query: str,
    actual_answer: str,
    retrieved_chunks: Sequence[dict[str, Any]],
    expected_answer: str = "",
    expected_behavior: str = "answer",
) -> dict[str, Any]:
    behavior = _detect_behavior(actual_answer)
    if behavior == "refuse":
        claims: list[dict[str, Any]] = []
        faithfulness = 1.0
    else:
        raw_claims = _split_claims(actual_answer)
        claims = [{"text": c, "supported": _supported(c, retrieved_chunks)} for c in raw_claims]
        faithfulness = (
            1.0
            if not claims
            else sum(1 for c in claims if c["supported"]) / len(claims)
        )
    points = _expected_points(expected_answer)
    covered: list[str] = []
    answer_l = actual_answer.lower()
    chunk_blob = " ".join(str(c.get("text") or "") for c in retrieved_chunks).lower()
    for p in points:
        if p.lower() in answer_l or p.lower() in chunk_blob:
            covered.append(p)
    completeness = 1.0 if not points else len(covered) / len(points)
    if behavior == "refuse":
        relevancy = 1.0 if expected_behavior == "refuse" else 0.0
    elif behavior == "clarify":
        relevancy = 1.0 if expected_behavior == "clarify" else 0.4
    else:
        expected = (expected_answer or "").strip()
        if expected and expected.lower() in actual_answer.lower():
            relevancy = 1.0
        else:
            relevancy = _token_overlap(query, actual_answer)
    return {
        "evaluated_behavior": behavior,
        "claims": claims,
        "expected_points": points,
        "covered_points": covered,
        "faithfulness": round(faithfulness, 4),
        "completeness": round(completeness, 4),
        "answer_relevancy": round(float(relevancy), 4),
        "reason": "heuristic judge",
        "provider": "heuristic",
    }


def _chat_complete(messages: list[dict[str, str]], model: str) -> str:
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY", "")
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


def _parse_llm_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text)
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def llm_judge(
    *,
    query: str,
    actual_answer: str,
    retrieved_chunks: Sequence[dict[str, Any]],
    expected_answer: str,
    expected_behavior: str,
    spec: EvaluationSpec,
) -> dict[str, Any]:
    model = os.environ.get("JUDGE_MODEL") or spec.judge.model
    user = json.dumps(
        {
            "query": query,
            "actual_answer": actual_answer,
            "retrieved_chunks": [
                {"chunk_id": c.get("chunk_id"), "doc_id": c.get("doc_id"), "text": c.get("text")}
                for c in retrieved_chunks
            ],
            "expected_answer": expected_answer,
            "expected_behavior": expected_behavior,
            "product_mode": spec.product_mode,
        },
        ensure_ascii=False,
    )
    content = _chat_complete(
        [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        model=model,
    )
    data = _parse_llm_json(content)
    claims = data.get("claims") or []
    points = data.get("expected_points") or []
    covered = data.get("covered_points") or []
    return {
        "evaluated_behavior": data.get("evaluated_behavior") or _detect_behavior(actual_answer),
        "claims": claims,
        "expected_points": points,
        "covered_points": covered,
        "faithfulness": float(data.get("faithfulness", 0)),
        "completeness": float(data.get("completeness", 0)),
        "answer_relevancy": float(data.get("answer_relevancy", 0)),
        "reason": data.get("reason") or "llm judge",
        "provider": "llm",
    }


def judge(
    *,
    query: str,
    actual_answer: str,
    retrieved_chunks: Sequence[dict[str, Any]],
    expected_answer: str = "",
    expected_behavior: str = "answer",
    spec: EvaluationSpec | dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec_obj = parse_spec(spec)
    if _has_llm_key():
        try:
            return llm_judge(
                query=query,
                actual_answer=actual_answer,
                retrieved_chunks=list(retrieved_chunks),
                expected_answer=expected_answer,
                expected_behavior=expected_behavior,
                spec=spec_obj,
            )
        except Exception as exc:  # heuristic fallback keeps Demo alive
            result = heuristic_judge(
                query=query,
                actual_answer=actual_answer,
                retrieved_chunks=list(retrieved_chunks),
                expected_answer=expected_answer,
                expected_behavior=expected_behavior,
            )
            result["reason"] = f"llm failed, heuristic used: {exc}"
            return result
    return heuristic_judge(
        query=query,
        actual_answer=actual_answer,
        retrieved_chunks=list(retrieved_chunks),
        expected_answer=expected_answer,
        expected_behavior=expected_behavior,
    )
