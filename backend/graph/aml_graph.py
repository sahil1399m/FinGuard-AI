from typing import TypedDict
from langgraph.graph import StateGraph, END

from backend.agents import (
    geo_velocity, structuring, behavioral,
    prosecution, defense, judge, supervisor,
)
from backend.risk_score import compute_risk_score


# ── State ──────────────────────────────────────────────────────────────────────
class AMLState(TypedDict):
    transaction:            dict
    user_history:           list[dict]
    geo_result:              dict
    structuring_result:      dict
    behavioral_result:       dict
    risk_score:              int
    status:                  str
    breakdown:               dict
    findings:                list[dict]
    prosecution_result:      dict
    defense_result:          dict
    judge_result:            dict
    final_verdict:           str
    final_risk_score:        int
    final_reasoning:         str
    recommended_action:      str


# ── Nodes ──────────────────────────────────────────────────────────────────────
def node_geo_velocity(state: AMLState) -> dict:
    return {"geo_result": geo_velocity.run(state["transaction"])}

def node_structuring(state: AMLState) -> dict:
    return {"structuring_result": structuring.run(
        state["transaction"], state.get("user_history", [])
    )}

def node_behavioral(state: AMLState) -> dict:
    return {"behavioral_result": behavioral.run(
        state["transaction"], state.get("user_history", [])
    )}

def node_risk_score(state: AMLState) -> dict:
    geo  = state.get("geo_result", {})
    stru = state.get("structuring_result", {})
    beh  = state.get("behavioral_result", {})

    scored = compute_risk_score(
        geo_flagged          = geo.get("flagged", False),
        structuring_flagged  = stru.get("flagged", False),
        behavioral_flagged   = beh.get("flagged", False),
        amount_usd           = state["transaction"].get("amount_usd", 0),
        timestamp             = state["transaction"].get("timestamp", ""),
    )
    findings = supervisor.build_findings_summary(geo, stru, beh)

    return {
        "risk_score": scored["risk_score"],
        "status":     scored["status"],
        "breakdown":  scored["breakdown"],
        "findings":   findings,
    }

def node_prosecution(state: AMLState) -> dict:
    return {"prosecution_result": prosecution.run(state["transaction"], state["findings"])}

def node_defense(state: AMLState) -> dict:
    return {"defense_result": defense.run(state["transaction"], state["findings"])}

def node_judge(state: AMLState) -> dict:
    """Judge reads both arguments and issues the final verdict — no HITL pause."""
    result = judge.run(
        transaction         = state["transaction"],
        prosecution_result  = state["prosecution_result"],
        defense_result      = state["defense_result"],
        current_risk_score  = state["risk_score"],
    )
    return {
        "judge_result":       result,
        "final_verdict":      result["verdict"],
        "final_risk_score":   result["final_risk_score"],
        "final_reasoning":    result["reasoning"],
        "recommended_action": result["recommended_action"],
    }

def node_skip_debate(state: AMLState) -> dict:
    """Below debate threshold — rule-based verdict only, resolves immediately."""
    return {
        "prosecution_result": {},
        "defense_result":     {},
        "judge_result":       {},
        "final_verdict":      state["status"],
        "final_risk_score":   state["risk_score"],
        "final_reasoning":    "Score below debate threshold — rule-based verdict only.",
        "recommended_action": "No action required." if state["status"] == "CLEAN" else "Monitor account.",
    }


# ── Routing ────────────────────────────────────────────────────────────────────
def route_after_scoring(state: AMLState) -> str:
    return "prosecution" if supervisor.should_debate(state["risk_score"]) else "skip_debate"


# ── Build ──────────────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(AMLState)

    graph.add_node("geo_velocity", node_geo_velocity)
    graph.add_node("structuring",  node_structuring)
    graph.add_node("behavioral",   node_behavioral)
    graph.add_node("risk_score",   node_risk_score)
    graph.add_node("prosecution",  node_prosecution)
    graph.add_node("defense",      node_defense)
    graph.add_node("judge",        node_judge)
    graph.add_node("skip_debate",  node_skip_debate)

    graph.set_entry_point("geo_velocity")
    graph.add_edge("geo_velocity", "structuring")
    graph.add_edge("structuring",  "behavioral")
    graph.add_edge("behavioral",   "risk_score")

    graph.add_conditional_edges(
        "risk_score",
        route_after_scoring,
        {"prosecution": "prosecution", "skip_debate": "skip_debate"},
    )

    graph.add_edge("prosecution", "defense")
    graph.add_edge("defense",     "judge")
    graph.add_edge("judge",       END)
    graph.add_edge("skip_debate", END)

    return graph.compile()


aml_app = build_graph()


async def run_aml_pipeline(transaction: dict, user_history: list[dict]) -> dict:
    initial_state: AMLState = {
        "transaction":         transaction,
        "user_history":        user_history,
        "geo_result":          {},
        "structuring_result":  {},
        "behavioral_result":   {},
        "risk_score":          0,
        "status":              "PENDING",
        "breakdown":           {},
        "findings":            [],
        "prosecution_result":  {},
        "defense_result":      {},
        "judge_result":        {},
        "final_verdict":       "PENDING",
        "final_risk_score":    0,
        "final_reasoning":     "",
        "recommended_action":  "",
    }
    return await aml_app.ainvoke(initial_state)