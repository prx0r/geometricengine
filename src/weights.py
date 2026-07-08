import sqlite3
import json
import uuid
from datetime import datetime


def save_pathway_run(db_path: str, state: dict) -> str:
    run_id = str(uuid.uuid4())
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    graph_mythought = state.get("graph_mythought", {})
    selected_pathway = state.get("selected_pathway", {})
    response_form = state.get("response_form", {})

    response_form_name = ""
    if isinstance(response_form, dict):
        response_form_name = response_form.get("response_form", "")
    elif isinstance(response_form, str):
        response_form_name = response_form

    pathway_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO selected_pathways
        (id, pathway_candidate_id, graph_mythought_id, thread_id, selected_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        pathway_id,
        str(uuid.uuid4()),
        run_id,
        state.get("thread_id", "unknown"),
        json.dumps(selected_pathway),
        datetime.utcnow().isoformat(),
    ))

    cur.execute("""
        INSERT INTO graph_mythoughts
        (id, thread_id, user_text, graph_mythought_json, pathway_id,
         response_form, rendered_response, score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (
        run_id,
        state.get("thread_id", "unknown"),
        state.get("user_text", ""),
        json.dumps(graph_mythought),
        pathway_id,
        response_form_name,
        state.get("final_response", ""),
        datetime.utcnow().isoformat(),
    ))

    cur.execute("""
        INSERT INTO rendered_responses
        (id, graph_mythought_id, response_form, rendered_text, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        str(uuid.uuid4()),
        run_id,
        response_form_name,
        state.get("final_response", ""),
        datetime.utcnow().isoformat(),
    ))

    conn.commit()
    conn.close()
    return run_id


def load_policy_weights(db_path: str) -> dict[tuple, float]:
    weights: dict[tuple, float] = {}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT from_type, from_value, to_type, to_value, weight, success_count, failure_count FROM policy_weights")
        for row in cur.fetchall():
            from_type, from_val, to_type, to_val, weight, succ, fail = row
            total = succ + fail
            effective = weight * (succ / total) if total > 0 else weight
            weights[(from_type, from_val, to_type, to_val)] = effective
        conn.close()
    except Exception:
        pass
    return weights


def apply_feedback(db_path: str, graph_mythought_id: str, score: int, tags: list[str] = None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        UPDATE graph_mythoughts SET score = ? WHERE id = ?
    """, (score, graph_mythought_id))

    cur.execute("""
        INSERT INTO feedback_events
        (id, graph_mythought_id, score, tags_json, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        str(uuid.uuid4()),
        graph_mythought_id,
        score,
        json.dumps(tags or []),
        datetime.utcnow().isoformat(),
    ))

    reward = score / 2.0

    cur.execute("""
        SELECT graph_mythought_json
        FROM graph_mythoughts WHERE id = ?
    """, (graph_mythought_id,))
    row = cur.fetchone()
    if row:
        gm = json.loads(row[0])
        selected_pathway = gm.get("selected_pathway", {})
        selected_fn = selected_pathway.get("function_id", "")
        selected_mech = selected_pathway.get("mechanism_shape", "")
        selected_phase = selected_pathway.get("phase", "")

        if selected_fn and selected_mech:
            cur.execute("""
                INSERT INTO policy_weights
                (id, from_type, from_value, to_type, to_value, weight, success_count, failure_count)
                VALUES (?, 'selected_function', ?, 'selected_mechanism', ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    weight = weight + ?,
                    success_count = success_count + ?,
                    failure_count = failure_count + ?
            """, (
                f"pw_fn_mech_{selected_fn}_{selected_mech}",
                selected_fn, selected_mech,
                0.0 + 0.1 * reward,
                1 if reward > 0 else 0,
                1 if reward < 0 else 0,
                0.1 * reward,
                1 if reward > 0 else 0,
                1 if reward < 0 else 0,
            ))

        if selected_phase and selected_fn:
            cur.execute("""
                INSERT INTO policy_weights
                (id, from_type, from_value, to_type, to_value, weight, success_count, failure_count)
                VALUES (?, 'selected_phase', ?, 'selected_function', ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    weight = weight + ?,
                    success_count = success_count + ?,
                    failure_count = failure_count + ?
            """, (
                f"pw_phase_fn_{selected_phase}_{selected_fn}",
                selected_phase, selected_fn,
                0.0 + 0.1 * reward,
                1 if reward > 0 else 0,
                1 if reward < 0 else 0,
                0.1 * reward,
                1 if reward > 0 else 0,
                1 if reward < 0 else 0,
            ))

    conn.commit()
    conn.close()
