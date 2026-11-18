import pytest

from backend.app.schemas.common import Category
from rag.retriever import Evidence, HybridRetriever, RetrievalCache
from rag.vector_store import InMemoryVectorStore, VectorDocument


class StaticEmbeddings:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    async def embed_query(self, text: str) -> list[float]:
        if "billing" in text.casefold():
            return [0.0, 1.0, 0.0]
        return [1.0, 0.0, 0.0]


def document(
    document_id: str,
    text: str,
    article_id: str,
    category: str,
    vector: list[float],
    *,
    title: str,
    source: str,
) -> VectorDocument:
    return VectorDocument(
        id=document_id,
        text=text,
        vector=vector,
        metadata={
            "article_id": article_id,
            "category": category,
            "title": title,
            "source": source,
            "slug": article_id,
        },
    )


async def create_retriever() -> HybridRetriever:
    documents = [
        document(
            "mfa-1",
            "MFA recovery lets a user unlock an account after verification.",
            "mfa-recovery",
            "login_issue",
            [1.0, 0.0, 0.0],
            title="MFA recovery",
            source="kb://mfa-recovery#overview",
        ),
        document(
            "mfa-2",
            "Reset MFA after identity verification and restore login access.",
            "mfa-recovery",
            "login_issue",
            [0.8, 0.2, 0.0],
            title="MFA recovery",
            source="kb://mfa-recovery#reset",
        ),
        document(
            "billing-1",
            "Review billing invoice refund requests and seat adjustments.",
            "billing-seat-adjustments",
            "billing",
            [0.0, 1.0, 0.0],
            title="Billing and seat adjustments",
            source="kb://billing-seat-adjustments#overview",
        ),
        document(
            "security-1",
            "Secure a suspicious login and protect the account.",
            "suspicious-login",
            "security",
            [0.0, 0.0, 1.0],
            title="Suspicious login",
            source="kb://suspicious-login#overview",
        ),
        document(
            "workspace-1",
            "Invite collaborators and configure shared workspace permissions.",
            "workspace-sharing",
            "workspace_permissions",
            [0.0, 0.0, 1.0],
            title="Workspace sharing",
            source="kb://workspace-sharing#overview",
        ),
        document(
            "api-1",
            "API authentication uses scoped access tokens.",
            "api-authentication",
            "api_failure",
            [0.0, 0.0, 1.0],
            title="API authentication",
            source="kb://api-authentication#overview",
        ),
    ]
    store = InMemoryVectorStore(embeddings=StaticEmbeddings())
    await store.add_documents(documents)
    return HybridRetriever(store, documents, candidate_k=6)


async def test_retrieval_modes_select_semantic_or_keyword_results():
    retriever = await create_retriever()

    semantic = await retriever.retrieve("login help", mode="semantic")
    keyword = await retriever.retrieve("invoice refund", mode="keyword")

    assert semantic[0].article_id == "mfa-recovery"
    assert keyword[0].article_id == "billing-seat-adjustments"


async def test_hybrid_fuses_results_and_deduplicates_articles():
    retriever = await create_retriever()

    results = await retriever.retrieve(
        "MFA recovery login",
        top_k=5,
    )

    assert len(results) == 2
    assert len({result.article_id for result in results}) == len(results)
    assert results[0].id == "mfa-1"
    assert results[0].article_id == "mfa-recovery"
    assert results[0].source == "kb://mfa-recovery#overview"
    assert results[0].url == "/knowledge/mfa-recovery"
    assert results[0].score == pytest.approx(2 / 61)


async def test_category_filter_and_top_k_are_respected():
    retriever = await create_retriever()

    results = await retriever.retrieve(
        "invoice refund",
        category=Category.BILLING,
        mode="keyword",
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].article_id == "billing-seat-adjustments"


async def test_cache_normalizes_query_and_reuses_results():
    retriever = await create_retriever()
    initial_count = await retriever.vector_store.count()
    search_calls = 0
    original_search = retriever.vector_store.search

    async def counted_search(*args, **kwargs):
        nonlocal search_calls
        search_calls += 1
        return await original_search(*args, **kwargs)

    retriever.vector_store.search = counted_search

    first = await retriever.retrieve(" MFA   recovery ", mode="semantic")
    second = await retriever.retrieve("mfa recovery", mode="semantic")

    assert first == second
    assert search_calls == 1
    assert initial_count == 6


async def test_optional_reranker_only_accepts_known_evidence_ids():
    async def reverse_candidates(query, candidates):
        return [candidate.id for candidate in reversed(candidates)]

    retriever = await create_retriever()
    retriever.reranker = reverse_candidates
    results = await retriever.retrieve("account", top_k=2)

    assert len(results) == 2
    assert results[0].article_id != results[1].article_id

    async def invalid_candidate(query, candidates):
        return ["invented-evidence"]

    retriever.reranker = invalid_candidate
    with pytest.raises(ValueError, match="unknown evidence ID"):
        await retriever.retrieve("account", top_k=2)


async def test_invalid_queries_and_modes_are_rejected():
    retriever = await create_retriever()

    with pytest.raises(ValueError, match="query"):
        await retriever.retrieve("  ")
    with pytest.raises(ValueError, match="Unsupported retrieval mode"):
        await retriever.retrieve("account", mode="unknown")
    with pytest.raises(ValueError, match="top_k"):
        await retriever.retrieve("account", top_k=0)


async def test_title_overlap_heuristic_breaks_ties():
    documents = [
        document(
            "a-unrelated",
            "Account support procedure",
            "unrelated",
            "account",
            [1.0, 0.0, 0.0],
            title="General support",
            source="kb://general-support#overview",
        ),
        document(
            "z-account",
            "Account support procedure",
            "account-access",
            "account",
            [1.0, 0.0, 0.0],
            title="Account access",
            source="kb://account-access#overview",
        ),
    ]
    store = InMemoryVectorStore(embeddings=StaticEmbeddings())
    await store.add_documents(documents)
    retriever = HybridRetriever(store, documents)

    results = await retriever.retrieve("account", top_k=2)

    assert results[0].article_id == "account-access"


def test_retrieval_cache_validates_limits():
    with pytest.raises(ValueError, match="TTL"):
        RetrievalCache(ttl_seconds=0)
    with pytest.raises(ValueError, match="max_entries"):
        RetrievalCache(max_entries=0)


def test_retrieval_cache_expires_entries(monkeypatch):
    now = 100.0
    monkeypatch.setattr("rag.retriever.time.monotonic", lambda: now)
    cache = RetrievalCache(ttl_seconds=2)
    key = ("semantic", "", 1, "account")
    evidence = Evidence(
        id="account",
        title="Account",
        source="kb://account#overview",
        snippet="Account help",
        score=1.0,
        url="/knowledge/account",
        article_id="account",
    )
    cache.set(key, [evidence])

    assert cache.get(key) == [evidence]
    now += 2
    assert cache.get(key) is None
