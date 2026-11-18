import json
from pathlib import Path

import pytest

from backend.app.cli.ingest_knowledge import main as ingest_command
from backend.app.core.config import Settings
from rag.chunking import load_article_files
from rag.embeddings import FakeEmbeddings
from rag.ingest import KnowledgeIndex, build_vector_documents
from rag.vector_store import InMemoryVectorStore, VectorDocument

KNOWLEDGE_DIR = Path(__file__).parents[2] / "sample_data" / "knowledge_base"


async def test_ingest_indexes_articles_and_searches_cited_chunks():
    store = InMemoryVectorStore(embeddings=FakeEmbeddings())
    index = KnowledgeIndex(KNOWLEDGE_DIR, store)

    summary = await index.initialize()
    results = await index.search(
        "API 429 retry backoff",
        category=None,
        mode="hybrid",
        top_k=3,
    )

    assert summary.articles_indexed == 15
    assert summary.chunks_indexed == await store.count()
    assert results
    assert results[0].article_id == "api-rate-limits"
    assert results[0].source.startswith("kb://api-rate-limits#")


async def test_reindex_removes_stale_vector_documents():
    store = InMemoryVectorStore(embeddings=FakeEmbeddings())
    await store.add_documents(
        [
            VectorDocument(
                id="stale-document",
                text="obsolete support article",
                metadata={"article_id": "obsolete"},
            )
        ]
    )
    index = KnowledgeIndex(KNOWLEDGE_DIR, store)

    summary = await index.reindex()

    expected_chunks = len(
        build_vector_documents(load_article_files(KNOWLEDGE_DIR))
    )
    assert summary.articles_indexed == 15
    assert summary.chunks_indexed == expected_chunks
    assert await store.count() == expected_chunks
    assert index.get_article("obsolete") is None


async def test_failed_reindex_does_not_leave_a_success_shaped_empty_search():
    store = InMemoryVectorStore(embeddings=FakeEmbeddings())
    index = KnowledgeIndex(KNOWLEDGE_DIR, store)
    await index.initialize()

    async def fail_add(documents):
        raise RuntimeError("index write failed")

    store.add_documents = fail_add
    with pytest.raises(RuntimeError, match="index write failed"):
        await index.reindex()

    assert index.list_articles() == ()
    with pytest.raises(
        RuntimeError,
        match="Knowledge index has not been initialized",
    ):
        await index.search(
            "MFA recovery",
            category=None,
            mode="hybrid",
            top_k=1,
        )


async def test_initialize_reuses_existing_vector_index_without_stale_results():
    articles = load_article_files(KNOWLEDGE_DIR)
    store = InMemoryVectorStore(embeddings=FakeEmbeddings())
    await store.add_documents(
        [
            VectorDocument(
                id="stale-document",
                text="obsolete article",
                metadata={"article_id": "obsolete", "title": "Obsolete"},
            )
        ]
    )
    index = KnowledgeIndex(KNOWLEDGE_DIR, store)

    await index.initialize()
    results = await index.search(
        "obsolete article",
        category=None,
        mode="semantic",
        top_k=5,
    )

    assert index.list_articles() == tuple(articles)
    assert all(result.article_id != "obsolete" for result in results)


def test_ingest_command_rebuilds_index_and_reports_counts(monkeypatch, capsys):
    settings = Settings(
        _env_file=None,
        vector_store="memory",
        sample_data_dir=str(KNOWLEDGE_DIR.parent),
    )
    monkeypatch.setattr(
        "backend.app.cli.ingest_knowledge.get_settings",
        lambda: settings,
    )

    assert ingest_command([]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["articles_indexed"] == 15
    assert output["chunks_indexed"] == 45


def test_ingest_command_reports_empty_article_directory(
    monkeypatch,
    capsys,
    tmp_path,
):
    settings = Settings(_env_file=None, vector_store="memory")
    monkeypatch.setattr(
        "backend.app.cli.ingest_knowledge.get_settings",
        lambda: settings,
    )

    assert ingest_command(["--articles-dir", str(tmp_path)]) == 1
    assert "No knowledge articles found" in capsys.readouterr().err
