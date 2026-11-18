from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from backend.app.core.config import get_settings
from backend.app.services.knowledge_service import KnowledgeService


async def _ingest(articles_dir: str | None) -> dict[str, int]:
    settings = get_settings()
    service = KnowledgeService.from_settings(
        settings,
        articles_dir=articles_dir,
    )
    summary = await service.reindex()
    return {
        "articles_indexed": summary.articles_indexed,
        "chunks_indexed": summary.chunks_indexed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the configured CloudDesk knowledge vector index."
    )
    parser.add_argument(
        "--articles-dir",
        type=Path,
        help="Markdown article directory (defaults to SAMPLE_DATA_DIR/knowledge_base).",
    )
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(
            _ingest(str(args.articles_dir) if args.articles_dir else None)
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Knowledge ingest failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
