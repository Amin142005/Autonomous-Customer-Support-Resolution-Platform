from __future__ import annotations

from agents.graph import GRAPH_EDGES, GRAPH_NODES, build_support_graph, route_risk


def test_graph_exposes_expected_nodes_and_edges():
    assert "understand_ticket" in GRAPH_NODES
    assert "troubleshooting" in GRAPH_NODES
    assert "risk_check" in GRAPH_NODES
    assert "ticket_summary" in GRAPH_NODES
    assert ("troubleshooting", "resolution_planning") in GRAPH_EDGES


def test_support_graph_compiles_with_checkpointer():
    compiled = build_support_graph()
    assert compiled is not None


def test_risk_routes_policy_before_approval():
    assert route_risk({
        "escalation_required": True,
        "approval_required": True,
        "risk_level": "high",
    }) == "escalation"


def test_risk_routes_approval_before_high_risk_execution():
    assert route_risk({
        "escalation_required": False,
        "approval_required": True,
        "risk_level": "high",
    }) == "human_approval"


def test_risk_routes_low_risk_to_execution():
    assert route_risk({
        "escalation_required": False,
        "approval_required": False,
        "risk_level": "low",
    }) == "execute_resolution"
