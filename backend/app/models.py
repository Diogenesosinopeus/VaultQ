from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: int
    note_name: str
    path: str
    heading: str
    line_start: int
    line_end: int
    excerpt: str
    tags: list[str] = Field(default_factory=list)
    score: float = 0
    obsidian_url: str


class SearchResponse(BaseModel):
    query: str
    total: int
    items: list[Citation]


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=12)


class AskResponse(BaseModel):
    answer: str
    grounded: bool
    confidence: str
    mode: str = "extractive"
    citations: list[Citation]


class ReviewRequest(BaseModel):
    topic: str = Field(default="", max_length=200)
    count: int = Field(default=5, ge=1, le=12)


class ReviewQuestion(BaseModel):
    question: str
    answer_hint: str
    citation: Citation


class ReviewResponse(BaseModel):
    topic: str
    questions: list[ReviewQuestion]
    learning_path: list[str]
    gaps: list[str]


class IndexResponse(BaseModel):
    indexed_files: int
    indexed_chunks: int
    skipped_files: int
    removed_files: int
    embedded_chunks: int = 0
    embedding_model: str | None = None


class AIStatus(BaseModel):
    connected: bool
    chat_ready: bool
    embedding_ready: bool
    chat_model: str
    embedding_model: str
    embedded_chunks: int = 0
    message: str


class StatsResponse(BaseModel):
    documents: int
    chunks: int
    tags: list[dict[str, int | str]]
    directories: list[dict[str, int | str]]
    last_indexed_at: str | None
    root: str
    read_only: bool = True
    ai: AIStatus

