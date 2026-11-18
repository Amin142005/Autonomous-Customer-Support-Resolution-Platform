from __future__ import annotations

import re
import time
from collections import OrderedDict, defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from rank_bm25 import BM25Okapi

from backend.app.schemas.common import Category
from rag.vector_store import VectorDocument, VectorSearchResult, VectorStoreService

DEFAULT_RRF_K = 60
DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_CANDIDATE_K = 20
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Evidence:
    id: str
    title: str
    source: str
    snippet: str
    score: float
    url: str
    article_id: str

    def as_dict(self) -> dict[str, str | float]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "snippet": self.snippet,
            "score": self.score,
            "url": self.url,
            "article_id": self.article_id,
        }


class Reranker(Protocol):
    async def __call__(
        self,
        query: str,
        candidates: Sequence[Evidence],
    ) -> Sequence[str]:
        """Return candidate evidence IDs in preferred order."""
        ...


class RetrievalCache:
    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        max_entries: int = 512,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("Cache TTL must be positive")
        if max_entries < 1:
            raise ValueError("Cache max_entries must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: OrderedDict[
            tuple[str, str, int, str], tuple[float, tuple[Evidence, ...]]
        ] = OrderedDict()

    def get(
        self,
        key: tuple[str, str, int, str],
    ) -> list[Evidence] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, evidence = entry
        if expires_at <= time.monotonic():
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return list(evidence)

    def set(
        self,
        key: tuple[str, str, int, str],
        evidence: Sequence[Evidence],
    ) -> None:
        self._entries[key] = (
            time.monotonic() + self.ttl_seconds,
            tuple(evidence),
        )
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)


def _tokens(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


def _category_value(category: str | Category | None) -> str:
    if category is None:
        return ""
    return category.value if isinstance(category, Category) else category


def _category_matches(
    metadata: Mapping[str, object],
    category: str | Category | None,
) -> bool:
    if category is None:
        return True
    value = metadata.get("category")
    if isinstance(value, Category):
        value = value.value
    return value == _category_value(category)


class HybridRetriever:
    def __init__(
        self,
        vector_store: VectorStoreService,
        documents: Sequence[VectorDocument],
        *,
        reranker: Reranker | Callable[
            [str, Sequence[Evidence]], Awaitable[Sequence[str]]
        ] | None = None,
        cache: RetrievalCache | None = None,
        rrf_k: int = DEFAULT_RRF_K,
        candidate_k: int = DEFAULT_CANDIDATE_K,
        snippet_max_chars: int = 700,
    ) -> None:
        if rrf_k < 1:
            raise ValueError("rrf_k must be positive")
        if candidate_k < 1:
            raise ValueError("candidate_k must be positive")
        if snippet_max_chars < 1:
            raise ValueError("snippet_max_chars must be positive")
        self.vector_store = vector_store
        self.documents = tuple(documents)
        self.reranker = reranker
        self.cache = cache or RetrievalCache()
        self.rrf_k = rrf_k
        self.candidate_k = candidate_k
        self.snippet_max_chars = snippet_max_chars

    async def retrieve(
        self,
        query: str,
        *,
        category: str | Category | None = None,
        mode: str = "hybrid",
        top_k: int = 5,
    ) -> list[Evidence]:
        normalized_query = " ".join(query.casefold().split())
        normalized_mode = mode.casefold()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if normalized_mode not in {"hybrid", "semantic", "keyword"}:
            raise ValueError(f"Unsupported retrieval mode: {mode}")
        if top_k < 1:
            raise ValueError("top_k must be positive")

        category_key = _category_value(category)
        cache_key = (normalized_mode, category_key, top_k, normalized_query)
        cached = self.cache.get(cache_key)
        if cached is not None and self.reranker is None:
            return cached

        filtered_documents = [
            document
            for document in self.documents
            if _category_matches(document.metadata, category)
        ]
        if not filtered_documents:
            return []

        semantic_results: list[VectorSearchResult] = []
        if normalized_mode in {"hybrid", "semantic"}:
            vector_filters = (
                {"category": category_key} if category is not None else None
            )
            semantic_results = await self.vector_store.search(
                query,
                top_k=self.candidate_k,
                filters=vector_filters,
            )
            semantic_results = [
                result for result in semantic_results if result.score > 0
            ]

        keyword_results = (
            self._keyword_search(
                query,
                filtered_documents,
                self.candidate_k,
            )
            if normalized_mode in {"hybrid", "keyword"}
            else []
        )

        fused_scores: defaultdict[str, float] = defaultdict(float)
        texts: dict[str, str] = {}
        metadata_by_id: dict[str, dict[str, object]] = {}
        self._add_ranked_results(
            semantic_results,
            fused_scores,
            texts,
            metadata_by_id,
        )
        self._add_ranked_results(
            keyword_results,
            fused_scores,
            texts,
            metadata_by_id,
        )

        ranked_ids = sorted(
            fused_scores,
            key=lambda evidence_id: (
                -(
                    fused_scores[evidence_id]
                    + self._heuristic_score(
                        query,
                        metadata_by_id[evidence_id],
                        category,
                    )
                ),
                evidence_id,
            ),
        )
        evidence = self._unique_article_evidence(
            ranked_ids,
            fused_scores,
            texts,
            metadata_by_id,
            top_k,
        )
        if self.reranker is not None and evidence:
            evidence = await self._rerank(query, evidence)
            evidence = self._deduplicate_evidence(evidence, top_k)

        if self.reranker is None:
            self.cache.set(cache_key, evidence)
        return evidence

    def _keyword_search(
        self,
        query: str,
        documents: Sequence[VectorDocument],
        limit: int,
    ) -> list[VectorSearchResult]:
        tokenized_documents = [_tokens(document.text) for document in documents]
        if not any(tokenized_documents):
            return []
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        bm25 = BM25Okapi(tokenized_documents)
        scores = bm25.get_scores(query_tokens)
        ranked_indices = sorted(
            range(len(documents)),
            key=lambda index: (-float(scores[index]), documents[index].id),
        )
        results: list[VectorSearchResult] = []
        for index in ranked_indices:
            score = float(scores[index])
            if not set(query_tokens).intersection(tokenized_documents[index]):
                continue
            document = documents[index]
            results.append(
                VectorSearchResult(
                    id=document.id,
                    text=document.text,
                    score=score,
                    metadata=dict(document.metadata),
                )
            )
            if len(results) >= limit:
                break
        return results

    def _add_ranked_results(
        self,
        results: Sequence[VectorSearchResult],
        scores: defaultdict[str, float],
        texts: dict[str, str],
        metadata_by_id: dict[str, dict[str, object]],
    ) -> None:
        for rank, result in enumerate(results, start=1):
            scores[result.id] += 1.0 / (self.rrf_k + rank)
            texts[result.id] = result.text
            metadata_by_id[result.id] = dict(result.metadata)

    def _heuristic_score(
        self,
        query: str,
        metadata: Mapping[str, object],
        category: str | Category | None,
    ) -> float:
        bonus = 0.0
        if category is not None and _category_matches(metadata, category):
            bonus += 0.05

        query_tokens = set(_tokens(query))
        title_tokens = set(_tokens(str(metadata.get("title", ""))))
        if title_tokens:
            bonus += 0.05 * len(query_tokens & title_tokens) / len(title_tokens)
        return bonus

    def _unique_article_evidence(
        self,
        ranked_ids: Sequence[str],
        fused_scores: Mapping[str, float],
        texts: Mapping[str, str],
        metadata_by_id: Mapping[str, Mapping[str, object]],
        top_k: int,
    ) -> list[Evidence]:
        evidence: list[Evidence] = []
        seen_articles: set[str] = set()
        for evidence_id in ranked_ids:
            metadata = metadata_by_id[evidence_id]
            article_id = str(metadata.get("article_id", ""))
            if not article_id or article_id in seen_articles:
                continue
            seen_articles.add(article_id)
            source = str(metadata.get("source", ""))
            if not source:
                slug = str(metadata.get("slug", article_id))
                heading = str(metadata.get("heading", "overview"))
                source = f"kb://{slug}#{heading}"
            evidence.append(
                Evidence(
                    id=evidence_id,
                    title=str(metadata.get("title", article_id)),
                    source=source,
                    snippet=texts[evidence_id][: self.snippet_max_chars],
                    score=float(fused_scores[evidence_id]),
                    url=f"/knowledge/{article_id}",
                    article_id=article_id,
                )
            )
            if len(evidence) >= top_k:
                break
        return evidence

    async def _rerank(
        self,
        query: str,
        evidence: Sequence[Evidence],
    ) -> list[Evidence]:
        assert self.reranker is not None
        requested_order = await self.reranker(query, evidence)
        evidence_by_id = {item.id: item for item in evidence}
        ordered: list[Evidence] = []
        seen: set[str] = set()
        for evidence_id in requested_order:
            if evidence_id not in evidence_by_id:
                raise ValueError(
                    f"Reranker returned unknown evidence ID: {evidence_id}"
                )
            if evidence_id not in seen:
                ordered.append(evidence_by_id[evidence_id])
                seen.add(evidence_id)
        ordered.extend(item for item in evidence if item.id not in seen)
        return ordered

    @staticmethod
    def _deduplicate_evidence(
        evidence: Sequence[Evidence],
        top_k: int,
    ) -> list[Evidence]:
        unique: list[Evidence] = []
        seen_articles: set[str] = set()
        for item in evidence:
            if item.article_id in seen_articles:
                continue
            unique.append(item)
            seen_articles.add(item.article_id)
            if len(unique) >= top_k:
                break
        return unique


async def retrieve(
    query: str,
    *,
    vector_store: VectorStoreService,
    documents: Sequence[VectorDocument],
    category: str | Category | None = None,
    mode: str = "hybrid",
    top_k: int = 5,
    reranker: Reranker | None = None,
) -> list[Evidence]:
    retriever = HybridRetriever(
        vector_store,
        documents,
        reranker=reranker,
    )
    return await retriever.retrieve(
        query,
        category=category,
        mode=mode,
        top_k=top_k,
    )
