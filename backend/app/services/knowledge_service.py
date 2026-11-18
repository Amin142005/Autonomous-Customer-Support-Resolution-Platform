from __future__ import annotations

from pathlib import Path

from backend.app.core.config import Settings
from backend.app.schemas.common import Category
from rag.chunking import Article
from rag.embeddings import create_embeddings
from rag.ingest import IngestSummary, KnowledgeIndex
from rag.retriever import Evidence
from rag.vector_store import create_vector_store


class KnowledgeService:
    def __init__(self, index: KnowledgeIndex) -> None:
        self.index = index

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        articles_dir: str | Path | None = None,
    ) -> KnowledgeService:
        embeddings = create_embeddings(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
        vector_store = create_vector_store(
            vector_store=settings.vector_store,
            embeddings=embeddings,
            qdrant_url=settings.qdrant_url,
            qdrant_api_key=settings.qdrant_api_key.get_secret_value(),
            qdrant_collection=settings.qdrant_collection,
        )
        root = (
            Path(articles_dir)
            if articles_dir is not None
            else Path(settings.sample_data_dir) / "knowledge_base"
        )
        return cls(KnowledgeIndex(root, vector_store))

    async def initialize(self) -> IngestSummary:
        return await self.index.initialize()

    async def reindex(self) -> IngestSummary:
        return await self.index.reindex()

    def list_articles(self) -> tuple[Article, ...]:
        return self.index.list_articles()

    def get_article(self, article_id: str) -> Article | None:
        return self.index.get_article(article_id)

    async def search(
        self,
        query: str,
        *,
        category: Category | None,
        mode: str,
        top_k: int,
    ) -> list[Evidence]:
        return await self.index.search(
            query,
            category=category,
            mode=mode,
            top_k=top_k,
        )
