from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from backend.app.schemas.common import Category


@dataclass(frozen=True, slots=True)
class Article:
    id: str
    slug: str
    title: str
    category: Category
    tags: tuple[str, ...]
    summary: str
    content: str


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    article_id: str
    title: str
    heading: str
    slug: str
    category: Category
    tags: tuple[str, ...]
    summary: str
    text: str
    source: str


_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise ValueError("Knowledge article must start with YAML front matter")

    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()

    missing = {"title", "category", "tags", "summary"} - values.keys()
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Knowledge article front matter missing: {names}")
    return values, text[match.end() :]


def _parse_tags(raw: str) -> tuple[str, ...]:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return tuple(
        item.strip().strip("\"'")
        for item in value.split(",")
        if item.strip()
    )


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_article_files(directory: str | Path) -> list[Article]:
    root = Path(directory)
    if not root.exists():
        raise FileNotFoundError(f"Knowledge article directory not found: {root}")

    articles: list[Article] = []
    for path in sorted(root.glob("*.md")):
        front_matter, content = _parse_front_matter(
            path.read_text(encoding="utf-8")
        )
        title = _strip_quotes(front_matter["title"])
        summary = _strip_quotes(front_matter["summary"])
        try:
            category = Category(_strip_quotes(front_matter["category"]))
        except ValueError as exc:
            raise ValueError(
                f"Invalid category in knowledge article {path.name}: "
                f"{front_matter['category']}"
            ) from exc

        slug = path.stem
        articles.append(
            Article(
                id=slug,
                slug=slug,
                title=title,
                category=category,
                tags=_parse_tags(front_matter["tags"]),
                summary=summary,
                content=content.strip(),
            )
        )
    return articles


def _heading_sections(content: str) -> list[tuple[str, str]]:
    matches = list(_HEADING.finditer(content))
    if not matches:
        text = content.strip()
        return [("Overview", text)] if text else []

    sections: list[tuple[str, str]] = []
    leading = content[: matches[0].start()].strip()
    if leading:
        sections.append(("Overview", leading))

    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        text = content[start:end].strip()
        if text:
            sections.append((heading, text))
    return sections


def _anchor(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _window_text(text: str, window_size: int, overlap: int) -> list[str]:
    if len(text) <= window_size:
        return [text]

    windows: list[str] = []
    start = 0
    step = max(1, window_size - overlap)
    while start < len(text):
        end = min(len(text), start + window_size)
        windows.append(text[start:end].strip())
        if end == len(text):
            break
        start += step
    return [window for window in windows if window]


def chunk_article(
    article: Article,
    *,
    window_size: int = 900,
    overlap: int = 150,
) -> list[Chunk]:
    if window_size < 1:
        raise ValueError("window_size must be greater than zero")
    if overlap < 0 or overlap >= window_size:
        raise ValueError("overlap must be non-negative and smaller than window_size")

    chunks: list[Chunk] = []
    for heading, section_text in _heading_sections(article.content):
        for window_index, window in enumerate(
            _window_text(section_text, window_size, overlap)
        ):
            prefix = f"{article.title} - {heading}"
            text = f"{prefix}\n\n{window}"
            anchor = _anchor(heading)
            source = f"kb://{article.slug}#{anchor}"
            digest = hashlib.sha256(
                f"{article.slug}|{heading}|{window_index}|{window}".encode()
            ).hexdigest()[:16]
            chunks.append(
                Chunk(
                    id=f"{article.slug}-{digest}",
                    article_id=article.id,
                    title=article.title,
                    heading=heading,
                    slug=article.slug,
                    category=article.category,
                    tags=article.tags,
                    summary=article.summary,
                    text=text,
                    source=source,
                )
            )
    return chunks