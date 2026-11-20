from agents.specialists.knowledge import KnowledgeAgent
from backend.app.schemas.common import Category
from backend.app.schemas.workflow import Evidence
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.result import ToolResult


class EvidenceTool:
    name = "search_docs"

    async def ainvoke(self, input: dict[str, object]) -> object:
        del input
        return [
            {
                "id": "sso-login",
                "title": "SSO login troubleshooting",
                "source": "kb://sso-login-troubleshooting#login",
                "snippet": "Verify identity provider settings.",
                "score": 0.91,
                "url": "/knowledge/sso-login",
                "article_id": "sso-login",
            }
        ]


async def test_knowledge_agent_retrieves_cited_evidence():
    registry = ToolRegistry(timeout_seconds=1)
    registry.register(EvidenceTool())
    agent = KnowledgeAgent(
        registry,
        previous_cases=[
            {
                "id": "CASE-001",
                "category": "login_issue",
                "subject": "Users unable to complete SSO login",
                "resolution": "Confirmed the identity provider configuration.",
            }
        ],
    )

    evidence = await agent.retrieve(
        "SSO login fails",
        category=Category.LOGIN_ISSUE,
    )

    assert evidence == [
        Evidence(
            id="sso-login",
            title="SSO login troubleshooting",
            source="kb://sso-login-troubleshooting#login",
            snippet="Verify identity provider settings.",
            score=0.91,
            url="/knowledge/sso-login",
            article_id="sso-login",
        )
    ]


def test_knowledge_agent_finds_similar_resolved_case_with_jaccard():
    registry = ToolRegistry(timeout_seconds=1)
    registry.register(EvidenceTool())
    agent = KnowledgeAgent(
        registry,
        previous_cases=[
            {
                "id": "CASE-001",
                "category": "login_issue",
                "subject": "Users unable to complete SSO login",
                "resolution": "Confirmed the identity provider configuration.",
            },
            {
                "id": "CASE-002",
                "category": "billing",
                "subject": "Seat count differs from invoice",
                "resolution": "Reviewed the billing seat calculation.",
            },
        ],
    )

    cases = agent.similar_cases(
        "SSO login fails for the whole team",
        Category.LOGIN_ISSUE,
        limit=3,
    )

    assert len(cases) == 1
    assert cases[0].ticket_number == "CASE-001"
    assert cases[0].similarity > 0


async def test_knowledge_agent_returns_empty_evidence_when_tool_fails():
    registry = ToolRegistry(timeout_seconds=1)

    async def unknown_execute(
        name: str,
        args: dict[str, object],
        approved: bool = False,
    ) -> ToolResult:
        del name, args, approved
        return ToolResult.failure(
            "search_docs",
            "unknown_tool",
            "unknown tool",
        )

    registry.execute = unknown_execute
    agent = KnowledgeAgent(registry, previous_cases=[])

    evidence = await agent.retrieve("storage quota")

    assert evidence == []
