import sqlite3
import json
import uuid
from datetime import datetime


def save_pathway_run(db_path: str, state: dict) -> str:
    run_id = str(uuid.uuid4())
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pathway_runs
        (id, thread_id, user_text, retrieved_hyperedges_json, candidate_nodes_json,
         hermes_seed_json, final_response, score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (
        run_id,
        state.get("thread_id", "unknown"),
        state.get("user_text", ""),
        json.dumps(state.get("retrieved_hyperedges", [])),
        json.dumps(state.get("candidate_nodes", {})),
        json.dumps(state.get("hermes_seed", {})),
        state.get("final_response", ""),
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()
    return run_id


def apply_feedback(db_path: str, pathway_run_id: str, score: int, tags: list[str] = None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        UPDATE pathway_runs SET score = ? WHERE id = ?
    """, (score, pathway_run_id))
    cur.execute("""
        INSERT INTO feedback_events
        (id, pathway_run_id, score, tags_json, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        str(uuid.uuid4()),
        pathway_run_id,
        score,
        json.dumps(tags or []),
        datetime.utcnow().isoformat(),
    ))

    reward = score / 2.0
    cur.execute("""
        SELECT retrieved_hyperedges_json, hermes_seed_json
        FROM pathway_runs WHERE id = ?
    """, (pathway_run_id,))
    row = cur.fetchone()
    if row:
        hyperedges = json.loads(row[0])
        seed = json.loads(row[1])
        selected_move = seed.get("selected_move", "")
        mechanism = seed.get("mechanism", "")

        for he in hyperedges:
            fn = he.get("function_id")
            if fn:
                cur.execute("""
                    INSERT INTO policy_weights
                    (id, from_type, from_value, to_type, to_value, weight, success_count, failure_count)
                    VALUES (?, 'retrieved_function', ?, 'selected_move', ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        weight = weight + ?,
                        success_count = success_count + ?,
                        failure_count = failure_count + ?
                """, (
                    f"pw_fn_{fn}_{selected_move}",
                    fn, selected_move,
                    0.0 + 0.1 * reward,
                    1 if reward > 0 else 0,
                    1 if reward < 0 else 0,
                    0.1 * reward,
                    1 if reward > 0 else 0,
                    1 if reward < 0 else 0,
                ))

    conn.commit()
    conn.close()
