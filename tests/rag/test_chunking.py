from pathlib import Path

import pytest

from backend.app.schemas.common import Category
from rag.chunking import Article, chunk_article, load_article_files

KNOWLEDGE_DIR = Path(__file__).parents[2] / "sample_data" / "knowledge_base"


def test_knowledge_directory_has_exactly_fifteen_articles():
    articles = load_article_files(KNOWLEDGE_DIR)
    assert len(articles) == 15
    assert len({article.slug for article in articles}) == 15


def test_articles_have_required_front_matter_and_categories():
    articles = load_article_files(KNOWLEDGE_DIR)
    for article in articles:
        assert article.title
        assert article.summary
        assert article.tags
        assert article.category.value
        assert article.content


def test_chunking_splits_headings_and_prefixes_provenance():
    articles = load_article_files(KNOWLEDGE_DIR)
    chunks = chunk_article(articles[0])
    assert chunks
    for chunk in chunks:
        assert chunk.text.startswith(f"{chunk.title} - {chunk.heading}")
        assert chunk.source.startswith("kb://")
        assert chunk.article_id == articles[0].id
        assert chunk.category == articles[0].category


def test_chunk_windows_overlap_and_remain_bounded():
    article = Article(
        id="window-test",
        slug="window-test",
        title="Window Test",
        category=Category.OTHER,
        tags=("test",),
        summary="Window test article",
        content="# Details\n\n" + ("x" * 220),
    )
    chunks = chunk_article(article, window_size=120, overlap=20)
    first = chunks[0].text.rsplit("\n\n", 1)[-1]
    second = chunks[1].text.rsplit("\n\n", 1)[-1]
    assert len(first) == 120
    assert len(second) == 120
    assert first[-20:] == second[:20]


def test_chunking_rejects_invalid_window_parameters():
    article = load_article_files(KNOWLEDGE_DIR)[0]
    with pytest.raises(ValueError, match="window_size"):
        chunk_article(article, window_size=0)
    with pytest.raises(ValueError, match="overlap"):
        chunk_article(article, window_size=100, overlap=100)