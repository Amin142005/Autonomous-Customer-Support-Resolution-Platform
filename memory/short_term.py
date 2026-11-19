from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from backend.app.core.redis import RedisProtocol, create_redis_client

SHORT_TERM_TTL_SECONDS = 24 * 60 * 60
CONVERSATION_TTL_SECONDS = SHORT_TERM_TTL_SECONDS
WORKFLOW_TTL_SECONDS = SHORT_TERM_TTL_SECONDS
RETRIEVAL_CACHE_TTL_SECONDS = 300
CACHE_TTL_SECONDS = RETRIEVAL_CACHE_TTL_SECONDS
WORKFLOW_STATE_TTL_SECONDS = WORKFLOW_TTL_SECONDS


def conversation_key(ticket_id: str) -> str:
    normalized = ticket_id.strip()
    if not normalized:
        raise ValueError("ticket_id must not be empty")
    return f"conversation:{normalized}"


def workflow_key(workflow_id: str) -> str:
    normalized = workflow_id.strip()
    if not normalized:
        raise ValueError("workflow_id must not be empty")
    return f"workflow:{normalized}"


def rag_cache_key(
    mode: str,
    category: str | None,
    top_k: int,
    query: str,
) -> str:
    normalized_mode = mode.strip().lower() or "hybrid"
    normalized_category = (category or "all").strip().lower() or "all"
    if top_k < 1:
        raise ValueError("top_k must be greater than zero")
    normalized_query = " ".join(query.split()).lower()
    if not normalized_query:
        raise ValueError("query must not be empty")
    return (
        f"rag:{normalized_mode}:{normalized_category}:"
        f"{top_k}:{normalized_query}"
    )


build_rag_cache_key = rag_cache_key
get_rag_cache_key = rag_cache_key


class ShortTermMemory:
    """Store short-lived workflow state and retrieval cache values in Redis."""

    def __init__(
        self,
        redis_client: RedisProtocol | None = None,
        *,
        conversation_ttl: int = CONVERSATION_TTL_SECONDS,
        workflow_ttl: int = WORKFLOW_TTL_SECONDS,
        cache_ttl: int = RETRIEVAL_CACHE_TTL_SECONDS,
    ) -> None:
        if conversation_ttl <= 0:
            raise ValueError("conversation_ttl must be greater than zero")
        if workflow_ttl <= 0:
            raise ValueError("workflow_ttl must be greater than zero")
        if cache_ttl <= 0:
            raise ValueError("cache_ttl must be greater than zero")
        self.redis_client = redis_client
        self.conversation_ttl = conversation_ttl
        self.workflow_ttl = workflow_ttl
        self.cache_ttl = cache_ttl

    async def _client(self) -> RedisProtocol:
        if self.redis_client is None:
            self.redis_client = await create_redis_client()
        return self.redis_client

    @staticmethod
    def _encode(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode(value: str | bytes | None) -> Any:
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def set_conversation(
        self,
        ticket_id: str,
        messages: list[object] | tuple[object, ...],
    ) -> bool:
        client = await self._client()
        result = await client.set(
            conversation_key(ticket_id),
            self._encode(list(messages)),
            ex=self.conversation_ttl,
        )
        return result is True or result == "OK"

    async def get_conversation(
        self,
        ticket_id: str,
    ) -> list[Any]:
        client = await self._client()
        value = self._decode(await client.get(conversation_key(ticket_id)))
        if value is None:
            return []
        if not isinstance(value, list):
            return [value]
        return value

    async def append_conversation(
        self,
        ticket_id: str,
        message: Mapping[str, object] | object,
    ) -> list[Any]:
        messages = await self.get_conversation(ticket_id)
        encoded_message = dict(message) if isinstance(message, Mapping) else message
        messages.append(encoded_message)
        await self.set_conversation(ticket_id, messages)
        return messages

    append_message = append_conversation
    save_conversation = set_conversation
    load_conversation = get_conversation

    async def delete_conversation(self, ticket_id: str) -> bool:
        client = await self._client()
        return await client.delete(conversation_key(ticket_id)) > 0

    clear_conversation = delete_conversation

    async def set_workflow_state(
        self,
        workflow_id: str,
        state: Mapping[str, object] | object,
    ) -> bool:
        client = await self._client()
        result = await client.set(
            workflow_key(workflow_id),
            self._encode(dict(state) if isinstance(state, Mapping) else state),
            ex=self.workflow_ttl,
        )
        return result is True or result == "OK"

    set_workflow = set_workflow_state
    save_workflow_state = set_workflow_state

    async def get_workflow_state(
        self,
        workflow_id: str,
    ) -> Any | None:
        client = await self._client()
        return self._decode(await client.get(workflow_key(workflow_id)))

    get_workflow = get_workflow_state
    load_workflow_state = get_workflow_state

    async def delete_workflow_state(self, workflow_id: str) -> bool:
        client = await self._client()
        return await client.delete(workflow_key(workflow_id)) > 0

    async def set_retrieval_cache(
        self,
        mode: str,
        category: str | None,
        top_k: int,
        query: str,
        value: object,
    ) -> bool:
        client = await self._client()
        result = await client.set(
            rag_cache_key(mode, category, top_k, query),
            self._encode(value),
            ex=self.cache_ttl,
        )
        return result is True or result == "OK"

    cache_retrieval = set_retrieval_cache

    async def get_retrieval_cache(
        self,
        mode: str,
        category: str | None,
        top_k: int,
        query: str,
    ) -> Any | None:
        client = await self._client()
        return self._decode(
            await client.get(rag_cache_key(mode, category, top_k, query))
        )

    get_cached_retrieval = get_retrieval_cache

    async def delete_retrieval_cache(
        self,
        mode: str,
        category: str | None,
        top_k: int,
        query: str,
    ) -> bool:
        client = await self._client()
        return await client.delete(
            rag_cache_key(mode, category, top_k, query)
        ) > 0
