from __future__ import annotations

import re

from .lmstudio import LMStudioClient, LMStudioError
from .models import AskResponse, Citation, ReviewQuestion, ReviewResponse
from .repository import KnowledgeRepository


SENTENCE_RE = re.compile(r"(?<=[。！？.!?])\s+|\n+")


class KnowledgeService:
    def __init__(self, repository: KnowledgeRepository, lm_studio: LMStudioClient | None = None):
        self.repository = repository
        self.lm_studio = lm_studio

    def index_embeddings(self) -> int:
        if not self.lm_studio:
            return 0
        model = self.lm_studio.settings.lm_studio_embedding_model
        total = 0
        try:
            if not self.lm_studio.status()["embedding_ready"]:
                return 0
            while batch := self.repository.chunks_missing_embeddings(
                model, self.lm_studio.settings.embedding_batch_size
            ):
                vectors = self.lm_studio.embed([text for _, text in batch])
                self.repository.save_embeddings(model, [
                    (chunk_id, vector) for (chunk_id, _), vector in zip(batch, vectors)
                ])
                total += len(batch)
        except LMStudioError:
            return total
        return total

    def search(self, query: str, limit: int = 10, directory: str = "", tag: str = "") -> list[Citation]:
        keyword = self.repository.search(query, limit=limit, directory=directory, tag=tag)
        if not self.lm_studio:
            return keyword
        try:
            query_vector = self.lm_studio.embed([query])[0]
            semantic = self.repository.semantic_search(
                query_vector,
                self.lm_studio.settings.lm_studio_embedding_model,
                limit=limit,
                directory=directory,
                tag=tag,
            )
        except (LMStudioError, IndexError):
            return keyword

        merged: dict[int, tuple[Citation, float]] = {}
        for index, citation in enumerate(keyword):
            merged[citation.chunk_id] = (citation, 0.55 / (index + 1))
        for index, citation in enumerate(semantic):
            previous = merged.get(citation.chunk_id)
            score = 0.45 / (index + 1)
            merged[citation.chunk_id] = (citation if previous is None else previous[0], score + (previous[1] if previous else 0))
        ordered = sorted(merged.values(), key=lambda item: item[1], reverse=True)[:limit]
        results = []
        for citation, score in ordered:
            citation.score = round(score, 4)
            results.append(citation)
        return results

    def model_status(self) -> dict[str, object]:
        if not self.lm_studio:
            return {
                "connected": False, "chat_ready": False, "embedding_ready": False,
                "chat_model": "", "embedding_model": "", "embedded_chunks": 0,
                "message": "本地模型未配置",
            }
        status = self.lm_studio.status()
        status["embedded_chunks"] = self.repository.embedding_count(self.lm_studio.settings.lm_studio_embedding_model)
        return status

    def answer(self, question: str, top_k: int) -> AskResponse:
        keyword_citations = self.repository.search(question, limit=top_k)
        citations = self.search(question, limit=top_k)
        if not citations:
            return AskResponse(
                answer="库里没有足够信息来回答这个问题。你可以换一组更贴近笔记原文的关键词，或先补充相关资料。",
                grounded=False, confidence="无依据", mode="refusal", citations=[],
            )
        if self.lm_studio:
            sources = "\n\n".join(
                f"[{index}] 笔记：{citation.note_name}\n位置：{citation.heading}，第 {citation.line_start}-{citation.line_end} 行\n原文：{citation.excerpt}"
                for index, citation in enumerate(citations, start=1)
            )
            try:
                generated = self.lm_studio.complete_grounded_answer(question, sources)
                references = {int(value) for value in re.findall(r"\[(\d+)\]", generated)}
                valid = references and all(1 <= value <= len(citations) for value in references)
                normalized = generated.strip().rstrip("。！!")
                if normalized in {"库里没有足够信息", "库里没有足够信息来回答这个问题"}:
                    # A small local model can occasionally overlook a literal keyword hit.
                    # Reconsider only when FTS found direct evidence; semantic-only results
                    # never bypass the normal refusal path.
                    if keyword_citations:
                        generated = self.lm_studio.complete_grounded_answer(
                            question, sources, reconsider=True
                        )
                        references = {int(value) for value in re.findall(r"\[(\d+)\]", generated)}
                        valid = references and all(1 <= value <= len(citations) for value in references)
                        normalized = generated.strip().rstrip("。！!")
                        if valid and normalized not in {
                            "库里没有足够信息",
                            "库里没有足够信息来回答这个问题",
                        }:
                            confidence = "较高" if len(references) >= 2 else "有限"
                            return AskResponse(
                                answer=generated,
                                grounded=True,
                                confidence=confidence,
                                mode="lm_studio",
                                citations=citations,
                            )
                    return AskResponse(answer="库里没有足够信息来回答这个问题。", grounded=False, confidence="依据不足", mode="lm_studio", citations=citations)
                if valid:
                    confidence = "较高" if len(references) >= 2 else "有限"
                    return AskResponse(answer=generated, grounded=True, confidence=confidence, mode="lm_studio", citations=citations)
            except LMStudioError:
                pass
        return self._extractive_answer(citations)

    def _extractive_answer(self, citations: list[Citation]) -> AskResponse:
        evidence: list[str] = []
        for citation in citations[:3]:
            sentences = [item.strip(" -\t") for item in SENTENCE_RE.split(citation.excerpt) if len(item.strip()) >= 12]
            if sentences:
                evidence.append(sentences[0])
        if not evidence:
            return AskResponse(answer="库里找到了相关条目，但原文不足以形成可靠回答。", grounded=False, confidence="依据不足", mode="extractive", citations=citations)
        numbered = "\n".join(f"{index + 1}. {sentence}" for index, sentence in enumerate(evidence))
        answer = f"根据库内现有笔记，可以归纳为：\n\n{numbered}\n\n以上结论仅依据下方引文；笔记没有覆盖的部分不作推断。"
        confidence = "较高" if len(citations) >= 3 else "有限"
        return AskResponse(answer=answer, grounded=True, confidence=confidence, mode="extractive", citations=citations)

    def review(self, topic: str, count: int) -> ReviewResponse:
        citations = self.search(topic, limit=count) if topic.strip() else self.repository.recent_chunks(limit=count)
        questions: list[ReviewQuestion] = []
        for citation in citations:
            subject = citation.heading.split(" › ")[-1]
            hint = citation.excerpt.replace("\n", " ")[:120]
            questions.append(ReviewQuestion(
                question=f"不看原文，你能解释“{subject}”的核心要点吗？",
                answer_hint=hint + ("…" if len(citation.excerpt) > 120 else ""), citation=citation,
            ))
        learning_path = []
        seen: set[str] = set()
        for citation in citations:
            label = citation.heading.split(" › ")[-1]
            if label not in seen:
                learning_path.append(label)
                seen.add(label)
        gaps: list[str] = []
        if not citations:
            gaps.append(f"“{topic or '当前知识库'}”没有可用于复习的材料。")
        elif len(citations) < 3:
            gaps.append("相关材料少于 3 个片段，主题覆盖可能不完整。")
        if citations and len({c.note_name for c in citations}) == 1:
            gaps.append("证据只来自一篇笔记，建议补充第二来源或实践记录。")
        return ReviewResponse(topic=topic or "最近笔记", questions=questions, learning_path=learning_path, gaps=gaps)

