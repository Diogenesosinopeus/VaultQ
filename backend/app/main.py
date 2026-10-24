from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .lmstudio import LMStudioClient
from .models import AskRequest, AskResponse, IndexResponse, ReviewRequest, ReviewResponse, SearchResponse, StatsResponse
from .repository import KnowledgeRepository
from .service import KnowledgeService


settings = get_settings()
repository = KnowledgeRepository(settings)
lm_studio = LMStudioClient(settings)
service = KnowledgeService(repository, lm_studio)


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.rebuild()
    service.index_embeddings()
    yield


app = FastAPI(title="VaultQ API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    model_status = service.model_status()
    return {"status": "ok", "read_only": True, "lm_studio": bool(model_status["connected"])}


@app.post("/api/index", response_model=IndexResponse)
def rebuild_index() -> dict:
    result = repository.rebuild()
    result["embedded_chunks"] = service.index_embeddings()
    result["embedding_model"] = settings.lm_studio_embedding_model
    return result


@app.get("/api/search", response_model=SearchResponse)
def search(
    q: str = Query(min_length=1, max_length=300),
    limit: int = Query(default=10, ge=1, le=30),
    directory: str = Query(default=""),
    tag: str = Query(default=""),
) -> SearchResponse:
    items = service.search(q, limit=limit, directory=directory, tag=tag)
    return SearchResponse(query=q, total=len(items), items=items)


@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    return service.answer(payload.question, payload.top_k)


@app.post("/api/review", response_model=ReviewResponse)
def review(payload: ReviewRequest) -> ReviewResponse:
    return service.review(payload.topic, payload.count)


@app.get("/api/stats", response_model=StatsResponse)
def stats() -> dict:
    result = repository.stats()
    result["ai"] = service.model_status()
    return result

