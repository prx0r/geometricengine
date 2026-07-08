from typing import Any
import sqlite3
from src.train import query as trained_query
from src.retrieve import retrieve_mythoughts


def select_pathway(user_text: str,
                   retrieved_hyperedges: list[dict] | None = None,
                   db_path: str = "data/engine.sqlite") -> dict[str, Any]:
    retrieved = retrieved_hyperedges
    if retrieved is None:
        retrieved = retrieve_mythoughts(user_text, k=6)

    state = "unknown"
    state_counts: dict[str, float] = {}
    if retrieved:
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

    weights = trained_query(state, db_path=db_path)

    top_fn = weights["functions"][0] if weights["functions"] else {"id": "RM_01", "weight": 0.0}
    top_mech = weights["mechanisms"][0] if weights["mechanisms"] else {"id": "none", "weight": 0.0}
    top_action = weights["actions"][0] if weights["actions"] else {"action": "", "weight": 0.0}

    phase = "UNMAKING"
    fn_id = top_fn["id"]
    if fn_id:
        prefix = fn_id.split("_")[0]
        phase_map = {"UM": "UNMAKING", "RM": "REMAKING", "SM": "SELF-MAKING", "ME": "META"}
        phase = phase_map.get(prefix, "UNMAKING")

    fallback = weights.get("similarity_fallback")
    derived = f"graph_from_{fallback['source']}" if fallback else "graph"

    return {
        "derived_by": derived,
        "state": state,
        "phase": phase,
        "function_id": fn_id,
        "mechanism_shape": top_mech["id"],
        "teaching_action": top_action["action"],
        "register": weights.get("register", {}),
        "source_hyperedges": [h["id"] for h in retrieved[:3]],
        "similarity_fallback": fallback,
        "weights": {
            "function_weight": round(top_fn["weight"], 3),
            "mechanism_weight": round(top_mech["weight"], 3),
            "num_candidates": len(weights["functions"]),
        },
    }


def make_graph_mythought(user_text: str, pathway: dict[str, Any],
                          retrieved: list[dict[str, Any]]) -> dict[str, Any]:
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
    return "\n".join(lines)
