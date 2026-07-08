import sqlite3
import json
import uuid
from datetime import datetime


def save_pathway_run(db_path: str, state: dict) -> str:
    run_id = str(uuid.uuid4())
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    graph_mythought = state.get("graph_mythought", {})
    pathway = state.get("pathway", {})

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
        "",
        "",
        state.get("final_response", ""),
        datetime.utcnow().isoformat(),
    ))

    conn.commit()
    conn.close()
    return run_id


def apply_feedback(db_path: str, graph_mythought_id: str, score: int, tags: list[str] = None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("UPDATE graph_mythoughts SET score = ? WHERE id = ?", (score, graph_mythought_id))
    cur.execute("""
        INSERT INTO feedback_events
        (id, graph_mythought_id, score, tags_json, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), graph_mythought_id, score, json.dumps(tags or []), datetime.utcnow().isoformat()))

    # Fine-tune policy weights based on feedback
    cur.execute("SELECT graph_mythought_json FROM graph_mythoughts WHERE id = ?", (graph_mythought_id,))
    row = cur.fetchone()
    if row:
        gm = json.loads(row[0])
        pathway = gm.get("selected_pathway", {})
        state = gm.get("inferred_state", "unknown")
        fn = pathway.get("function_id", "")
        mech = pathway.get("mechanism_shape", "")

        reward = score / 2.0

        if state and fn:
            edge_id = f"fb_state_fn_{state}_{fn}".replace(" ", "_")[:100]
            cur.execute("""
                INSERT INTO policy_weights
                (id, from_type, from_value, to_type, to_value, weight, success_count, failure_count)
                VALUES (?, 'state', ?, 'function', ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    weight = weight + ?, success_count = success_count + ?, failure_count = failure_count + ?
            """, (edge_id, state, fn, 0.0 + 0.1 * reward, 1 if reward > 0 else 0, 1 if reward < 0 else 0,
                  0.1 * reward, 1 if reward > 0 else 0, 1 if reward < 0 else 0))

    conn.commit()
    conn.close()
