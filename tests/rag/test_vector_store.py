import pytest

from rag.embeddings import FakeEmbeddings
from rag.vector_store import (
    InMemoryVectorStore,
    QdrantVectorStore,
    VectorDocument,
    create_embeddings,
    create_vector_store,
)


@pytest.mark.parametrize("text", ["SSO login fails", "", "API 429 rate limit"])
async def test_fake_embeddings_are_deterministic_and_normalized(text):
    embeddings = FakeEmbeddings(dimensions=384)
    first = embeddings.embed_text(text)
    second = await embeddings.embed_query(text)

    assert len(first) == 384
    assert second == first
    assert first == embeddings.embed_sync(text)
    norm = sum(value * value for value in first) ** 0.5
    assert norm == 0 or abs(norm - 1.0) < 1e-6


async def test_fake_embeddings_preserve_document_order():
    embeddings = create_embeddings(
        provider="fake",
        model="fake-hash",
        dimensions=384,
    )
    vectors = await embeddings.embed_documents(
        ["billing refund", "login MFA", "billing refund"]
    )

    assert vectors[0] == vectors[2]
    assert vectors[0] != vectors[1]


async def test_in_memory_store_add_search_filter_delete_and_count():
    store = InMemoryVectorStore(dimensions=384)
    added = await store.add_documents(
        [
            VectorDocument(
                id="mfa",
                text="MFA recovery unlock account",
                metadata={"category": "login_issue"},
            ),
            VectorDocument(
                id="refund",
                text="Refund billing seat adjustment",
                metadata={"category": "billing"},
            ),
        ]
    )

    assert added == 2
    assert await store.count() == 2

    login_results = await store.search(
        "MFA login",
        top_k=5,
        filters={"category": "login_issue"},
    )
    assert login_results
    assert login_results[0].id == "mfa"

    assert await store.delete(["mfa"]) == 1
    assert await store.count() == 1
    remaining = await store.search("billing", top_k=5)
    assert len(remaining) == 1
    assert remaining[0].id == "refund"


async def test_explicit_vectors_and_delete_by_article():
    store = InMemoryVectorStore(dimensions=3)
    await store.add_documents(
        [
            VectorDocument(
                id="chunk-1",
                text="first",
                metadata={"article_id": "article-a"},
                vector=[1.0, 0.0, 0.0],
            ),
            VectorDocument(
                id="chunk-2",
                text="second",
                metadata={"article_id": "article-b"},
                vector=[0.0, 1.0, 0.0],
            ),
        ]
    )

    results = await store.search([1.0, 0.0, 0.0], top_k=1)
    assert results[0].id == "chunk-1"
    assert await store.delete_by_article("article-a") == 1
    assert await store.count() == 1


def test_vector_store_factory():
    embeddings = FakeEmbeddings(dimensions=384)
    store = create_vector_store(
        vector_store="memory",
        embeddings=embeddings,
    )
    assert isinstance(store, InMemoryVectorStore)

    with pytest.raises(ValueError, match="Unsupported vector store"):
        create_vector_store(vector_store="unknown", embeddings=embeddings)

    qdrant = create_vector_store(
        vector_store="qdrant",
        embeddings=embeddings,
        qdrant_url="http://127.0.0.1:6333",
    )
    assert isinstance(qdrant, QdrantVectorStore)
