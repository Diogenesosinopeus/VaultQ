from pathlib import Path

from backend.app.config import Settings
from backend.app.parser import parse_markdown
from backend.app.repository import KnowledgeRepository
from backend.app.service import KnowledgeService


def test_parser_tracks_heading_lines_and_tags(tmp_path: Path):
    note = tmp_path / "demo.md"
    note.write_text("---\ntags: [FastAPI, 安全]\n---\n# JWT 登录\n\n统一错误信息可以避免用户枚举。 #认证\n", encoding="utf-8")
    parsed = parse_markdown(note)
    assert parsed.title == "JWT 登录"
    assert parsed.tags == ["FastAPI", "安全", "认证"]
    assert parsed.chunks[0].heading == "JWT 登录"
    assert parsed.chunks[0].line_start == 6


def test_search_and_refusal(tmp_path: Path):
    notes = tmp_path / "笔记"
    notes.mkdir()
    (notes / "jwt.md").write_text("# JWT 安全\n\n登录失败时返回统一提示，避免攻击者根据响应判断账号是否存在。", encoding="utf-8")
    repository = KnowledgeRepository(Settings(root=tmp_path, vault_name="test"))
    repository.rebuild()
    found = repository.search("登录 账号")
    assert found and found[0].note_name == "JWT 安全"
    answer = KnowledgeService(repository).answer("量子计算是什么", 5)
    assert answer.grounded is False
    assert "没有足够信息" in answer.answer


class FakeLMStudio:
    def __init__(self, settings: Settings):
        self.settings = settings

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if any(term in text for term in ("账号", "枚举", "隐藏")) else [0.0, 1.0] for text in texts]

    def complete_grounded_answer(self, question: str, sources: str) -> str:
        assert question
        assert "[1]" in sources
        return "登录失败时应使用统一提示，避免泄露账号是否存在。[1]"

    def status(self) -> dict[str, object]:
        return {
            "connected": True,
            "chat_ready": True,
            "embedding_ready": True,
            "chat_model": self.settings.lm_studio_chat_model,
            "embedding_model": self.settings.lm_studio_embedding_model,
            "message": "ready",
        }


def test_local_rag_embeddings_and_citation_validation(tmp_path: Path):
    notes = tmp_path / "笔记"
    notes.mkdir()
    (notes / "jwt.md").write_text("# JWT 安全\n\n登录失败时返回统一提示，避免攻击者判断账号是否存在。", encoding="utf-8")
    settings = Settings(root=tmp_path, vault_name="test")
    repository = KnowledgeRepository(settings)
    repository.rebuild()
    service = KnowledgeService(repository, FakeLMStudio(settings))  # type: ignore[arg-type]

    assert service.index_embeddings() == 1
    results = service.search("如何隐藏账号存在性")
    assert results and results[0].note_name == "JWT 安全"
    answer = service.answer("怎样避免账号枚举？", 5)
    assert answer.grounded is True
    assert answer.mode == "lm_studio"
    assert "[1]" in answer.answer
