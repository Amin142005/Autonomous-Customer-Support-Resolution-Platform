from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.common import Category


class KnowledgeArticleSummary(BaseModel):
    id: str
    slug: str
    title: str
    category: Category
    tags: list[str]
    summary: str


class KnowledgeArticleDetail(KnowledgeArticleSummary):
    content: str


class KnowledgeArticleListResponse(BaseModel):
    items: list[KnowledgeArticleSummary] = Field(default_factory=list)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    category: Category | None = None
    mode: Literal["hybrid", "semantic", "keyword"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be empty")
        return normalized


class KnowledgeEvidence(BaseModel):
    id: str
    title: str
    source: str
    snippet: str
    score: float
    url: str
    article_id: str


class KnowledgeSearchResponse(BaseModel):
    items: list[KnowledgeEvidence] = Field(default_factory=list)


class KnowledgeReindexResponse(BaseModel):
    articles_indexed: int
    chunks_indexed: int
