from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from backend.app.schemas.common import Category
from backend.app.schemas.workflow import Evidence, PreviousCase
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.result import ToolResult

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class KnowledgeAgent:
    """Retrieve cited knowledge and find similar resolved cases."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        previous_cases: Sequence[Mapping[str, Any] | PreviousCase] | None = None,
        sample_data_dir: str | Path = "sample_data",
    ) -> None:
        self.registry = registry
        self.previous_cases = (
            tuple(previous_cases)
            if previous_cases is not None
            else self._load_previous_cases(sample_data_dir)
        )

    async def run(
        self,
        query: str,
        *,
        category: Category | str | None = None,
        mode: str = "hybrid",
        top_k: int = 5,
    ) -> tuple[list[Evidence], list[PreviousCase]]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k < 1 or top_k > 20:
            raise ValueError("top_k must be between 1 and 20")

        evidence = await self.retrieve(
            normalized_query,
            category=category,
            mode=mode,
            top_k=top_k,
        )
        similar_cases = self.similar_cases(normalized_query, category, limit=3)
        return evidence, similar_cases

    async def retrieve(
        self,
        query: str,
        *,
        category: Category | str | None = None,
        mode: str = "hybrid",
        top_k: int = 5,
    ) -> list[Evidence]:
        normalized_category = (
            str(category.value if isinstance(category, Category) else category)
            if category is not None
            else None
        )
        try:
            result: ToolResult | object = await self.registry.execute(
                "search_docs",
                {
                    "query": query,
                    "category": normalized_category,
                    "mode": mode,
                    "top_k": top_k,
                },
            )
        except Exception:  # noqa: BLE001
            return []

        if isinstance(result, ToolResult):
            if not result.ok or not isinstance(result.output, list):
                return []
            output = result.output
        elif isinstance(result, list):
            output = result
        else:
            return []

        evidence: list[Evidence] = []
        for item in output:
            if not isinstance(item, Mapping):
                continue
            try:
                evidence.append(
                    Evidence(
                        id=str(item.get("id", "")),
                        title=str(item.get("title", "")),
                        source=str(item.get("source", "")),
                        snippet=str(item.get("snippet", "")),
                        score=float(item.get("score", 0.0)),
                        url=str(item.get("url", "")),
                        article_id=str(item.get("article_id", "")),
                    )
                )
            except (TypeError, ValueError):
                continue
        return evidence

    def similar_cases(
        self,
        query: str,
        category: Category | str | None = None,
        *,
        limit: int = 3,
    ) -> list[PreviousCase]:
        if limit < 1:
            return []
        normalized_category = (
            str(category.value if isinstance(category, Category) else category)
            if category is not None
            else None
        )
        query_tokens = self._tokens(query)
        matches: list[tuple[float, PreviousCase]] = []

        for raw_case in self.previous_cases:
            if isinstance(raw_case, PreviousCase):
                case = raw_case
            elif isinstance(raw_case, Mapping):
                case = self._case_from_mapping(raw_case)
            else:
                continue

            case_category = (
                case.category.value
                if isinstance(case.category, Category)
                else case.category
            )
            if (
                normalized_category is not None
                and case_category is not None
                and str(case_category).lower() != normalized_category.lower()
            ):
                continue

            case_text = " ".join(
                (
                    case.subject,
                    case.resolution,
                    case.summary,
                    str(case_category or ""),
                )
            )
            case_tokens = self._tokens(case_text)
            similarity = self._jaccard(query_tokens, case_tokens)
            if similarity <= 0:
                continue
            matches.append(
                (
                    similarity,
                    case.model_copy(
                        update={
                            "similarity": similarity,
                            "ticket_number": case.ticket_number or case.number,
                        }
                    ),
                )
            )

        matches.sort(
            key=lambda match: (
                match[0],
                match[1].ticket_number,
            ),
            reverse=True,
        )
        return [case for _, case in matches[:limit]]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(_TOKEN_PATTERN.findall(text.casefold()))

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    @staticmethod
    def _case_from_mapping(case: Mapping[str, Any]) -> PreviousCase:
        category_value = case.get("category")
        category: Category | None = None
        if isinstance(category_value, str):
            try:
                category = Category(category_value)
            except ValueError:
                category = None

        return PreviousCase(
            ticket_number=str(case.get("id", "") or case.get("ticket_number", "")),
            number=str(case.get("number", "") or case.get("id", "")),
            subject=str(case.get("subject", "")),
            category=category,
            resolution=str(case.get("resolution", "")),
            summary=str(case.get("summary", "")),
            similarity=0.0,
        )

    @staticmethod
    def _load_previous_cases(
        sample_data_dir: str | Path,
    ) -> tuple[Mapping[str, Any] | PreviousCase, ...]:
        path = Path(sample_data_dir) / "previous_resolutions.json"
        if not path.is_file():
            return ()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ()
        if not isinstance(payload, list):
            return ()
        return tuple(item for item in payload if isinstance(item, Mapping))


__all__ = ["KnowledgeAgent"]
