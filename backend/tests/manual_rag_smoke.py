"""End-to-end smoke suite for a running VaultQ + LM Studio instance."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Case:
    question: str
    should_ground: bool


CASES = (
    Case("VaultQ 为什么不会编造答案？", True),
    Case("如果检索不到可靠资料，系统会怎样处理？", True),
    Case("笔记内容会被上传到外部服务器吗？", True),
    Case("如何从搜索结果回到 Obsidian 原文？", True),
    Case("VaultQ 会修改或删除我的 Markdown 文件吗？", True),
    Case("量子纠缠的贝尔不等式如何推导？", False),
    Case("明朝万历年间的赋税制度有什么变化？", False),
)


def main() -> int:
    failures: list[str] = []
    results: list[dict[str, object]] = []
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=120, trust_env=False) as client:
        stats = client.get("/api/stats").json()
        if not stats["ai"]["chat_ready"] or not stats["ai"]["embedding_ready"]:
            print(json.dumps({"error": "local models are not ready", "ai": stats["ai"]}, ensure_ascii=False))
            return 2
        for round_number in range(1, 3):
            for case in CASES:
                response = client.post("/api/ask", json={"question": case.question, "top_k": 6})
                response.raise_for_status()
                payload = response.json()
                references = re.findall(r"\[(\d+)\]", payload["answer"])
                passed = payload["grounded"] is case.should_ground
                if case.should_ground:
                    passed = passed and payload["mode"] == "lm_studio" and bool(references) and bool(payload["citations"])
                else:
                    passed = passed and not references
                record = {
                    "round": round_number,
                    "question": case.question,
                    "expected_grounded": case.should_ground,
                    "grounded": payload["grounded"],
                    "mode": payload["mode"],
                    "citations": len(payload["citations"]),
                    "references": references,
                    "passed": passed,
                }
                results.append(record)
                print(json.dumps(record, ensure_ascii=True), flush=True)
                if not passed:
                    failures.append(f"round {round_number}: {case.question}")
    summary = {"total": len(results), "passed": len(results) - len(failures), "failed": failures}
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
