"""Train graph edge weights from UNO transition data.

Each UNO transition is a training example:
    from_state → (function, mechanism, register, teaching_actions) → to_state

Training = counting co-occurrences with similarity weighting.
The resulting weights are stored in policy_weights table.
"""
import sqlite3
import json
import uuid
from collections import defaultdict
from typing import Any


def load_transitions(db_path: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT from_state, to_state, move_function, mechanism_shape,
               teaching_actions_json, register_json, prediction_match
        FROM transitions
    """)
    rows = cur.fetchall()
    conn.close()

    transitions = []
    for r in rows:
        transitions.append({
            "from_state": r[0],
            "to_state": r[1],
            "function_id": r[2],
            "mechanism_shape": r[3],
            "teaching_actions": json.loads(r[4]) if r[4] else [],
            "register": json.loads(r[5]) if r[5] else None,
            "prediction_match": r[6],
        })
    return transitions


def train_weights(db_path: str, output_db: str = None):
    """Train graph weights from all UNO transitions."""
    transitions = load_transitions(db_path)
    output_db = output_db or db_path

    # Weight stores: key -> (total_weight, success_count, failure_count)
    # Keys: (from_type, from_value, to_type, to_value)
    weights: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)

    for t in transitions:
        from_state = t["from_state"]
        fn = t["function_id"]
        mech = t["mechanism_shape"]
        actions = t["teaching_actions"]
        reg = t["register"]
        to_state = t["to_state"]
        match = t["prediction_match"]

        # Base reward: transitions are implicit positive examples
        if match == "true":
            reward = 1.0
        elif match == "partial":
            reward = 0.5
        else:
            reward = 0.3  # unknown: mild positive (happened in real therapy)

        if from_state and fn:
            weights[("state", from_state, "function", fn)].append(reward)
        if from_state and mech:
            weights[("state", from_state, "mechanism", mech)].append(reward)
        if fn and to_state:
            weights[("function", fn, "next_state", to_state)].append(reward)
        if fn and mech:
            weights[("function", fn, "mechanism", mech)].append(reward)

        if from_state and reg:
            for i, dim in enumerate(["intensity", "intimacy", "attunement", "style", "depth", "meta_mode"]):
                if i < len(reg) and reg[i] is not None:
                    weights[("state", from_state, f"register_{dim}", str(reg[i]))].append(reward)

        for action in actions:
            if from_state and action:
                weights[("state", from_state, "teaching_action", action)].append(reward)
            if fn and action:
                weights[("function", fn, "teaching_action", action)].append(reward)

    conn = sqlite3.connect(output_db)
    cur = conn.cursor()

    # Ensure schema has policy_weights
    cur.execute("""
        CREATE TABLE IF NOT EXISTS policy_weights (
            id TEXT PRIMARY KEY,
            from_type TEXT,
            from_value TEXT,
            to_type TEXT,
            to_value TEXT,
            weight REAL DEFAULT 0.0,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_edge
        ON policy_weights(from_type, from_value, to_type, to_value)
    """)

    inserted = 0
    for key, rewards in weights.items():
        from_type, from_val, to_type, to_val = key
        avg_reward = sum(rewards) / len(rewards)
        successes = sum(1 for r in rewards if r >= 0.5)
        failures = sum(1 for r in rewards if r < 0.3)

        edge_id = f"trained_{from_type}_{from_val}_{to_type}_{to_val}"
        edge_id = edge_id.replace(" ", "_").replace("/", "_")[:100]

        cur.execute("""
            INSERT INTO policy_weights
            (id, from_type, from_value, to_type, to_value, weight, success_count, failure_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                weight = weight + ?,
                success_count = success_count + ?,
                failure_count = failure_count + ?
        """, (
            edge_id, from_type, from_val, to_type, to_val,
            avg_reward, successes, failures,
            avg_reward * 0.1,
            successes,
            failures,
        ))
        inserted += 1

    # Also train marginal distributions: what's most common overall?
    # state -> function marginal
    state_fn_marginal: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in transitions:
        s, fn = t["from_state"], t["function_id"]
        if s and fn:
            state_fn_marginal[s][fn] += 1.0
    for state, fn_counts in state_fn_marginal.items():
        total = sum(fn_counts.values())
        for fn, count in fn_counts.items():
            edge_id = f"marginal_state_fn_{state}_{fn}".replace(" ", "_").replace("/", "_")[:100]
            cur.execute("""
                INSERT INTO policy_weights
                (id, from_type, from_value, to_type, to_value, weight, success_count, failure_count)
                VALUES (?, 'marginal_state', ?, 'marginal_function', ?, ?, 1, 0)
                ON CONFLICT(id) DO UPDATE SET weight = weight + ?
            """, (edge_id, state, fn, count / total, count / total))

    conn.commit()
    conn.close()
    print(f"Trained {inserted} policy weights from {len(transitions)} transitions")


def get_state_weights(state: str, db_path: str = "data/engine.sqlite") -> dict[str, list]:
    """Query trained weights for a given state (inference helper)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    result = {
        "functions": [],
        "mechanisms": [],
        "teaching_actions": [],
        "register": {},
    }

    cur.execute("""
        SELECT to_value, weight, success_count, failure_count
        FROM policy_weights
        WHERE from_type = 'state' AND from_value = ? AND to_type = 'function'
        ORDER BY weight DESC
    """, (state,))
    result["functions"] = [{"function_id": r[0], "weight": r[1], "successes": r[2], "failures": r[3]} for r in cur.fetchall()]

    cur.execute("""
        SELECT to_value, weight, success_count, failure_count
        FROM policy_weights
        WHERE from_type = 'state' AND from_value = ? AND to_type = 'mechanism'
        ORDER BY weight DESC
    """, (state,))
    result["mechanisms"] = [{"mechanism": r[0], "weight": r[1]} for r in cur.fetchall()]

    cur.execute("""
        SELECT to_value, weight
        FROM policy_weights
        WHERE from_type = 'state' AND from_value = ? AND to_type = 'teaching_action'
        ORDER BY weight DESC
    """, (state,))
    result["teaching_actions"] = [{"action": r[0], "weight": r[1]} for r in cur.fetchall()]

    for dim in ["intensity", "intimacy", "attunement", "style", "depth", "meta_mode"]:
        cur.execute("""
            SELECT to_value, weight
            FROM policy_weights
            WHERE from_type = 'state' AND from_value = ? AND to_type = ?
            ORDER BY weight DESC LIMIT 1
        """, (state, f"register_{dim}"))
        row = cur.fetchone()
        if row:
            result["register"][dim] = {"value": row[0], "weight": row[1]}

    conn.close()
    return result


def get_marginal_weights(db_path: str = "data/engine.sqlite") -> dict[str, list]:
    """Get marginal (overall most common) function weights for unknown states."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT from_value, to_value, weight
        FROM policy_weights
        WHERE from_type = 'marginal_state'
        ORDER BY weight DESC LIMIT 10
    """)
    rows = cur.fetchall()
    conn.close()
    return {
        "functions": [{"function_id": r[1], "weight": r[2]} for r in rows],
    }


if __name__ == "__main__":
    train_weights("data/engine.sqlite")
    print("\nSample weights for 'fearful_disclosure':")
    w = get_state_weights("fearful_disclosure")
    for fn in w["functions"][:5]:
        print(f"  function {fn['function_id']}: weight={fn['weight']:.3f}")
    for mech in w["mechanisms"][:5]:
        print(f"  mechanism {mech['mechanism']}: weight={mech['weight']:.3f}")
