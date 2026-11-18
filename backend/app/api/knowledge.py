from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.schemas.common import Role
from backend.app.schemas.knowledge import (
    KnowledgeArticleDetail,
    KnowledgeArticleListResponse,
    KnowledgeArticleSummary,
    KnowledgeEvidence,
    KnowledgeReindexResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from backend.app.services.knowledge_service import KnowledgeService
from rag.chunking import Article

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

ViewerUser = Annotated[AuthenticatedUser, Depends(require_role(Role.VIEWER))]
AdminUser = Annotated[AuthenticatedUser, Depends(require_role(Role.ADMIN))]


def _service(request: Request) -> KnowledgeService:
    service = getattr(request.app.state, "knowledge_service", None)
    if not isinstance(service, KnowledgeService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge service is not initialized",
        )
    return service


def _summary(article: Article) -> KnowledgeArticleSummary:
    return KnowledgeArticleSummary(
        id=article.id,
        slug=article.slug,
        title=article.title,
        category=article.category,
        tags=list(article.tags),
        summary=article.summary,
    )


@router.get("", response_model=KnowledgeArticleListResponse)
async def list_knowledge_articles(
    _current_user: ViewerUser,
    request: Request,
) -> KnowledgeArticleListResponse:
    return KnowledgeArticleListResponse(
        items=[_summary(article) for article in _service(request).list_articles()]
    )


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    body: KnowledgeSearchRequest,
    _current_user: ViewerUser,
    request: Request,
) -> KnowledgeSearchResponse:
    evidence = await _service(request).search(
        body.query,
        category=body.category,
        mode=body.mode,
        top_k=body.top_k,
    )
    return KnowledgeSearchResponse(
        items=[KnowledgeEvidence(**item.as_dict()) for item in evidence]
    )


@router.post("/reindex", response_model=KnowledgeReindexResponse)
async def reindex_knowledge(
    _current_user: AdminUser,
    request: Request,
) -> KnowledgeReindexResponse:
    try:
        summary = await _service(request).reindex()
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Knowledge reindex failed: {exc}",
        ) from exc
    return KnowledgeReindexResponse(
        articles_indexed=summary.articles_indexed,
        chunks_indexed=summary.chunks_indexed,
    )


@router.get("/{article_id}", response_model=KnowledgeArticleDetail)
async def get_knowledge_article(
    article_id: str,
    _current_user: ViewerUser,
    request: Request,
) -> KnowledgeArticleDetail:
    article = _service(request).get_article(article_id)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge article not found",
        )
    return KnowledgeArticleDetail(
        **_summary(article).model_dump(),
        content=article.content,
    )
