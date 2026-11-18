from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from backend.app.schemas.common import Category
from rag.chunking import Article, Chunk, chunk_article, load_article_files
from rag.retriever import Evidence, HybridRetriever
from rag.vector_store import VectorDocument, VectorStoreService


@dataclass(frozen=True)
class IngestSummary:
    articles_indexed: int
    chunks_indexed: int


def build_vector_documents(articles: Sequence[Article]) -> list[VectorDocument]:
    documents: list[VectorDocument] = []
    for article in articles:
        for chunk in chunk_article(article):
            documents.append(_chunk_to_document(chunk))
    return documents


def _chunk_to_document(chunk: Chunk) -> VectorDocument:
    point_id = str(uuid5(NAMESPACE_URL, f"clouddesk-knowledge:{chunk.id}"))
    return VectorDocument(
        id=point_id,
        text=chunk.text,
        metadata={
            "article_id": chunk.article_id,
            "category": chunk.category.value,
            "heading": chunk.heading,
            "slug": chunk.slug,
            "source": chunk.source,
            "tags": list(chunk.tags),
            "title": chunk.title,
            "summary": chunk.summary,
        },
    )


class KnowledgeIndex:
    def __init__(
        self,
        articles_dir: str | Path,
        vector_store: VectorStoreService,
    ) -> None:
        self.articles_dir = Path(articles_dir)
        self.vector_store = vector_store
        self.articles: tuple[Article, ...] = ()
        self.documents: tuple[VectorDocument, ...] = ()
        self.retriever: HybridRetriever | None = None

    def _load_corpus(self) -> tuple[list[Article], list[VectorDocument]]:
        articles = load_article_files(self.articles_dir)
        if not articles:
            raise ValueError(
                f"No knowledge articles found in {self.articles_dir}"
            )
        return articles, build_vector_documents(articles)

    async def initialize(self) -> IngestSummary:
        articles, documents = self._load_corpus()
        if await self.vector_store.count() == 0:
            indexed = await self.vector_store.add_documents(documents)
            if indexed != len(documents):
                raise RuntimeError(
                    f"Vector store indexed {indexed} of {len(documents)} chunks"
                )
        self._replace_corpus(articles, documents)
        return IngestSummary(len(articles), len(documents))

    async def reindex(self) -> IngestSummary:
        articles, documents = self._load_corpus()
        await self.vector_store.clear()
        self.articles = ()
        self.documents = ()
        self.retriever = None
        indexed = await self.vector_store.add_documents(documents)
        if indexed != len(documents):
            raise RuntimeError(
                f"Vector store indexed {indexed} of {len(documents)} chunks"
            )
        self._replace_corpus(articles, documents)
        return IngestSummary(len(articles), indexed)

    def _replace_corpus(
        self,
        articles: Sequence[Article],
        documents: Sequence[VectorDocument],
    ) -> None:
        self.articles = tuple(articles)
        self.documents = tuple(documents)
        self.retriever = HybridRetriever(
            self.vector_store,
            self.documents,
        )

    def list_articles(self) -> tuple[Article, ...]:
        return self.articles

    def get_article(self, article_id: str) -> Article | None:
        return next(
            (article for article in self.articles if article.id == article_id),
            None,
        )

    async def search(
        self,
        query: str,
        *,
        category: Category | None,
        mode: str,
        top_k: int,
    ) -> list[Evidence]:
        if self.retriever is None:
            raise RuntimeError("Knowledge index has not been initialized")
        return await self.retriever.retrieve(
            query,
            category=category,
            mode=mode,
            top_k=top_k,
        )
