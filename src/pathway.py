"""Pathway inference using UNO-trained graph weights.

The training (src/train.py) learned edge weights from real UNO transitions.
This module queries those weights to select a pathway for the current state.
"""
from typing import Any
from src.train import get_state_weights, get_marginal_weights
from src.retrieve import retrieve_mythoughts


def select_pathway(user_text: str, db_path: str = "data/engine.sqlite") -> dict[str, Any]:
    """Select a pedagogical pathway for the given user input.

    Uses trained UNO transition weights if the state is known,
    falls back to semantic retrieval + marginal weights for unknown states.
    """
    # Step 1: retrieve similar hyperedges for context
    retrieved = retrieve_mythoughts(user_text, k=6)

    # Step 2: try to infer state from retrieved hyperedges
    state = "unknown"
    if retrieved:
        state_counts: dict[str, float] = {}
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        for he in retrieved[:3]:
            cur.execute("""
                SELECT node_value FROM mythought_incidences
                WHERE hyperedge_id = ? AND node_type = 'student_state'
                LIMIT 1
            """, (he["id"],))
            row = cur.fetchone()
            if row:
                s = row[0]
                state_counts[s] = state_counts.get(s, 0) + he.get("similarity", 0.5)
        conn.close()
        if state_counts:
            state = max(state_counts, key=state_counts.get)

    # Step 3: query trained weights
    weights = get_state_weights(state, db_path)

    # Step 4: fallback to marginal if state has no trained functions
    if not weights["functions"]:
        marginal = get_marginal_weights(db_path)
        weights["functions"] = marginal.get("functions", [])

    # Step 5: pick top function and mechanism
    top_fn = weights["functions"][0] if weights["functions"] else {"function_id": "RM_01", "weight": 0.0}
    top_mech = weights["mechanisms"][0] if weights["mechanisms"] else {"mechanism": "none", "weight": 0.0}
    top_action = weights["teaching_actions"][0] if weights["teaching_actions"] else {"action": "", "weight": 0.0}

    # Step 6: determine phase from function
    phase = "UNMAKING"
    if top_fn["function_id"]:
        prefix = top_fn["function_id"].split("_")[0]
        phase_map = {"UM": "UNMAKING", "RM": "REMAKING", "SM": "SELF-MAKING", "ME": "META"}
        phase = phase_map.get(prefix, "UNMAKING")

    pathway = {
        "derived_by": "graph",
        "state": state,
        "phase": phase,
        "function_id": top_fn["function_id"],
        "mechanism_shape": top_mech["mechanism"],
        "teaching_action": top_action["action"],
        "register": weights.get("register", {}),
        "source_hyperedges": [h["id"] for h in retrieved[:3]],
        "weights": {
            "function_weight": round(top_fn["weight"], 3),
            "mechanism_weight": round(top_mech["weight"], 3),
            "num_candidates": len(weights["functions"]),
        },
    }

    return pathway


def make_graph_mythought(user_text: str, pathway: dict[str, Any],
                          retrieved: list[dict[str, Any]]) -> dict[str, Any]:
    """Compose the graph_mythought from selected pathway and source data."""
    pattern = ""
    if retrieved:
        fns = [h.get("function_id") for h in retrieved if h.get("function_id")]
        mechs = [h.get("mechanism_shape") for h in retrieved if h.get("mechanism_shape")]
        pattern = f"Retrieved: functions={fns[:3]}, mechanisms={mechs[:3]}"

    return {
        "derived_by": "graph",
        "user_text": user_text,
        "inferred_state": pathway["state"],
        "selected_pathway": {
            "phase": pathway["phase"],
            "function_id": pathway["function_id"],
            "mechanism_shape": pathway["mechanism_shape"],
        },
        "retrieved_pattern": pattern,
        "source_hyperedges": pathway["source_hyperedges"],
    }


def render_pathway(pathway: dict[str, Any]) -> str:
    """Template render from graph-selected pathway."""
    state = pathway["state"]
    phase = pathway["phase"]
    fn = pathway["function_id"]
    mech = pathway["mechanism_shape"]
    action = pathway["teaching_action"]

    lines = [
        f"State: {state}",
        f"Phase: {phase}",
        f"Function: {fn}",
        f"Mechanism: {mech}",
    ]
    if action:
        lines.append(f"Action: {action}")
    if pathway.get("register"):
        reg = pathway["register"]
        reg_parts = [f"{k}={v.get('value', '?')}" for k, v in reg.items() if v]
        if reg_parts:
            lines.append(f"Register: {', '.join(reg_parts)}")

    lines.append("")
    lines.append("The graph selected this pathway from UNO-trained weights.")
    lines.append(f"Source hyperedges: {len(pathway.get('source_hyperedges', []))} retrieved")
    return "\n".join(lines)
