import fakeredis.aioredis
import pytest

from memory.short_term import (
    CONVERSATION_TTL_SECONDS,
    RETRIEVAL_CACHE_TTL_SECONDS,
    WORKFLOW_TTL_SECONDS,
    ShortTermMemory,
    conversation_key,
    rag_cache_key,
    workflow_key,
)


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def test_short_term_memory_uses_expected_ttl_constants(fake_redis):
    memory = ShortTermMemory(fake_redis)

    await memory.set_conversation("ticket-1", [{"role": "customer"}])
    await memory.set_workflow_state("workflow-1", {"current_node": "understand"})
    await memory.set_retrieval_cache(
        "hybrid",
        "billing",
        5,
        "Invoice refund",
        [{"article_id": "refund"}],
    )

    assert 0 < await fake_redis.ttl("conversation:ticket-1") <= CONVERSATION_TTL_SECONDS
    assert 0 < await fake_redis.ttl("workflow:workflow-1") <= WORKFLOW_TTL_SECONDS
    assert (
        0
        < await fake_redis.ttl(
            "rag:hybrid:billing:5:invoice refund"
        )
        <= RETRIEVAL_CACHE_TTL_SECONDS
    )


async def test_conversation_is_json_round_tripped(fake_redis):
    memory = ShortTermMemory(fake_redis)

    await memory.append_conversation(
        "ticket-1",
        {"role": "customer", "body": "SSO is failing"},
    )
    await memory.append_conversation(
        "ticket-1",
        {"role": "agent", "body": "We are investigating"},
    )

    assert await memory.get_conversation("ticket-1") == [
        {"role": "customer", "body": "SSO is failing"},
        {"role": "agent", "body": "We are investigating"},
    ]
    assert await memory.delete_conversation("ticket-1")
    assert await memory.get_conversation("ticket-1") == []


async def test_workflow_state_is_json_round_tripped(fake_redis):
    memory = ShortTermMemory(fake_redis)

    await memory.set_workflow_state(
        "workflow-1",
        {"current_node": "troubleshooting", "completed": ["understand"]},
    )

    assert await memory.get_workflow_state("workflow-1") == {
        "current_node": "troubleshooting",
        "completed": ["understand"],
    }

    assert await memory.delete_workflow_state("workflow-1")
    assert await memory.get_workflow_state("workflow-1") is None


async def test_retrieval_cache_is_keyed_by_query_parameters(fake_redis):
    memory = ShortTermMemory(fake_redis)

    await memory.set_retrieval_cache(
        "Semantic",
        "Billing",
        3,
        "  Invoice   refund  ",
        [{"id": "refund-1"}],
    )

    assert rag_cache_key("semantic", "billing", 3, "Invoice refund") == (
        "rag:semantic:billing:3:invoice refund"
    )
    assert await memory.get_retrieval_cache(
        "semantic",
        "billing",
        3,
        "Invoice refund",
    ) == [{"id": "refund-1"}]
    assert await memory.delete_retrieval_cache(
        "semantic",
        "billing",
        3,
        "Invoice refund",
    )


def test_key_builders_reject_empty_ids():
    with pytest.raises(ValueError, match="ticket_id"):
        conversation_key("  ")
    with pytest.raises(ValueError, match="workflow_id"):
        workflow_key("")


async def test_missing_values_return_none_or_empty(fake_redis):
    memory = ShortTermMemory(fake_redis)

    assert await memory.get_conversation("missing") == []
    assert await memory.get_workflow_state("missing") is None
    assert await memory.get_retrieval_cache(
        "hybrid",
        None,
        5,
        "missing query",
    ) is None
